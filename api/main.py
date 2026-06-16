"""FastAPI backend for the affiliate-posting bot (HuggingFace Spaces, port 7860)."""

import asyncio
import csv
import io
import json
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
from .utils.retry_queue import queue_depth as _retry_queue_depth
from .utils.snapshot import record_response
from .utils.circuit_breaker import all_statuses as cb_statuses, reset_breaker, reset_all as cb_reset_all
from .utils.telemetry import golden_signals
from .utils.prometheus import build_prometheus_output
from .utils.platform_queue import get_enabled_platforms

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
    scheduler.add_job(
        pipeline.retry_failed_posts, CronTrigger.from_crontab("*/15 * * * *"),
        id="retry_queue", replace_existing=True,
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
        "retry_queue_depth": _retry_queue_depth(),
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


@app.post("/api/preview")
async def preview_post(body: dict):
    """Dry-run: generate caption for a product without posting."""
    from .ai.text import generate_platform_caption
    from .utils.category_detector import ensure_category
    from .utils.trend_injector import get_trends_for

    product = {
        "name": body.get("name", "Sample Product"),
        "category": body.get("category", "General"),
        "description": body.get("description", ""),
        "price": body.get("price"),
        "url": body.get("url", ""),
    }
    product = ensure_category(product)
    platform = body.get("platform", "bluesky")
    trends = get_trends_for(product.get("category", "General"), n=3)
    caption = await generate_platform_caption(product, trends=trends, platform=platform)
    return {
        "caption": caption,
        "platform": platform,
        "product_name": product["name"],
        "category": product.get("category", "General"),
        "char_count": len(caption),
        "dry_run": True,
    }


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
    # Compute next 5 scheduled run times for the dashboard preview widget
    cron_exprs: list[str] = []
    try:
        from apscheduler.triggers.cron import CronTrigger as _CT
        trigger = _CT.from_crontab(_cron())
        from datetime import timedelta
        nxt = datetime.now(timezone.utc)
        for _ in range(5):
            fire = trigger.get_next_fire_time(nxt, nxt)
            if fire is None:
                break
            cron_exprs.append(fire.strftime("%Y-%m-%dT%H:%M:%SZ"))
            nxt = fire + timedelta(seconds=1)
    except Exception:  # noqa: BLE001
        pass
    return {
        "cron":             _cron(),
        "nextRun":          _next_run(),
        "paused":           pipeline.STATE["paused"],
        "schedulerEnabled": s.get("schedulerEnabled", True),
        "postsPerDay":      s.get("postsPerDay", 1),
        "postingHours":     s.get("postingHours", "8-22"),
        "cronExpressions":  cron_exprs,
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
    # Build hourly engagement heatmap from run history (successful posts by hour)
    runs = metrics.get_recent_runs(500)
    hour_scores: dict[int, list[int]] = {h: [] for h in range(24)}
    engagement_data = False
    for r in runs:
        if not r.get("success"):
            continue
        ts = r.get("timestamp", "")
        try:
            hour = int(str(ts)[11:13]) if len(str(ts)) >= 13 else -1
            if 0 <= hour <= 23:
                # Score = 1 base + click bonus
                score = 1 + int(r.get("clicks", 0))
                hour_scores[hour].append(score)
                engagement_data = True
        except Exception:  # noqa: BLE001
            pass
    hourly_data = [
        {"hour": h, "avgScore": round(sum(v) / len(v), 2) if v else 0, "count": len(v)}
        for h, v in sorted(hour_scores.items())
        if h >= start and h <= end  # only show hours in posting window
    ]

    return {
        "ok": True,
        "suggestedTimes": suggested,
        "hourlyData": hourly_data,
        "message": f"Based on your posting window ({hours}), spread {n} post(s) evenly.",
        "basedOn": "engagement-analysis" if engagement_data else "posting-hours",
    }


# ── Smart schedule ───────────────────────────────────────────────────────────

@app.get("/api/schedule/next")
async def schedule_next(tz_offset: int = 0):
    runs = metrics.get_recent_runs(500)
    from .utils.smart_schedule import next_fire_time
    return next_fire_time(runs, tz_offset_hours=tz_offset)


@app.get("/api/schedule/optimal")
async def schedule_optimal():
    """Return peak engagement hours and optimal cron derived from run history."""
    from .utils.smart_schedule import schedule_summary
    runs = metrics.get_recent_runs(500)
    return schedule_summary(runs)


@app.get("/api/ctr-stats")
async def ctr_stats():
    """Return CTR feedback stats: top products, per-source CTR, overall CTR."""
    from .utils.ctr_feedback import ctr_summary
    runs = metrics.get_recent_runs(500)
    return ctr_summary(runs)


@app.get("/api/hashtags")
async def api_hashtags(category: str = "General", platform: str = "instagram", n: int = 8):
    """Return optimized hashtags for a product category and platform."""
    from .utils.hashtag_optimizer import hashtags_for
    runs = metrics.get_recent_runs(200)
    tags = hashtags_for(category, platform=platform, runs=runs, n=n)
    return {"category": category, "platform": platform, "hashtags": tags}


@app.get("/api/trends")
async def get_trends(category: str = "General", n: int = 3):
    from .utils.trend_injector import get_trends_for
    return {"category": category, "trends": get_trends_for(category, n=n)}


# ── Logs & debug ────────────────────────────────────────────────────────────

@app.get("/api/metrics")
async def api_metrics():
    """Four Golden Signals: Latency, Traffic, Errors, Saturation."""
    return {
        "golden_signals": golden_signals(),
        "circuit_breakers": cb_statuses(),
        "slo": pipeline.calculate_slo(500),
    }


@app.get("/metrics", response_class=PlainTextResponse)
@app.get("/api/metrics-prom", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus text-format scrape endpoint for Grafana.

    Add as a scrape target in prometheus.yml:
      - job_name: affiliate-bot
        static_configs:
          - targets: ['your-space.hf.space']
        metrics_path: /metrics
    """
    return PlainTextResponse(build_prometheus_output(), media_type="text/plain; version=0.0.4")


@app.get("/api/architecture")
async def architecture():
    """System architecture overview — components, data flows, and dependencies."""
    return {
        "system": "Auto-Affiliate Bot",
        "description": "Scheduled pipeline that fetches affiliate products, generates AI captions, and posts to social platforms.",
        "components": {
            "scheduler": {
                "type": "APScheduler (AsyncIO)",
                "role": "Triggers pipeline on cron schedule",
                "config_key": "cronSchedule",
                "default": "0 * * * *",
            },
            "pipeline": {
                "type": "async Python",
                "phases": ["product_fetch", "dedup_check", "caption_gen", "image_fetch", "tracking_url", "multi_platform_post"],
                "circuit_breakers": ["bluesky", "groq", "mistral", "sovrn"],
                "timeout_s": 300,
            },
            "affiliate_feeds": {
                "priority_order": ["SOVRN", "TakeAds", "Admitad", "Travelpayouts"],
                "env_keys": ["SOVRN_API_KEY", "TAKEADS_API_KEY", "ADMITAD_FEED_URL", "TRAVELPAYOUTS_TOKEN"],
            },
            "ai_caption": {
                "providers": ["Groq (llama-3.3-70b)", "Mistral (mistral-small)"],
                "fallback": "template",
                "language_guard": "English-only enforcement",
            },
            "publishing": {
                "platforms": ["bluesky", "mastodon", "x", "facebook", "instagram", "threads", "tumblr"],
                "auth_types": {"credentials": ["bluesky", "x", "facebook", "instagram"], "oauth2": ["mastodon", "threads", "tumblr"]},
                "circuit_breakers": ["bluesky", "mastodon", "x", "facebook", "instagram", "threads", "tumblr"],
            },
            "observability": {
                "metrics": ["/api/metrics (JSON)", "/metrics (Prometheus)", "/api/slo", "/api/finops"],
                "logs": "/api/logs",
                "alerts": "SLO error budget < 20% → warning; < 0% → circuit breaker",
                "grafana_scrape": "/metrics or /api/metrics-prom",
            },
            "data_persistence": {
                "files": {
                    "settings.json": "user configuration",
                    "runs.json": "pipeline run history (last 500)",
                    "bsky-session.json": "Bluesky session cache",
                    "social-connections.json": "platform credentials",
                    "budget.json": "daily AI cost tracker",
                    "dedup-store.json": "product dedup cache (24h TTL)",
                },
                "data_dir": "/data (configurable via DATA_DIR env var)",
            },
        },
        "data_flows": [
            "Scheduler → pipeline.run_pipeline()",
            "pipeline → _get_product() [SOVRN→TakeAds→Admitad→Travelpayouts]",
            "pipeline → ai_text.generate_post_text() [Groq→Mistral→template]",
            "pipeline → _find_image() [imageUrl→Amazon og:image scrape]",
            "pipeline → _tracking_url() → /r/{id} redirect",
            "pipeline → post_to_bluesky() / post_to_platform() [per enabled platform]",
            "Click → GET /r/{id} → 302 → affiliate deeplink + metrics.record_click()",
        ],
        "sdlc_integrations": {
            "prometheus": "GET /metrics — scrape with Prometheus, visualise in Grafana",
            "grafana_dashboard": "GET /api/grafana-dashboard — import JSON into Grafana",
            "healthcheck": "GET /health — Docker/Kubernetes liveness probe",
            "openapi": "GET /docs — Swagger UI, GET /openapi.json — OpenAPI 3.0 spec",
        },
    }


@app.get("/api/grafana-dashboard")
async def grafana_dashboard():
    """Return a ready-to-import Grafana dashboard JSON targeting /metrics."""
    space_host = settings.get_settings().get("spaceHost") or os.environ.get("SPACE_HOST", "localhost:7860")
    return {
        "title": "Auto-Affiliate Bot",
        "uid": "affiliate-bot-v1",
        "schemaVersion": 38,
        "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"},
        "__inputs": [{"name": "DS_PROMETHEUS", "label": "Prometheus", "type": "datasource", "pluginId": "prometheus"}],
        "templating": {"list": []},
        "panels": [
            {
                "id": 1, "title": "SLO Compliance %", "type": "stat", "gridPos": {"x": 0, "y": 0, "w": 4, "h": 4},
                "targets": [{"expr": "affiliate_slo_pct", "legendFormat": "SLO %"}],
                "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background"},
                "fieldConfig": {"defaults": {"thresholds": {"steps": [{"value": 0, "color": "red"}, {"value": 90, "color": "yellow"}, {"value": 99, "color": "green"}]}, "unit": "percent"}},
            },
            {
                "id": 2, "title": "Error Budget Remaining %", "type": "gauge", "gridPos": {"x": 4, "y": 0, "w": 4, "h": 4},
                "targets": [{"expr": "affiliate_error_budget_remaining_pct", "legendFormat": "Budget %"}],
                "fieldConfig": {"defaults": {"min": 0, "max": 100, "unit": "percent", "thresholds": {"steps": [{"value": 0, "color": "red"}, {"value": 20, "color": "yellow"}, {"value": 50, "color": "green"}]}}},
            },
            {
                "id": 3, "title": "Daily AI Spend vs Cap", "type": "bargauge", "gridPos": {"x": 8, "y": 0, "w": 4, "h": 4},
                "targets": [
                    {"expr": "affiliate_daily_spend_usd", "legendFormat": "Spent"},
                    {"expr": "affiliate_daily_cost_cap_usd", "legendFormat": "Cap"},
                ],
                "fieldConfig": {"defaults": {"unit": "currencyUSD"}},
            },
            {
                "id": 4, "title": "Pipeline State", "type": "stat", "gridPos": {"x": 12, "y": 0, "w": 4, "h": 4},
                "targets": [
                    {"expr": "affiliate_pipeline_running", "legendFormat": "Running"},
                    {"expr": "affiliate_pipeline_paused", "legendFormat": "Paused"},
                ],
            },
            {
                "id": 5, "title": "Total Clicks", "type": "stat", "gridPos": {"x": 16, "y": 0, "w": 4, "h": 4},
                "targets": [{"expr": "affiliate_clicks_total", "legendFormat": "Clicks"}],
                "fieldConfig": {"defaults": {"unit": "short"}},
            },
            {
                "id": 6, "title": "Circuit Breakers", "type": "table", "gridPos": {"x": 0, "y": 4, "w": 8, "h": 6},
                "targets": [{"expr": "affiliate_circuit_breaker_open", "legendFormat": "{{breaker}}", "instant": True}],
            },
            {
                "id": 7, "title": "Component Latency P99 (ms)", "type": "timeseries", "gridPos": {"x": 8, "y": 4, "w": 16, "h": 6},
                "targets": [{"expr": "affiliate_latency_p99_ms", "legendFormat": "{{component}}"}],
                "fieldConfig": {"defaults": {"unit": "ms"}},
            },
            {
                "id": 8, "title": "Pipeline Runs (total / success)", "type": "timeseries", "gridPos": {"x": 0, "y": 10, "w": 12, "h": 6},
                "targets": [
                    {"expr": "affiliate_pipeline_runs_total", "legendFormat": "Total runs"},
                    {"expr": "affiliate_pipeline_success_total", "legendFormat": "Successes"},
                ],
            },
            {
                "id": 9, "title": "Component Error Rate %", "type": "timeseries", "gridPos": {"x": 12, "y": 10, "w": 12, "h": 6},
                "targets": [{"expr": "affiliate_error_rate_pct", "legendFormat": "{{component}}"}],
                "fieldConfig": {"defaults": {"unit": "percent"}},
            },
        ],
        "_import_instructions": {
            "step1": f"Add Prometheus scrape target: {space_host}/metrics",
            "step2": "In Grafana: Dashboards → Import → paste this JSON",
            "step3": "Select your Prometheus datasource as DS_PROMETHEUS",
        },
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


@app.get("/api/circuit-breakers")
async def list_circuit_breakers():
    return cb_statuses()


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

@app.get("/api/platforms/enabled")
async def platforms_enabled():
    return get_enabled_platforms(settings.get_settings())


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
        missing = []
        if not handle:
            missing.append("BSKY_HANDLE")
        if not password:
            missing.append("BSKY_APP_PASSWORD")
        return {"ok": False, "error": f"Bluesky credentials not set — enter them in Accounts or set {chr(39).join(missing) if len(missing)==1 else ' and '.join(missing)} in Space Secrets"}

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


# ── Click Tracker ───────────────────────────────────────────────────────────

@app.post("/api/clicks/record")
async def record_click_event(body: dict):
    from .utils.click_tracker import record_click
    return record_click(
        product_name=body.get("product_name", "unknown"),
        url=body.get("url", ""),
        platform=body.get("platform", "unknown"),
        source=body.get("source", "unknown"),
    )


@app.get("/api/clicks/summary")
async def click_summary():
    from .utils.click_tracker import clicks_summary
    return clicks_summary()


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
    """FinOps: daily spend, 30-day forecast, cap status, ROI and spend alerts."""
    s   = settings.get_settings()
    cap = float(s.get("dailyCostCap", 2.0))
    forecast = budget.get_monthly_forecast(cap)
    alert = budget.spend_alert(cap)
    runs = metrics.get_recent_runs(500)
    rev_forecast = budget.revenue_forecast(runs)
    roi = budget.compute_roi(
        monthly_commission=rev_forecast["projected_monthly_usd"],
        monthly_spend=forecast["monthly_est_usd"],
    )
    return {
        "today_usd":  round(budget.get_daily_spend(), 6),
        "cap_usd":    cap,
        "forecast":   forecast,
        "alert":      alert,
        "roi":        roi,
        "revenue_forecast": rev_forecast,
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
    from .utils import ab_test as _ab
    metrics.record_click(tracking_id)
    _ab.record_click(tracking_id)
    target = pipeline.resolve_redirect(tracking_id)
    if target:
        return RedirectResponse(target, status_code=302)
    return RedirectResponse("/", status_code=302)


# ── Affiliate conversion postbacks ─────────────────────────────────────────

@app.post("/api/affiliate/postback")
async def affiliate_postback(request: Request):
    """Receive affiliate conversion postbacks from networks.

    Networks call this URL when a user makes a purchase via our affiliate link.
    SOVRN:       POST /api/affiliate/postback?tid={tracking_id}&commission={amount}&network=sovrn
    TakeAds:     POST /api/affiliate/postback?tid={tracking_id}&commission={amount}&network=takeads
    Generic:     JSON body with tracking_id, commission_usd, network, order_id

    Security: validate the source via a shared secret in production.
    """
    import hmac as _hmac
    import hashlib as _hl

    # Accept both query-params (GET-style postbacks) and JSON body
    params = dict(request.query_params)
    try:
        body = await request.json()
    except Exception:
        body = {}

    tracking_id = (
        params.get("tid") or params.get("tracking_id")
        or body.get("tracking_id") or body.get("tid") or ""
    ).strip()
    try:
        commission_usd = float(
            params.get("commission") or params.get("commission_usd")
            or body.get("commission_usd") or body.get("commission") or 0
        )
    except (ValueError, TypeError):
        commission_usd = 0.0
    network = (
        params.get("network") or body.get("network") or "unknown"
    ).strip().lower()
    order_id = (
        params.get("order_id") or body.get("order_id") or ""
    ).strip()

    # Optional shared-secret validation (set POSTBACK_SECRET in Space Secrets)
    secret = os.environ.get("POSTBACK_SECRET", "")
    if secret:
        sig = params.get("sig") or body.get("sig") or ""
        expected = _hmac.new(secret.encode(), tracking_id.encode(), _hl.sha256).hexdigest()
        if not _hmac.compare_digest(sig, expected):
            return JSONResponse({"ok": False, "error": "invalid signature"}, status_code=403)

    if not tracking_id:
        return {"ok": False, "error": "tracking_id required"}
    if commission_usd < 0:
        return {"ok": False, "error": "commission must be non-negative"}

    result = metrics.record_conversion(tracking_id, commission_usd, network, order_id)
    if not result:
        logger.warn(f"Postback for unknown tracking_id={tracking_id!r} — no matching run")
        return {"ok": False, "error": "tracking_id not found"}

    logger.info(
        f"Conversion recorded: {tracking_id} +${commission_usd:.2f} via {network}",
        "postback",
    )
    return {
        "ok": True,
        "tracking_id": tracking_id,
        "commission_usd": commission_usd,
        "network": network,
        "total_commission_usd": result.get("totalCommissionUsd", 0),
    }


@app.get("/api/revenue")
async def revenue_summary():
    """Revenue dashboard — conversions, commission by network, daily breakdown."""
    runs = metrics.get_recent_runs(500)
    total_commission = metrics.get_total_commission()
    by_network = metrics.get_commission_by_network()
    conversion_count = metrics.get_conversion_count()
    total_clicks = metrics.get_total_clicks()

    # Daily revenue breakdown
    from collections import defaultdict as _dd
    daily: dict = _dd(lambda: {"conversions": 0, "commission_usd": 0.0, "clicks": 0})
    for r in runs:
        day = str(r.get("timestamp", ""))[:10]
        if not day:
            continue
        daily[day]["clicks"] += int(r.get("clicks", 0))
        for c in r.get("conversions", []):
            daily[day]["conversions"] += 1
            daily[day]["commission_usd"] = round(
                daily[day]["commission_usd"] + c.get("commission_usd", 0), 4
            )

    daily_list = [{"date": d, **v} for d, v in sorted(daily.items())][-30:]

    epc = round(total_commission / total_clicks, 4) if total_clicks else 0.0  # earnings per click

    return {
        "total_commission_usd": total_commission,
        "conversion_count": conversion_count,
        "total_clicks": total_clicks,
        "epc_usd": epc,
        "by_network": by_network,
        "daily": daily_list,
    }


@app.get("/api/ab-results")
async def ab_results():
    """A/B caption test results — CTR per variant and winner if statistically clear."""
    from .utils import ab_test as _ab
    return _ab.get_results()


@app.get("/api/analytics/summary")
async def analytics_summary(days: int = 30):
    """Run history analytics — aggregated stats for the last `days` days."""
    runs = metrics.get_recent_runs(500)
    from .utils.analytics import summarize_runs
    return summarize_runs(runs, days=days)


# ── Blacklist management ──────────────────────────────────────────────────────

@app.get("/api/blacklist")
async def get_blacklist():
    from .utils.blacklist import get_blacklist
    return get_blacklist()


@app.post("/api/blacklist/product")
async def blacklist_product(body: dict):
    from .utils.blacklist import add_product
    add_product(body.get("name", ""))
    return {"ok": True}


@app.post("/api/blacklist/domain")
async def blacklist_domain(body: dict):
    from .utils.blacklist import add_domain
    add_domain(body.get("domain", ""))
    return {"ok": True}


@app.delete("/api/blacklist/product")
async def remove_blacklist_product(name: str):
    from .utils.blacklist import remove_product
    return {"removed": remove_product(name)}


@app.delete("/api/blacklist/domain")
async def remove_blacklist_domain(domain: str):
    from .utils.blacklist import remove_domain
    return {"removed": remove_domain(domain)}


@app.get("/api/feeds/health")
async def feeds_health():
    from .utils.feed_health import all_feeds_health
    return {"feeds": all_feeds_health()}


@app.get("/api/commission-rates")
async def commission_rates():
    from .utils.commission_rates import get_all_rates
    return get_all_rates()


@app.post("/api/commission-rates")
async def set_commission_rate(body: dict):
    from .utils.commission_rates import set_rate
    try:
        set_rate(body.get("network", "default"), float(body.get("rate", 0.05)))
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Scheduled post queue ───────────────────────────────────────────────────

@app.get("/api/queue")
async def get_post_queue(status: str | None = None):
    from .utils.post_queue import get_queue
    return {"items": get_queue(status=status)}

@app.post("/api/queue")
async def enqueue_post(body: dict):
    from .utils.post_queue import enqueue
    return enqueue(
        product_name=body.get("product_name", ""),
        platform=body.get("platform", "bluesky"),
        scheduled_at=body.get("scheduled_at", ""),
        caption=body.get("caption"),
    )

@app.delete("/api/queue/{item_id}")
async def cancel_queued_post(item_id: str):
    from .utils.post_queue import cancel
    return {"cancelled": cancel(item_id)}



# ── Build registry ─────────────────────────────────────────────────────────

@app.get("/api/builds")
async def list_builds():
    from .utils.build_registry import get_builds
    builds = get_builds()
    return {"builds": builds, "total": len(builds)}


@app.get("/api/builds/{number}")
async def get_build_by_number(number: int):
    from .utils.build_registry import get_build
    build = get_build(number)
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


# ── Activity log ────────────────────────────────────────────────────────────

@app.get("/api/activity")
async def get_activity(limit: int = 100):
    from .utils.activity_log import get_recent
    return {"entries": get_recent(limit=limit)}


@app.get("/api/activity/summary")
async def get_activity_summary():
    from .utils.activity_log import activity_summary
    return activity_summary()


@app.get("/api/health/full")
async def full_health():
    from .utils.system_health import get_full_health
    return get_full_health()


@app.get("/api/audit")
async def system_audit():
    from .utils.system_audit import run_audit
    return run_audit()


@app.post("/api/geo-filter")
async def geo_filter_products(body: dict):
    from .utils.geo_filter import filter_by_region
    products = body.get("products", [])
    allowed = body.get("allowed_regions", [])
    return {"filtered": filter_by_region(products, allowed), "count": len(filter_by_region(products, allowed))}


@app.post("/api/variations")
async def get_variations(body: dict):
    from .utils.content_variations import generate_all_variations
    product = body.get("product", {})
    return generate_all_variations(product)


@app.post("/api/link-check")
async def link_check(body: dict):
    url = body.get("url", "")
    if not url:
        return {"url": url, "alive": False, "error": "no url provided"}
    from .utils.link_checker import check_link
    return await check_link(url)


@app.post("/api/price-monitor/rank")
async def rank_products_by_value(body: dict):
    from .utils.price_monitor import rank_by_value, best_value_per_category
    products = body.get("products", [])
    return {
        "ranked": rank_by_value(products),
        "best_per_category": best_value_per_category(products),
    }


# ── Link-in-bio landing page ───────────────────────────────────────────────

@app.get("/bio", response_class=HTMLResponse)
@app.get("/links", response_class=HTMLResponse)
async def link_in_bio():
    """Public link-in-bio page — Instagram bio link target.

    Shows the last 10 successful posts as product cards with:
    - Product name + description
    - Price
    - Affiliate tracking link (via /r/{tracking_id})
    - Category badge

    No authentication required — this is the public storefront.
    """
    space_host = settings.get_settings().get("spaceHost") or os.environ.get("SPACE_HOST", "")
    base_url = f"https://{space_host}" if space_host else ""

    runs = metrics.get_recent_runs(200)
    successful = [
        r for r in reversed(runs)
        if r.get("success") and r.get("deeplink") and r.get("product")
    ][:10]

    def _card(r: dict) -> str:
        name     = r.get("product", "Product")
        price    = r.get("price")
        category = r.get("category", "")
        image    = r.get("imageUrl") or r.get("postImageUrl") or ""
        tid      = r.get("trackingId", "")
        link     = f"{base_url}/r/{tid}" if tid and base_url else r.get("deeplink", "#")
        price_str = f"${price:.2f}" if isinstance(price, (int, float)) else (str(price) if price else "")
        img_html = (
            f'<img src="{image}" alt="{name}" loading="lazy" '
            f'onerror="this.style.display=\'none\'">'
            if image else
            '<div class="no-img">🛒</div>'
        )
        badge = f'<span class="badge">{category}</span>' if category else ""
        return f"""
        <a class="card" href="{link}" target="_blank" rel="noopener noreferrer">
          <div class="card-img">{img_html}</div>
          <div class="card-body">
            {badge}
            <h3>{name}</h3>
            {f'<p class="price">{price_str}</p>' if price_str else ""}
            <span class="cta">Shop Now →</span>
          </div>
        </a>"""

    cards_html = "\n".join(_card(r) for r in successful)
    if not cards_html:
        cards_html = '<p class="empty">No products yet — check back soon! 🛍️</p>'

    handle = settings.get_settings().get("bioHandle", "@auto.affiliate")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex">
  <title>{handle} — Latest Deals</title>
  <style>
    :root {{
      --bg: #0f0f0f; --surface: #1a1a1a; --border: #2a2a2a;
      --accent: #6366f1; --text: #e5e5e5; --muted: #888; --radius: 14px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    header {{ text-align: center; padding: 2rem 1rem 1rem; }}
    header h1 {{ font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; }}
    header p {{ color: var(--muted); font-size: 0.9rem; margin-top: 0.3rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; padding: 1rem; max-width: 960px; margin: 0 auto; }}
    .card {{ display: flex; flex-direction: column; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; text-decoration: none; color: inherit; transition: transform 0.15s, box-shadow 0.15s; }}
    .card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 32px rgba(99,102,241,0.18); }}
    .card-img {{ aspect-ratio: 4/3; overflow: hidden; background: var(--border); display: flex; align-items: center; justify-content: center; }}
    .card-img img {{ width: 100%; height: 100%; object-fit: cover; }}
    .no-img {{ font-size: 3rem; }}
    .card-body {{ padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; flex: 1; }}
    .badge {{ display: inline-block; background: rgba(99,102,241,0.15); color: var(--accent); border: 1px solid rgba(99,102,241,0.3); border-radius: 99px; font-size: 0.7rem; padding: 0.15rem 0.6rem; width: fit-content; }}
    h3 {{ font-size: 0.95rem; font-weight: 600; line-height: 1.35; }}
    .price {{ font-size: 1.1rem; font-weight: 700; color: var(--accent); }}
    .cta {{ margin-top: auto; font-size: 0.85rem; font-weight: 600; color: var(--accent); }}
    .empty {{ text-align: center; color: var(--muted); padding: 3rem; font-size: 1.1rem; }}
    footer {{ text-align: center; color: var(--muted); font-size: 0.75rem; padding: 2rem 1rem; }}
    footer a {{ color: var(--muted); }}
  </style>
</head>
<body>
  <header>
    <h1>{handle}</h1>
    <p>Latest deals — updated automatically ✨</p>
  </header>
  <main class="grid">
    {cards_html}
  </main>
  <footer>
    <p>Links may be affiliate links — we earn a small commission at no extra cost to you.</p>
  </footer>
</body>
</html>"""
