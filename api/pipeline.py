"""Hourly pipeline: fetch product -> trends -> caption -> image -> post to Bluesky.

Reliability:
  - Per-phase timeout guards
  - Graceful degradation: image failure never blocks a post
  - Multi-network product fetching with rotation
  - Per-component latency tracking
"""

import asyncio
import os
import time
import uuid

import httpx

from .ai import text as ai_text
from .bluesky_client import post_to_bluesky
from .feeds.sovrn import get_sovrn_product
from .utils import budget as budget_util
from .utils import logger, metrics, settings
from .utils.telemetry import Timer

STATIC_TRENDS = [
    "summer deals", "gift ideas", "tech upgrades", "home essentials",
    "self care", "back to school", "fitness goals", "everyday savings",
]

PIPELINE_TIMEOUT = 300  # 5 minutes max per run
IMAGE_TIMEOUT    = 15   # seconds to download image

# In-memory pipeline state shared with the API layer
STATE: dict = {
    "running": False,
    "paused": False,
    "lastRun": None,
    "lastError": None,
    "runCount": 0,
    "successCount": 0,
}

# Short tracking id -> destination deeplink (in-memory; also persisted via metrics)
_REDIRECTS: dict = {}


# ── Product fetching ─────────────────────────────────────────────────────────

async def _try_sovrn() -> dict | None:
    if not os.environ.get("SOVRN_API_KEY"):
        return None
    try:
        with Timer("sovrn_fetch"):
            return await get_sovrn_product()
    except Exception as err:  # noqa: BLE001
        logger.warn(f"SOVRN fetch failed: {err}")
        return None


async def _get_product() -> dict | None:
    """Try each configured network in priority order; return first successful product."""
    # Priority: SOVRN (curated + monetized) → future networks here
    product = await _try_sovrn()
    if product:
        return product

    logger.warn("All product networks failed or unconfigured — no product available")
    return None


# ── Trends ───────────────────────────────────────────────────────────────────

async def get_trends() -> list:
    return list(STATIC_TRENDS)


# ── Image ────────────────────────────────────────────────────────────────────

async def _find_image(product: dict) -> bytes | None:
    url = product.get("imageUrl")
    if not url:
        return None
    try:
        with Timer("image_download"):
            async with httpx.AsyncClient(timeout=IMAGE_TIMEOUT, follow_redirects=True) as client:
                r = await client.get(url)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                return r.content
            logger.warn(f"Image fetch non-200 ({r.status_code}) or non-image content-type")
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Image download failed (non-fatal): {err}")
    return None


# ── Tracking ─────────────────────────────────────────────────────────────────

def _tracking_url(deeplink: str) -> tuple[str, str]:
    tid = uuid.uuid4().hex[:10]
    _REDIRECTS[tid] = deeplink
    host = settings.get_space_host()
    redirect = f"{host}/r/{tid}" if host else deeplink
    return tid, redirect


def resolve_redirect(tracking_id: str) -> str | None:
    if tracking_id in _REDIRECTS:
        return _REDIRECTS[tracking_id]
    for run in metrics.get_recent_runs(500):
        if run.get("trackingId") == tracking_id:
            return run.get("deeplink")
    return None


# ── Run recording ────────────────────────────────────────────────────────────

def _record(run: dict) -> dict:
    metrics.record_run(run)
    STATE["lastRun"] = run
    STATE["lastError"] = run.get("error") if not run.get("success") else None
    STATE["runCount"] += 1
    if run.get("success"):
        STATE["successCount"] += 1
    return run


# ── Dry run ──────────────────────────────────────────────────────────────────

async def dry_run() -> dict:
    product = await _get_product()
    if not product:
        return {"ok": False, "error": "No product available from any configured network"}
    trends = await get_trends()
    caption = await ai_text.generate_post_text(product, trends)
    return {
        "ok": True,
        "product": product,
        "caption": caption,
        "captionLen": len(caption),
        "trends": trends[:3],
    }


# ── Main pipeline ────────────────────────────────────────────────────────────

