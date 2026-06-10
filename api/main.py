"""FastAPI backend for the affiliate-posting bot (HuggingFace Spaces, port 7860)."""

import csv
import io
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
)

from . import pipeline
from .ai import text as ai_text
from .utils import budget, logger, metrics, settings
from .utils.circuit_breaker import all_statuses as cb_statuses, reset_breaker, reset_all as cb_reset_all
from .utils.telemetry import golden_signals

DASHBOARD = Path(__file__).resolve().parent.parent / "src" / "dashboard.html"

# Env vars surfaced in /api/debug and used to compute setup warnings.
ENV_KEYS = [
    "BSKY_HANDLE", "BSKY_APP_PASSWORD", "SOVRN_API_KEY", "GROQ_API_KEY",
    "MISTRAL_API_KEY", "ADMITAD_CLIENT_ID", "TAKEADS_API_KEY",
    "TRAVELPAYOUTS_TOKEN", "SPACE_HOST", "CRON_SCHEDULE",
]
REQUIRED_VARS = ["BSKY_HANDLE", "BSKY_APP_PASSWORD"]

NETWORKS = [
    {"key": "sovrn", "name": "SOVRN Commerce", "env": "SOVRN_API_KEY"},
    {"key": "admitad", "name": "Admitad", "env": "ADMITAD_CLIENT_ID"},
    {"key": "takeads", "name": "TakeAds", "env": "TAKEADS_API_KEY"},
    {"key": "travelpayouts", "name": "Travelpayouts", "env": "TRAVELPAYOUTS_TOKEN"},
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
    logger.info(f"Scheduler started (cron={_cron()})")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Affiliate Bot", lifespan=lifespan)

try:
    from .social_oauth import router as social_router
    app.include_router(social_router, prefix="/api")
except Exception as err:  # noqa: BLE001
    logger.warn(f"social_oauth router not mounted: {err}")


# ── Pages & health ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    if DASHBOARD.exists():
        return FileResponse(str(DASHBOARD))
    return HTMLResponse("<h1>Affiliate Bot</h1><p>Dashboard not found.</p>")


@app.get("/health")
async def health():
    slo = pipeline.calculate_slo(500)
    missing = _missing_vars()
    bsky_ok = not missing
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
    if not s.get("bskyEnabled", True):
        return {"ok": False, "error": "Bluesky is disabled — re-enable it in Accounts"}
    missing = _missing_vars()
    if missing:
        return {"ok": False, "error": f"Missing credentials: {', '.join(missing)}"}

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
    scheduler.resume()
    return {"ok": True, "paused": False}


@app.get("/api/schedule/config")
async def schedule_config():
    return {"cron": _cron(), "nextRun": _next_run(), "paused": pipeline.STATE["paused"]}


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
    # Circuit breaker: if error budget is 0%, signal halt
    if slo.get("error_budget_remaining_pct", 100) <= 0:
        slo["circuit_breaker_active"] = True
        slo["action"] = "HALT_FEATURE_DEPLOYS — redirect all capacity to stability"
    else:
        slo["circuit_breaker_active"] = False
    return slo


@app.get("/api/logs")
async def logs(n: int = 100):
    return metrics_logs(n)


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
async def env_status():
    return {k: bool(os.environ.get(k)) for k in ENV_KEYS}


# ── Settings ────────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings_route():
    return settings.get_settings()


@app.post("/api/settings")
async def post_settings(request: Request):
    try:
        body = await request.json()
        saved = settings.save_settings(body)
        if "cronSchedule" in body:
            _schedule_job()
        return {"ok": True, "settings": saved}
    except Exception as err:  # noqa: BLE001
        return {"ok": False, "error": str(err)}


# ── Accounts & networks ─────────────────────────────────────────────────────

@app.get("/api/accounts")
async def accounts():
    has_creds = bool(os.environ.get("BSKY_HANDLE") and os.environ.get("BSKY_APP_PASSWORD"))
    bsky_enabled = settings.get_settings().get("bskyEnabled", True)
    connected = has_creds and bsky_enabled
    return {
        "bluesky": {
            "connected": connected,
            "handle": os.environ.get("BSKY_HANDLE", "") if connected else "",
            "method": "app-password",
            "hasCreds": has_creds,
        }
    }


@app.post("/api/accounts/bluesky/test")
async def test_bluesky():
    """Test Bluesky credentials by attempting a real login."""
    import httpx as _httpx
    from datetime import datetime, timezone
    handle   = (os.environ.get("BSKY_HANDLE",        "") or "").strip()
    password = (os.environ.get("BSKY_APP_PASSWORD", "") or "").strip()
    if not handle or not password:
        missing = []
        if not handle:   missing.append("BSKY_HANDLE")
        if not password: missing.append("BSKY_APP_PASSWORD")
        return {"ok": False, "error": f"Missing secrets: {', '.join(missing)}"}
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
            reset_ts = r.headers.get("RateLimit-Reset") or r.headers.get("X-RateLimit-Reset")
            retry_after = r.headers.get("Retry-After")
            reset_info = ""
            if reset_ts:
                try:
                    reset_dt = datetime.fromtimestamp(int(reset_ts), tz=timezone.utc)
                    reset_info = f" Resets at {reset_dt.strftime('%H:%M:%S')} UTC."
                except Exception:
                    pass
            elif retry_after:
                reset_info = f" Retry after {retry_after}s."
            return {
                "ok": False,
                "rateLimited": True,
                "error": f"Bluesky is rate-limiting login attempts (429).{reset_info} Wait a few minutes and try again — do not keep clicking Test.",
            }
        body = r.text[:200]
        return {"ok": False, "error": f"HTTP {r.status_code}: {body}"}
    except Exception as err:
        return {"ok": False, "error": str(err)}


@app.post("/api/accounts/bluesky/disconnect")
async def disconnect_bluesky():
    settings.save_settings({"bskyEnabled": False})
    return {"ok": True}


@app.post("/api/accounts/bluesky/enable")
async def enable_bluesky():
    settings.save_settings({"bskyEnabled": True})
    return {"ok": True}


@app.get("/api/networks")
async def networks():
    return [
        {"key": n["key"], "name": n["name"], "enabled": bool(os.environ.get(n["env"]))}
        for n in NETWORKS
    ]


@app.get("/api/network/test")
async def network_test(network: str = ""):
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
    missing = _missing_vars()
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
            "name": "SOVRN product network",
            "ok": sovrn_key,
            "detail": "SOVRN_API_KEY set" if sovrn_key else "NOT SET — no product source available (add SOVRN_API_KEY to Space Secrets)",
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
