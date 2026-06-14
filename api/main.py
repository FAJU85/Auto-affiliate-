"""FastAPI backend for the affiliate-posting bot (HuggingFace Spaces, port 7860)."""

import asyncio
import csv
import io
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)

from . import pipeline
from .ai import text as ai_text
from .utils import budget, logger, metrics, settings
from .utils.snapshot import record_response
from .utils.circuit_breaker import all_statuses as cb_statuses, reset_breaker, reset_all as cb_reset_all
from .utils.telemetry import golden_signals

DASHBOARD = Path(__file__).resolve().parent.parent / "src" / "dashboard.html"

# Env vars surfaced in /api/debug and used to compute setup warnings.
ENV_KEYS = [
    "BSKY_HANDLE", "BSKY_APP_PASSWORD", "SOVRN_API_KEY", "GROQ_API_KEY",
    "MISTRAL_API_KEY", "ADMITAD_CLIENT_ID", "TAKEADS_API_KEY",
    "TRAVELPAYOUTS_TOKEN", "SPACE_HOST", "CRON_SCHEDULE",
]
REQUIRED_VARS: list[str] = []  # Bluesky is optional when other platforms are selected

NETWORKS = [
    {"key": "sovrn",         "name": "SOVRN Commerce", "env": "SOVRN_API_KEY"},
    {"key": "admitad",       "name": "Admitad",         "env": "ADMITAD_FEED_URL"},
    {"key": "takeads",       "name": "TakeAds",         "env": "TAKEADS_API_KEY"},
    {"key": "travelpayouts", "name": "Travelpayouts",   "env": "TRAVELPAYOUTS_TOKEN"},
]

scheduler = AsyncIOScheduler(timezone="UTC")


def _cron() -> str:
    return os.environ.get("CRON_SCHEDULE") or settings.get_settings().get(
        "cronSchedule", "0 * * * *"
    )


def _schedule_job() -> None:
    scheduler.add_job(
        pipeline.run_pipeline, CronTrigger.from_crontab(_cron()),
        id="pipeline", replace_existing=True,
    )


def _next_run() -> str | None:
    job = scheduler.get_job("pipeline")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    _schedule_job()
    scheduler.start()
    logger.info(f"Scheduler started (cron={_cron()})", "scheduler")
    logger.info("Platform circuit breakers armed: bluesky, mastodon, x, threads, tumblr, sovrn, groq, mistral", "system")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped", "scheduler")


app = FastAPI(title="Affiliate Bot", lifespan=lifespan)