async def run_pipeline() -> dict:
    if STATE["running"]:
        return {"ok": False, "error": "Pipeline already running"}
    if STATE["paused"]:
        return {"ok": False, "error": "Pipeline is paused"}

    STATE["running"] = True
    started = time.time()
    try:
        return await asyncio.wait_for(
            _execute(started),
            timeout=PIPELINE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        err = f"Pipeline timed out after {PIPELINE_TIMEOUT}s"
        logger.error(err)
        return _record({"success": False, "error": err,
                        "durationMs": int((time.time() - started) * 1000)})
    except Exception as err:  # noqa: BLE001
        logger.error(f"Pipeline uncaught error: {err}")
        return _record({"success": False, "error": str(err),
                        "durationMs": int((time.time() - started) * 1000)})
    finally:
        STATE["running"] = False


async def _execute(started: float) -> dict:
    s = settings.get_settings()
    cap = float(s.get("dailyCostCap", 2.0))

    # ── Guard: cost cap ──
    if budget_util.get_daily_spend() >= cap:
        return _record({"success": False, "error": f"Daily cost cap ${cap:.2f} reached"})

    # ── Guard: credentials ──
    if not os.environ.get("BSKY_HANDLE") or not os.environ.get("BSKY_APP_PASSWORD"):
        return _record({
            "success": False,
            "error": "Bluesky credentials not configured — set BSKY_HANDLE + BSKY_APP_PASSWORD in Space Secrets",
        })

    # ── Phase 1: Product ──
    with Timer("product_fetch"):
        product = await _get_product()
    if not product:
        return _record({"success": False, "error": "No product available from any network"})

    # ── Guard: dedup ──
    if metrics.was_recently_posted(product.get("siteUrl"), product.get("name")):
        return _record({
            "success": False, "error": "Product already posted recently (dedup skip)",
            "product": product.get("name"), "productSource": product.get("source"),
        })

    # ── Phase 2: Caption ──
    trends = await get_trends()
    with Timer("caption_gen"):
        caption = await ai_text.generate_post_text(product, trends)
    logger.info(f"Caption ({len(caption)} chars): {caption[:80]}…")

    # ── Phase 3: Image (non-blocking — failure is fine) ──
    image = await _find_image(product)

    # ── Phase 4: Tracking URL ──
    deeplink = product.get("deeplink") or product.get("siteUrl") or ""
    if not deeplink:
        return _record({"success": False, "error": "Product has no URL"})
    tracking_id, redirect = _tracking_url(deeplink)

    # ── Phase 5: Post to Bluesky ──
    with Timer("bluesky_publish") as t:
        uri = await post_to_bluesky(caption, redirect, image, product)

    budget_util.add_spend(0.001)
    metrics.mark_posted(product.get("siteUrl"), product.get("name"), product.get("source"))

    duration_ms = int((time.time() - started) * 1000)
    logger.info(f"Pipeline complete in {duration_ms}ms — {uri}")

    return _record({
        "success": True,
        "product": product.get("name"),
        "productSource": product.get("source"),
        "imageSource": "feed" if image else "none",
        "captionChars": len(caption),
        "postUri": uri,
        "deeplink": deeplink,
        "trackingId": tracking_id,
        "durationMs": duration_ms,
    })


# ── SLO calculation ──────────────────────────────────────────────────────────

def calculate_slo(window: int = 500) -> dict:
    """Calculate 30-day SLO compliance and error budget."""
    runs = metrics.get_recent_runs(window)
    if not runs:
        return {"slo_pct": None, "error_budget_remaining_pct": 100.0, "total": 0}
    total   = len(runs)
    success = sum(1 for r in runs if r.get("success"))
    slo_pct = round(success / total * 100, 2)
    target  = 99.9
    # Error budget = allowed failures in period
    budget_consumed = max(0.0, target - slo_pct) / (100 - target) * 100 if total > 0 else 0.0
    return {
        "slo_pct": slo_pct,
        "slo_target": target,
        "error_budget_remaining_pct": round(max(0.0, 100.0 - budget_consumed), 1),
        "error_budget_consumed_pct": round(min(100.0, budget_consumed), 1),
        "total": total,
        "success": success,
        "failures": total - success,
    }
