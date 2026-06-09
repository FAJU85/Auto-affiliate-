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
    return {"ok": True, "status": "healthy"}


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
    return {
        "pipeline": {
            "running": pipeline.STATE["running"],
            "paused": pipeline.STATE["paused"],
            "schedule": _cron(),
            "nextRun": None if pipeline.STATE["paused"] else _next_run(),
            "lastRun": pipeline.STATE["lastRun"],
        },
        "budget": {"spent": round(budget.get_daily_spend(), 4), "cap": cap},
        "stats": _stats(),
        "runs": metrics.get_recent_runs(20),
        "missingVars": _missing_vars(),
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
    connected = bool(os.environ.get("BSKY_HANDLE") and os.environ.get("BSKY_APP_PASSWORD"))
    return {
        "bluesky": {
            "connected": connected,
            "handle": os.environ.get("BSKY_HANDLE", ""),
            "method": "app-password",
        }
    }


@app.post("/api/accounts/bluesky/disconnect")
async def disconnect_bluesky():
    return {"ok": True, "note": "Bluesky uses env credentials; clear them in Space settings."}


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

@app.get("/api/insights")
async def insights():
    return {
        "networkHealth": metrics.get_network_health(100),
        "dedup": metrics.get_dedup_status(),
        "totalClicks": metrics.get_total_clicks(),
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