class _SnapshotMiddleware(BaseHTTPMiddleware):
    """Capture GET /api/* JSON response shapes into logs/snapshots/ when SNAPSHOT_DIR is set."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if (
            request.method == "GET"
            and path.startswith("/api/")
            and response.headers.get("content-type", "").startswith("application/json")
        ):
            import json as _json
            from starlette.responses import Response
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk
            try:
                record_response(path, _json.loads(body_bytes))
            except Exception:
                pass
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        return response


app.add_middleware(_SnapshotMiddleware)


# ── Dashboard auth middleware ────────────────────────────────────────────────
# Protects all /api/* routes with a bearer token derived from DASHBOARD_PASSWORD.
# Public routes (no auth): /, /health, /r/{id}, /oauth/*, /api/social/*/callback
_PUBLIC_PREFIXES = ("/r/", "/health", "/oauth/", "/api/social/")
_PUBLIC_EXACT    = {"/", "/health"}

class DashboardAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        password = os.environ.get("DASHBOARD_PASSWORD", "")
        # No password set → Space is in open/dev mode, allow everything
        if not password:
            return await call_next(request)

        path = request.url.path

        # Always allow: redirect links, health check, OAuth callbacks, social OAuth flows
        if path in _PUBLIC_EXACT:
            return await call_next(request)
        if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # Check Authorization header: "Bearer {DASHBOARD_PASSWORD}"
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        if token == password:
            return await call_next(request)

        # Unauthenticated API call
        if path.startswith("/api/"):
            return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)

        # Unauthenticated dashboard page — serve the HTML (login form handles it client-side)
        return await call_next(request)

app.add_middleware(DashboardAuthMiddleware)


try:
    from .social_oauth import router as social_router, _handle_oauth_callback
    app.include_router(social_router, prefix="/api")
except Exception as err:  # noqa: BLE001
    logger.warn(f"social_oauth router not mounted: {err}")
    _handle_oauth_callback = None  # type: ignore


# Mastodon redirects to /oauth/social/callback (not /api/social/callback)
@app.get("/oauth/social/callback")
async def oauth_social_callback(
    request: Request,
    platform: str = "",
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    if _handle_oauth_callback is None:
        raise HTTPException(503, "OAuth not available")
    return await _handle_oauth_callback(platform, code, state, error)


# ── Pages & health ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    if DASHBOARD.exists():
        return FileResponse(str(DASHBOARD))
    return HTMLResponse("<h1>Affiliate Bot</h1><p>Dashboard not found.</p>")


@app.get("/health")
async def health():
    slo = pipeline.calculate_slo(500)
    missing = _missing_vars()
    # Degraded if SLO < 95% or credentials missing; down if SLO < 50%
    slo_pct = slo.get("slo_pct")
    if slo_pct is not None and slo_pct < 50:
        status_str = "degraded"
    elif missing:
        status_str = "misconfigured"
    else:
        status_str = "healthy"
    return {
        "ok": status_str == "healthy",
        "status": status_str,
        "slo_pct": slo_pct,
        "error_budget_remaining_pct": slo.get("error_budget_remaining_pct"),
        "missing_vars": missing,
        "circuit_breakers": cb_statuses(),
        "pipeline_running": pipeline.STATE["running"],
        "pipeline_paused": pipeline.STATE["paused"],
        "pipeline_paused_until": pipeline.STATE.get("pausedUntil"),
    }


# ── Status & stats ──────────────────────────────────────────────────────────

def _missing_vars() -> list:
    return [v for v in REQUIRED_VARS if not os.environ.get(v)]


def _stats() -> dict:
    runs = metrics.get_recent_runs(500)
    total = len(runs)
    success = sum(1 for r in runs if r.get("success"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    posts_today = sum(
        1 for r in runs if r.get("success") and str(r.get("timestamp", "")).startswith(today)
    )
    s = settings.get_settings()
    return {
        "totalRuns": total,
        "successRate": round(success / total * 100) if total else None,
        "postsToday": posts_today,
        "maxPostsPerDay": int(s.get("postsPerDay", 1)) * 24,
    }


@app.get("/api/status")
async def status():
    s = settings.get_settings()
    cap = float(s.get("dailyCostCap", 2.0))
    last_run = pipeline.STATE["lastRun"]
    return {
        "pipeline": {
            "running": pipeline.STATE["running"],
            "paused": pipeline.STATE["paused"],
            "pausedUntil": pipeline.STATE.get("pausedUntil"),
            "schedule": _cron(),
            "nextRun": None if pipeline.STATE["paused"] else _next_run(),
            "lastRun": last_run,
        },
        "budget": {"spent": round(budget.get_daily_spend(), 4), "cap": cap},
        "stats": _stats(),
        "runs": metrics.get_recent_runs(20),
        "missingVars": _missing_vars(),
        "circuit_breakers": cb_statuses(),
        # top-level lastRun for dashboard compatibility
        "lastRun": last_run,
    }


@app.get("/api/stats")
async def stats(days: int = 7):
    runs = metrics.get_recent_runs(500)
    by_day: dict = defaultdict(lambda: {"date": "", "byNetwork": defaultdict(int)})
    for r in runs:
        if not r.get("success"):
            continue
        day = str(r.get("timestamp", ""))[:10]
        if not day:
            continue
        by_day[day]["date"] = day
        by_day[day]["byNetwork"][r.get("productSource") or "unknown"] += 1
    out = [
        {"date": d["date"], "byNetwork": dict(d["byNetwork"])}
        for d in by_day.values()
    ]
    out.sort(key=lambda x: x["date"])
    return out[-days:]


# ── Actions ─────────────────────────────────────────────────────────────────

@app.post("/api/run")
async def run():
    if pipeline.STATE["running"]:
        return {"ok": False, "error": "Pipeline already running"}
    if pipeline.STATE["paused"]:
        return {"ok": False, "error": "Pipeline is paused — click Resume first"}

    # Pre-flight: check settings-level guards before firing the background task
    s = settings.get_settings()
    cap = float(s.get("dailyCostCap", 2.0))
    if budget.get_daily_spend() >= cap:
        return {"ok": False, "error": f"Daily cost cap ${cap:.2f} reached"}
    platforms = s.get("publishPlatforms", ["bluesky"])
    if not platforms:
        return {"ok": False, "error": "No publishing platforms selected — enable at least one in Settings"}
    # Only enforce Bluesky credential check when Bluesky is actually selected
    if "bluesky" in platforms:
        if not s.get("bskyEnabled", True):
            return {"ok": False, "error": "Bluesky is disabled — re-enable it in Accounts or deselect it in Settings"}
        missing = [v for v in ["BSKY_HANDLE", "BSKY_APP_PASSWORD"] if not os.environ.get(v)]
        if missing:
            return {"ok": False, "error": f"Bluesky credentials missing: {', '.join(missing)}"}

    import asyncio
    asyncio.create_task(pipeline.run_pipeline())
    return {"ok": True}


@app.post("/api/dry-run")
async def dry_run():
    return await pipeline.dry_run()


@app.post("/api/schedule/pause")
async def pause():
    pipeline.STATE["paused"] = True
    scheduler.pause()
    return {"ok": True, "paused": True}


@app.post("/api/schedule/resume")
async def resume():
    pipeline.STATE["paused"] = False
    pipeline.STATE["pausedUntil"] = None
    scheduler.resume()
    return {"ok": True, "paused": False}


@app.get("/api/schedule/config")
async def schedule_config():
    s = settings.get_settings()
    return {
        "cron":             _cron(),
        "nextRun":          _next_run(),
        "paused":           pipeline.STATE["paused"],
        "schedulerEnabled": s.get("schedulerEnabled", True),
        "postsPerDay":      s.get("postsPerDay", 1),
        "postingHours":     s.get("postingHours", "8-22"),
    }


@app.post("/api/schedule/config")
async def save_schedule_config(request: Request):
    """Save schedule settings (postsPerDay, postingHours, schedulerEnabled)."""
    try:
        body = await request.json()
        allowed = {k: body[k] for k in ("postsPerDay", "postingHours", "schedulerEnabled") if k in body}
        if not allowed:
            return {"ok": False, "error": "No valid schedule fields provided"}
        err = _validate_settings(allowed)
        if err:
            return {"ok": False, "error": err}
        settings.save_settings(allowed)
        if "schedulerEnabled" in allowed:
            _schedule_job()
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


@app.get("/api/schedule/suggest")
async def schedule_suggest(n: int = 1):
    """Return AI-suggested posting times based on posting hours setting."""
    s = settings.get_settings()
    hours = s.get("postingHours", "8-22")
    try:
        start, end = [int(x) for x in str(hours).split("-")]
    except Exception:  # noqa: BLE001
        start, end = 8, 22
    window = (end - start) if end > start else (end + 24 - start)
    step = max(1, window // max(n, 1))
    suggested = []
    for i in range(min(n, 8)):
        h = (start + step * i) % 24
        suggested.append({"label": f"{h:02d}:00 UTC", "hour": h})
    return {
        "ok": True,
        "suggestedTimes": suggested,
        "message": f"Based on your posting window ({hours}), spread {n} post(s) evenly.",
        "basedOn": "posting-hours",
    }


# ── Logs & debug ────────────────────────────────────────────────────────────

@app.get("/api/metrics")
async def api_metrics():
    """Four Golden Signals: Latency, Traffic, Errors, Saturation."""
    return {
        "golden_signals": golden_signals(),
        "circuit_breakers": cb_statuses(),
        "slo": pipeline.calculate_slo(500),
    }


@app.get("/api/slo")
async def api_slo():
    """SLO compliance and error budget status."""
    slo = pipeline.calculate_slo(500)
    budget_remaining = slo.get("error_budget_remaining_pct", 100)
    if budget_remaining <= 0:
        slo["circuit_breaker_active"] = True
        slo["action"] = "HALT_FEATURE_DEPLOYS — redirect all capacity to stability"
        logger.warn("Error budget exhausted — circuit breaker active, feature deploys halted", "system")
    elif budget_remaining <= 20:
        slo["circuit_breaker_active"] = False
        slo["action"] = "WARNING — error budget below 20%, monitor closely"
    else:
        slo["circuit_breaker_active"] = False
        slo["action"] = "nominal"
    return slo


@app.post("/api/circuit-breakers/reset-all")
async def reset_all_circuit_breakers():
    cb_reset_all()
    logger.info("All circuit breakers manually reset", "system")
    return {"ok": True}


@app.post("/api/circuit-breakers/all/reset")
async def reset_all_circuit_breakers_alias():
    """Alias for /reset-all — tolerates the intuitive /all/reset path."""
    cb_reset_all()
    logger.info("All circuit breakers manually reset", "system")
    return {"ok": True}


@app.post("/api/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str):
    ok = reset_breaker(name)
    if not ok:
        raise HTTPException(404, f"No circuit breaker named '{name}'")
    logger.info(f"Circuit breaker '{name}' manually reset", "system")
    return {"ok": True, "name": name}


@app.get("/api/logs")
async def logs(n: int = 200, level: str = "", component: str = ""):
    entries = logger.get_recent_logs(n)
    if level:
        entries = [e for e in entries if e.get("level") == level.lower()]
    if component:
        entries = [e for e in entries if e.get("component") == component.lower()]
    return entries


@app.post("/api/logs/clear")
async def clear_logs():
    n = logger.clear_logs()
    logger.info("Logs cleared by user", "system")
    return {"ok": True, "cleared": n}


@app.get("/api/logs/summary")
async def logs_summary():
    return logger.error_summary()


@app.post("/api/logs/analyze")
async def analyze_logs_ai():
    from .ai.log_analyzer import analyze_logs
    entries   = logger.get_recent_logs(200)
    last_run  = pipeline.STATE.get("lastRun")
    result    = await analyze_logs(entries, last_run)
    logger.info(f"AI log analysis complete — status: {result.get('status')} via {result.get('provider')}", "ai")
    return result


def metrics_logs(n: int) -> list:
    return logger.get_recent_logs(n)


@app.get("/api/debug")
async def debug():
    last = pipeline.STATE["lastRun"]
    recent_errors = [
        {"ts": r.get("timestamp"), "error": r.get("error")}
        for r in metrics.get_recent_runs(50) if r.get("error")
    ][-10:]
    return {
        "env": {k: bool(os.environ.get(k)) for k in ENV_KEYS},
        "networks": [
            {"key": n["key"], "enabled": bool(os.environ.get(n["env"]))}
            for n in NETWORKS
        ],
        "spaceHost": settings.get_space_host(),
        "lastRun": last,
        "recentErrors": recent_errors,
    }


@app.get("/api/env")
@app.get("/api/env-status")
async def env_status():
    return {k: bool(os.environ.get(k)) for k in ENV_KEYS}


# ── Settings ────────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings_route():
    return settings.get_settings()


_SETTINGS_VALIDATORS: dict[str, tuple] = {
    # key: (type_or_types, min_val, max_val)  — None means no bound
    "maxPostLength":  ((int, float), 1,    5000),
    "dailyCostCap":   ((int, float), 0.01, 1000),
    "alertThreshold": ((int, float), 0.01, 1000),
    "postsPerDay":    ((int, float), 1,    100),
    "rateLimitWaitMs":((int, float), 1000, 86_400_000),
    "seoMinScore":    ((int, float), 0,    100),
}


def _validate_settings(body: dict) -> str | None:
    """Return an error string if any field fails validation, else None."""
    for key, (types, lo, hi) in _SETTINGS_VALIDATORS.items():
        if key not in body:
            continue
        v = body[key]
        if not isinstance(v, types):
            return f"'{key}' must be a number (got {type(v).__name__})"
        if lo is not None and v < lo:
            return f"'{key}' must be >= {lo} (got {v})"
        if hi is not None and v > hi:
            return f"'{key}' must be <= {hi} (got {v})"
    if "postingHours" in body:
        ph = str(body["postingHours"])
        import re as _re
        m = _re.fullmatch(r"(\d{1,2})-(\d{1,2})", ph)
        if not m or not (0 <= int(m.group(1)) <= 23) or not (0 <= int(m.group(2)) <= 23):
            return f"'postingHours' must be HH-HH with hours 0-23 (got '{ph}')"
    return None


@app.post("/api/settings")
async def post_settings(request: Request):
    try:
        body = await request.json()
        err = _validate_settings(body)
        if err:
            return {"ok": False, "error": err}
        saved = settings.save_settings(body)
        if "cronSchedule" in body:
            _schedule_job()
        return {"ok": True, "settings": saved}
    except Exception as err:  # noqa: BLE001
        return {"ok": False, "error": str(err)}


# ── Accounts & networks ─────────────────────────────────────────────────────

@app.get("/api/accounts")
async def accounts():
    import json as _json
    from pathlib import Path as _Path
    from .bluesky_client import _bsky_credentials
    _bh, _bp = _bsky_credentials()
    has_creds = bool(_bh and _bp)
    bsky_enabled = settings.get_settings().get("bskyEnabled", True)
    connected = has_creds and bsky_enabled

    # Load social platform connections
    data_dir = _Path(os.environ.get("DATA_DIR", "/data"))
    try:
        social_raw = _json.loads((data_dir / "social-connections.json").read_text())
    except Exception:
        social_raw = {}

    social = {}
    for key in ("mastodon", "threads", "tumblr", "x", "facebook", "instagram"):
        c = social_raw.get(key, {})
        entry: dict = {
            "connected": bool(c.get("connected")),
            "handle":    c.get("handle", ""),
            "instance":  c.get("instance", ""),
        }
        # Return credential fields so the frontend can repopulate form inputs.
        # Sensitive values are masked — presence is confirmed without exposing secrets.
        if key == "x":
            for field in ("consumer_key", "consumer_secret", "access_token", "access_secret"):
                entry[field] = "••••" if c.get(field) else ""
        elif key == "facebook":
            entry["page_access_token"] = "••••" if c.get("page_access_token") else ""
            entry["page_id"] = c.get("page_id", "")
        elif key == "instagram":
            entry["access_token"] = "••••" if c.get("access_token") else ""
            entry["ig_user_id"] = c.get("ig_user_id", "")
        social[key] = entry

    return {
        "bluesky": {
            "connected": connected,
            "handle": os.environ.get("BSKY_HANDLE", "") if connected else "",
            "method": "app-password",
            "hasCreds": has_creds,
        },
        "social": social,
    }


_last_bsky_test: float = 0.0
_TEST_COOLDOWN  = 60  # seconds between Test button calls
_test_lock      = asyncio.Lock()  # prevent concurrent test calls racing the cooldown

@app.post("/api/accounts/bluesky/test")
async def test_bluesky():
    """Test Bluesky credentials. Enforces 60s cooldown and respects persistent rate-limit guard."""
    import httpx as _httpx
    from datetime import datetime, timezone
    from .bluesky_client import get_ratelimit_reset, _save_ratelimit

    global _last_bsky_test

    async with _test_lock:
        # Server-side cooldown — prevents rapid repeated clicks and races
        since = time.time() - _last_bsky_test
        if since < _TEST_COOLDOWN:
            wait = int(_TEST_COOLDOWN - since)
            return {"ok": False, "error": f"Please wait {wait}s before testing again."}

    # Persistent rate-limit guard — no login if we know we're blocked
    rl_until = get_ratelimit_reset()
    if rl_until:
        reset_dt = datetime.fromtimestamp(rl_until, tz=timezone.utc)
        wait_s = int(rl_until - time.time())
        return {
            "ok": False,
            "rateLimited": True,
            "error": f"Bluesky rate limit active until {reset_dt.strftime('%H:%M:%S')} UTC ({wait_s}s). Login blocked automatically — no need to retry.",
        }

    from .bluesky_client import _bsky_credentials
    handle, password = _bsky_credentials()
    if not handle or not password:
        return {"ok": False, "error": "Bluesky credentials not set — enter them in Accounts or set BSKY_HANDLE / BSKY_APP_PASSWORD in Space Secrets"}

    _last_bsky_test = time.time()
    try:
        timeout = _httpx.Timeout(connect=10, read=20, write=20, pool=5)
        async with _httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "https://bsky.social/xrpc/com.atproto.server.createSession",
                json={"identifier": handle, "password": password},
            )
        if r.status_code == 200:
            did = r.json().get("did", "")
            return {"ok": True, "handle": handle, "did": did}
        if r.status_code == 429:
            reset_ts_hdr = r.headers.get("RateLimit-Reset") or r.headers.get("X-RateLimit-Reset")
            retry_after  = int(r.headers.get("Retry-After", 300))
            reset_epoch  = float(reset_ts_hdr) if reset_ts_hdr else time.time() + retry_after
            _save_ratelimit(reset_epoch)  # persist so restarts respect it
            reset_dt = datetime.fromtimestamp(reset_epoch, tz=timezone.utc)
            return {
                "ok": False,
                "rateLimited": True,
                "error": f"Bluesky rate-limited (429). Resets at {reset_dt.strftime('%H:%M:%S')} UTC. Login blocked automatically — do not retry.",
            }
        body = r.text[:200]
        return {"ok": False, "error": f"HTTP {r.status_code}: {body}"}
    except Exception as err:
        return {"ok": False, "error": str(err)}


@app.post("/api/accounts/bluesky/disconnect")
async def disconnect_bluesky():
    try:
        from .bluesky_client import clear_session as _bsky_clear
        _bsky_clear()
    except Exception:
        pass
    settings.save_settings({"bskyEnabled": False})
    return {"ok": True}


@app.post("/api/accounts/bluesky/clear-session")
async def clear_bluesky_session():
    """Force a fresh login on next pipeline run (clears cached JWT)."""
    from .bluesky_client import clear_session as _bsky_clear
    _bsky_clear()
    return {"ok": True, "message": "Bluesky session cleared — next run will log in fresh"}


@app.post("/api/accounts/bluesky/enable")
async def enable_bluesky():
    settings.save_settings({"bskyEnabled": True})
    return {"ok": True}


# ── Social credential save endpoints ─────────────────────────────────────────
# These persist credentials to social-connections.json so the pipeline can
# post without requiring HuggingFace Space Secrets for every platform.

def _social_connections_file() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data")) / "social-connections.json"


def _load_social_connections() -> dict:
    f = _social_connections_file()
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        return {}


def _save_social_connections(data: dict) -> None:
    f = _social_connections_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


@app.post("/api/social/bluesky/credentials")
async def save_bluesky_credentials(request: Request):
    body = await request.json()
    handle   = (body.get("handle") or body.get("password") or "").strip()
    password = (body.get("password") or "").strip()
    # handle may be passed as first positional field; check both keys
    handle   = (body.get("handle") or "").strip()
    password = (body.get("password") or "").strip()
    if not handle or not password:
        return {"ok": False, "error": "handle and password are required"}
    conns = _load_social_connections()
    conns["bluesky"] = {"handle": handle, "password": password, "connected": True}
    _save_social_connections(conns)
    # Also inject into current process env so pipeline picks them up immediately
    os.environ["BSKY_HANDLE"] = handle
    os.environ["BSKY_APP_PASSWORD"] = password
    settings.save_settings({"bskyEnabled": True})
    return {"ok": True}


@app.post("/api/social/x/credentials")
async def save_x_credentials(request: Request):
    body = await request.json()
    handle          = (body.get("handle") or "").strip().lstrip("@")
    consumer_key    = (body.get("consumer_key") or "").strip()
    consumer_secret = (body.get("consumer_secret") or "").strip()
    access_token    = (body.get("access_token") or "").strip()
    access_secret   = (body.get("access_secret") or "").strip()
    if not handle:
        return {"ok": False, "error": "handle is required"}
    conns = _load_social_connections()
    existing = conns.get("x", {})
    conns["x"] = {
        "handle":          handle,
        "consumer_key":    consumer_key    or existing.get("consumer_key", ""),
        "consumer_secret": consumer_secret or existing.get("consumer_secret", ""),
        "access_token":    access_token    or existing.get("access_token", ""),
        "access_secret":   access_secret   or existing.get("access_secret", ""),
        "connected":       True,
    }
    _save_social_connections(conns)
    return {"ok": True}


@app.post("/api/social/facebook/credentials")
async def save_facebook_credentials(request: Request):
    body = await request.json()
    handle            = (body.get("handle") or "").strip()
    page_id           = (body.get("page_id") or handle).strip()
    page_access_token = (body.get("page_access_token") or "").strip()
    if not handle:
        return {"ok": False, "error": "handle is required"}
    conns = _load_social_connections()
    existing = conns.get("facebook", {})
    conns["facebook"] = {
        "handle":            handle,
        "page_id":           page_id           or existing.get("page_id", ""),
        "page_access_token": page_access_token or existing.get("page_access_token", ""),
        "connected":         bool(page_id and (page_access_token or existing.get("page_access_token"))),
    }
    _save_social_connections(conns)
    return {"ok": True}


@app.post("/api/social/instagram/credentials")
async def save_instagram_credentials(request: Request):
    body = await request.json()
    handle       = (body.get("handle") or "").strip().lstrip("@")
    ig_user_id   = (body.get("ig_user_id") or handle).strip()
    access_token = (body.get("access_token") or "").strip()
    if not handle:
        return {"ok": False, "error": "handle is required"}
    conns = _load_social_connections()
    existing = conns.get("instagram", {})
    conns["instagram"] = {
        "handle":       handle,
        "ig_user_id":   ig_user_id   or existing.get("ig_user_id", ""),
        "access_token": access_token or existing.get("access_token", ""),
        "connected":    bool(ig_user_id and (access_token or existing.get("access_token"))),
    }
    _save_social_connections(conns)
    return {"ok": True}


@app.get("/api/networks")
async def networks():
    return [
        {"key": n["key"], "name": n["name"], "enabled": bool(os.environ.get(n["env"]))}
        for n in NETWORKS
    ]


@app.get("/api/network/test")
@app.post("/api/network/test")
async def network_test(request: Request, network: str = ""):
    # Accept network from query param (GET) or JSON body (POST)
    if request.method == "POST":
        try:
            body = await request.json()
            network = body.get("network", network)
        except Exception:  # noqa: BLE001
            pass
    found = next((n for n in NETWORKS if n["key"] == network), None)
    if not found:
        return {"ok": False, "error": "Unknown network"}
    enabled = bool(os.environ.get(found["env"]))
    return {"ok": enabled, "network": network, "enabled": enabled}


# ── History & clicks ────────────────────────────────────────────────────────

@app.get("/api/history")
async def history(n: int = 100):
    return metrics.get_recent_runs(n)


@app.get("/api/history.csv", response_class=PlainTextResponse)
async def history_csv(n: int = 500):
    runs = metrics.get_recent_runs(n)
    buf = io.StringIO()
    cols = ["timestamp", "success", "product", "productSource", "captionChars",
            "clicks", "postUri", "error"]
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for r in runs:
        writer.writerow(r)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


@app.get("/api/clicks")
async def clicks(days: int = 30):
    runs = metrics.get_recent_runs(500)
    by_day: dict = defaultdict(lambda: {"posts": 0, "clicks": 0})
    for r in runs:
        day = str(r.get("timestamp", ""))[:10]
        if not day:
            continue
        if r.get("success"):
            by_day[day]["posts"] += 1
        by_day[day]["clicks"] += int(r.get("clicks", 0))
    daily = []
    for day in sorted(by_day):
        d = by_day[day]
        ctr = round(d["clicks"] / d["posts"], 2) if d["posts"] else 0
        daily.append({"date": day, "posts": d["posts"], "clicks": d["clicks"], "ctr": ctr})
    daily = daily[-days:]
    return {"daily": daily, "total": metrics.get_total_clicks()}


# ── Dedup ───────────────────────────────────────────────────────────────────

@app.get("/api/dedup/stats")
async def dedup_stats():
    return {**metrics.get_dedup_status(), "bySource": metrics.get_dedup_by_source()}


@app.post("/api/dedup/reset")
async def dedup_reset():
    cleared = metrics.clear_posted_store()
    return {"ok": True, "cleared": cleared}


@app.post("/api/slo/reset")
async def slo_reset():
    """Purge run history to reset SLO baseline after fixing a systematic failure."""
    cleared = metrics.clear_run_history()
    logger.info(f"SLO run history cleared ({cleared} records) — baseline reset", "system")
    return {"ok": True, "cleared": cleared}


# ── Insights ────────────────────────────────────────────────────────────────

@app.get("/api/finops")
async def finops():
    """FinOps: daily spend, 30-day forecast, cap status."""
    s   = settings.get_settings()
    cap = float(s.get("dailyCostCap", 2.0))
    return {
        "today_usd":  round(budget.get_daily_spend(), 6),
        "cap_usd":    cap,
        "forecast":   budget.get_monthly_forecast(cap),
    }


@app.get("/api/platform-rules")
async def platform_rules():
    """Return the anti-ban posting protocol for all platforms."""
    from .utils.platform_guardian import all_rules_summary, check_allowed
    runs = metrics.get_recent_runs(500)
    rules = all_rules_summary()
    for r in rules:
        allowed, reason = check_allowed(r["platform"], runs)
        r["currentlyAllowed"] = allowed
        r["guardianStatus"] = reason
    return {"ok": True, "rules": rules}


@app.get("/api/insights")
async def insights():
    return {
        "networkHealth": metrics.get_network_health(100),
        "dedup": metrics.get_dedup_status(),
        "totalClicks": metrics.get_total_clicks(),
    }


# ── Circuit breaker management ───────────────────────────────────────────────

@app.post("/api/circuit-breaker/reset")
async def circuit_breaker_reset(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if name == "all":
        cb_reset_all()
        return {"ok": True, "reset": "all"}
    if name:
        ok = reset_breaker(name)
        return {"ok": ok, "reset": name if ok else None,
                "error": None if ok else f"Unknown circuit breaker: {name}"}
    cb_reset_all()
    return {"ok": True, "reset": "all"}


# ── Diagnose ────────────────────────────────────────────────────────────────

@app.get("/api/diagnose")
async def diagnose():
    """Full pre-flight diagnosis: checks every blocker that prevents a successful post."""
    s = settings.get_settings()
    cap = float(s.get("dailyCostCap", 2.0))
    spend = round(budget.get_daily_spend(), 4)
    bsky_enabled = s.get("bskyEnabled", True)
    sovrn_key = bool(os.environ.get("SOVRN_API_KEY"))

    checks = [
        {
            "name": "Bluesky handle",
            "ok": bool(os.environ.get("BSKY_HANDLE")),
            "detail": os.environ.get("BSKY_HANDLE", "NOT SET — add BSKY_HANDLE to Space Secrets"),
        },
        {
            "name": "Bluesky app password",
            "ok": bool(os.environ.get("BSKY_APP_PASSWORD")),
            "detail": "set" if os.environ.get("BSKY_APP_PASSWORD") else "NOT SET — add BSKY_APP_PASSWORD to Space Secrets",
        },
        {
            "name": "Bluesky enabled",
            "ok": bsky_enabled,
            "detail": "enabled" if bsky_enabled else "DISABLED — click Re-enable in Accounts tab",
        },
        {
            "name": "Pipeline not paused",
            "ok": not pipeline.STATE["paused"],
            "detail": "not paused" if not pipeline.STATE["paused"] else "PAUSED — click Resume",
        },
        {
            "name": "Daily cost cap",
            "ok": spend < cap,
            "detail": f"${spend:.4f} spent of ${cap:.2f} cap",
        },
        {
            "name": "Product networks",
            "ok": any(bool(os.environ.get(n["env"])) for n in NETWORKS),
            "detail": ", ".join(
                n["name"] for n in NETWORKS if os.environ.get(n["env"])
            ) or "NONE configured — add SOVRN_API_KEY, TAKEADS_API_KEY, ADMITAD_FEED_URL, or TRAVELPAYOUTS_TOKEN",
        },
        {
            "name": "Click tracking (SPACE_HOST)",
            "ok": bool(settings.get_space_host()),
            "detail": settings.get_space_host() or "NOT SET — clicks won't be tracked. Add SPACE_HOST to Space Secrets (e.g. your-space-name.hf.space)",
        },
    ]

    last_run = pipeline.STATE["lastRun"]
    last_error = pipeline.STATE["lastError"]
    cb = cb_statuses()

    all_ok = all(c["ok"] for c in checks)
    return {
        "ready": all_ok,
        "checks": checks,
        "lastRun": last_run,
        "lastError": last_error,
        "circuitBreakers": cb,
        "pipelineRunning": pipeline.STATE["running"],
    }


# ── AI generation ───────────────────────────────────────────────────────────

@app.post("/api/ai/generate")
async def ai_generate(request: Request):
    body = await request.json()
    product = {
        "name": body.get("productName", "this product"),
        "category": body.get("category", "general"),
        "description": body.get("description", ""),
    }
    text = await ai_text.generate_post_text(product, [])
    return {"text": text, "seoScore": None, "seoGrade": None}


# ── Redirect tracking ───────────────────────────────────────────────────────

@app.get("/r/{tracking_id}")
async def redirect(tracking_id: str):
    metrics.record_click(tracking_id)
    target = pipeline.resolve_redirect(tracking_id)
    if target:
        return RedirectResponse(target, status_code=302)
    return RedirectResponse("/", status_code=302)
