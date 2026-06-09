"""Hourly pipeline: fetch product -> trends -> caption -> image -> post to Bluesky."""

import os
import time
import uuid
from urllib.parse import quote

import httpx

from .ai import text as ai_text
from .bluesky_client import post_to_bluesky
from .feeds.sovrn import get_sovrn_product
from .utils import budget, logger, metrics, settings

STATIC_TRENDS = [
    "summer deals", "gift ideas", "tech upgrades", "home essentials",
    "self care", "back to school", "fitness goals", "everyday savings",
]

# In-memory pipeline state shared with the API layer.
STATE = {
    "running": False,
    "paused": False,
    "lastRun": None,
    "lastError": None,
}

# Maps short tracking id -> destination deeplink (also persisted via metrics runs).
_REDIRECTS: dict = {}


async def get_trends() -> list:
    key = os.environ.get("ADMITAD_CLIENT_ID", "")
    if not key:
        return list(STATIC_TRENDS)
    # Admitad trend feed is optional; fall back to static on any issue.
    return list(STATIC_TRENDS)


async def _get_product() -> dict | None:
    """SOVRN first when key is set, then any other configured network."""
    product = await get_sovrn_product()
    if product:
        return product
    logger.warn("No product source returned a product")
    return None


async def _find_image(product: dict) -> bytes | None:
    url = product.get("imageUrl")
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            return r.content
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Image download failed: {err}")
    return None


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


async def dry_run() -> dict:
    product = await _get_product()
    if not product:
        return {"ok": False, "error": "No product available from any network"}
    trends = await get_trends()
    caption = await ai_text.generate_post_text(product, trends)
    return {
        "ok": True,
        "product": product,
        "caption": caption,
        "trends": trends[:3],
    }


def _record(run: dict) -> dict:
    metrics.record_run(run)
    STATE["lastRun"] = run
    STATE["lastError"] = run.get("error")
    return run


async def run_pipeline() -> dict:
    if STATE["running"]:
        return {"ok": False, "error": "Pipeline already running"}
    STATE["running"] = True
    started = time.time()
    try:
        return await _execute(started)
    except Exception as err:  # noqa: BLE001
        logger.error(f"Pipeline error: {err}")
        return _record({
            "success": False, "error": str(err),
            "durationMs": int((time.time() - started) * 1000),
        })
    finally:
        STATE["running"] = False


async def _execute(started: float) -> dict:
    cap = float(settings.get_settings().get("dailyCostCap", 2.0))
    if budget.get_daily_spend() >= cap:
        return _record({"success": False, "error": "Daily cost cap reached"})

    product = await _get_product()
    if not product:
        return _record({"success": False, "error": "No product available"})

    if metrics.was_recently_posted(product.get("siteUrl"), product.get("name")):
        return _record({
            "success": False, "error": "Product already posted (dedup)",
            "product": product.get("name"), "productSource": product.get("source"),
        })

    trends = await get_trends()
    caption = await ai_text.generate_post_text(product, trends)
    image = await _find_image(product)

    deeplink = product.get("deeplink") or product.get("siteUrl")
    tracking_id, redirect = _tracking_url(deeplink)

    uri = await post_to_bluesky(caption, redirect, image, product)

    budget.add_spend(0.001)
    metrics.mark_posted(product.get("siteUrl"), product.get("name"), product.get("source"))

    return _record({
        "success": True,
        "product": product.get("name"),
        "productSource": product.get("source"),
        "imageSource": "feed" if image else None,
        "captionChars": len(caption),
        "postUri": uri,
        "deeplink": deeplink,
        "trackingId": tracking_id,
        "durationMs": int((time.time() - started) * 1000),
    })
