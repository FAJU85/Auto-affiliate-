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
from .utils.circuit_breaker import AuthError
from .feeds.sovrn import get_sovrn_product
from .feeds.takeads import get_takeads_product
from .feeds.admitad import get_admitad_product
from .feeds.travelpayouts import get_travelpayouts_product
from .social_post import post_to_platform
from .utils.platform_guardian import check_allowed
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
    "pausedUntil": None,   # epoch float — auto-resume after this time (None = manual pause)
    "lastRun": None,
    "lastError": None,
    "runCount": 0,
    "successCount": 0,
}

RATE_LIMIT_COOLDOWN = 3600  # 1h auto-resume after rate-limit pause

# Short tracking id -> destination deeplink (in-memory; also persisted via metrics)
_REDIRECTS: dict = {}


# ── Product fetching ─────────────────────────────────────────────────────────

async def _try_network(name: str, fn, timer_key: str) -> dict | None:
    try:
        with Timer(timer_key):
            return await fn()
    except Exception as err:  # noqa: BLE001
        logger.warn(f"{name} fetch failed: {err}", name.lower())
        return None


async def _get_product() -> dict | None:
    """Try each configured network in priority order; return first successful product.

    Priority:
      1. SOVRN   — curated product pool, always monetized
      2. TakeAds — active affiliate programs, highest commission first
      3. Admitad — XML feed (requires ADMITAD_FEED_URL)
      4. Travelpayouts — live flight deals (travel niche)
    """
    if os.environ.get("SOVRN_API_KEY"):
        product = await _try_network("SOVRN", get_sovrn_product, "sovrn_fetch")
        if product:
            return product

    if os.environ.get("TAKEADS_API_KEY"):
        product = await _try_network("TakeAds", get_takeads_product, "takeads_fetch")
        if product:
            return product

    if os.environ.get("ADMITAD_FEED_URL"):
        product = await _try_network("Admitad", get_admitad_product, "admitad_fetch")
        if product:
            return product

    if os.environ.get("TRAVELPAYOUTS_TOKEN"):
        product = await _try_network("Travelpayouts", get_travelpayouts_product, "travelpayouts_fetch")
        if product:
            return product

    logger.warn("All product networks failed or unconfigured — no product available", "pipeline")
    return None


# ── Trends ───────────────────────────────────────────────────────────────────

async def get_trends() -> list:
    return list(STATIC_TRENDS)


# ── Image ────────────────────────────────────────────────────────────────────

async def _find_image(product: dict) -> tuple[bytes | None, str | None]:
    """Return (image_bytes, public_image_url). Either or both may be None.

    Facebook / Instagram / Threads need a public URL; Bluesky / Mastodon / X
    use raw bytes.  We return both so the pipeline can pass the right form to
    each platform.
    """
    # Try explicit imageUrl first
    url = product.get("imageUrl")
    if url:
        try:
            with Timer("image_download"):
                async with httpx.AsyncClient(timeout=IMAGE_TIMEOUT, follow_redirects=True) as client:
                    r = await client.get(url)
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                    return r.content, url
        except Exception as err:  # noqa: BLE001
            logger.warn(f"Image download failed: {err}")

    # Fall back: extract og:image from Amazon product page
    site_url = product.get("siteUrl") or product.get("deeplink") or ""
    if "amazon.com" in site_url:
        try:
            img_bytes, img_url = await _fetch_amazon_og_image(site_url)
            if img_bytes:
                return img_bytes, img_url
        except Exception as err:  # noqa: BLE001
            logger.warn(f"Amazon image scrape failed (non-fatal): {err}")

    logger.warn("No image available for product — posting without image")
    return None, None


async def _fetch_amazon_og_image(product_url: str) -> tuple[bytes | None, str | None]:
    """Scrape Amazon product page for og:image URL, then download it.
    Returns (bytes, url) so callers that need a public URL (Facebook/Instagram/Threads) have it.
    """
    import re
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        async with httpx.AsyncClient(timeout=IMAGE_TIMEOUT, follow_redirects=True, headers=headers) as client:
            r = await client.get(product_url)
        if r.status_code != 200:
            logger.warn(f"Amazon page fetch HTTP {r.status_code} — no image")
            return None, None
        m = re.search(r'"og:image"[^>]*content="([^"]+)"', r.text)
        if not m:
            m = re.search(r'content="(https://m\.media-amazon\.com/images/I/[^"]+)"', r.text)
        if not m:
            logger.warn("og:image not found in Amazon page")
            return None, None
        img_url = m.group(1).replace("&amp;", "&")
        async with httpx.AsyncClient(timeout=IMAGE_TIMEOUT, follow_redirects=True) as client:
            ir = await client.get(img_url)
        if ir.status_code == 200 and ir.headers.get("content-type", "").startswith("image"):
            return ir.content, img_url
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Amazon og:image fetch error: {err}")
    return None, None


# ── Tracking ─────────────────────────────────────────────────────────────────

def _tracking_url(deeplink: str) -> tuple[str, str]:
    tid = uuid.uuid4().hex[:10]
    _REDIRECTS[tid] = deeplink
    host = settings.get_space_host()
    if not host:
        logger.warn(
            "SPACE_HOST not configured — click tracking disabled. "
            "Set SPACE_HOST in Space Secrets to enable /r/{id} redirect tracking.",
            "pipeline",
        )
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
        # Auto-resume if the timed cooldown has expired
        until = STATE.get("pausedUntil")
        if until and time.time() >= until:
            STATE["paused"] = False
            STATE["pausedUntil"] = None
            logger.info("Rate-limit cooldown expired — auto-resuming pipeline", "pipeline")
        else:
            wait = int(until - time.time()) if until else 0
            msg = f"Pipeline is paused — auto-resumes in {wait}s" if until else "Pipeline is paused"
            return {"ok": False, "error": msg}

    STATE["running"] = True
    started = time.time()
    try:
        return await asyncio.wait_for(
            _execute(started),
            timeout=PIPELINE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        err = f"Pipeline timed out after {PIPELINE_TIMEOUT}s"
        logger.error(err, "pipeline")
        return _record({"success": False, "error": err,
                        "durationMs": int((time.time() - started) * 1000)})
    except Exception as err:  # noqa: BLE001
        logger.error(f"Pipeline uncaught error: {err}", "pipeline")
        return _record({"success": False, "error": str(err),
                        "durationMs": int((time.time() - started) * 1000)})
    finally:
        STATE["running"] = False


async def _execute(started: float) -> dict:
    s = settings.get_settings()
    cap = float(s.get("dailyCostCap", 2.0))
    platforms = s.get("publishPlatforms", ["bluesky"])

    # ── Guard: cost cap ──
    if budget_util.get_daily_spend() >= cap:
        return _record({"success": False, "error": f"Daily cost cap ${cap:.2f} reached"})

    # ── Guard: at least one platform selected ──
    if not platforms:
        return _record({"success": False, "error": "No publishing platforms selected — enable at least one in Settings"})

    # ── Guard: Bluesky credentials (only if Bluesky is selected) ──
    if "bluesky" in platforms:
        if not s.get("bskyEnabled", True):
            platforms = [p for p in platforms if p != "bluesky"]
            logger.warn("Bluesky disabled — skipping, continuing with other platforms", "bluesky")
        else:
            from .bluesky_client import _bsky_credentials
            _h, _p = _bsky_credentials()
            if not _h or not _p:
                platforms = [p for p in platforms if p != "bluesky"]
                logger.warn("Bluesky credentials missing — skipping, continuing with other platforms", "bluesky")

    if not platforms:
        return _record({"success": False, "error": "No platforms available to post to"})

    logger.info(f"Pipeline starting — platforms: {platforms}", "pipeline")

    # ── Phase 1: Product ──
    with Timer("product_fetch"):
        product = await _get_product()
    if not product:
        return _record({"success": False, "error": "No product available from any network"})
    logger.info(f"Product: {product.get('name', '?')!r} via {product.get('source', '?')}", "pipeline")

    # ── Guard: dedup (1h hard block — prevents exact repeat within same session) ──
    if metrics.was_posted_within(product.get("siteUrl"), product.get("name"), hours=1):
        return _record({
            "success": False, "error": "Product already posted recently (dedup skip)",
            "product": product.get("name"), "productSource": product.get("source"),
        })

    # ── Phase 2: Caption ──
    trends = await get_trends()
    with Timer("caption_gen"):
        caption = await ai_text.generate_post_text(product, trends)
    logger.info(f"Caption ({len(caption)} chars): {caption[:80]}…", "ai")

    # ── Phase 3: Image (non-blocking — failure is fine) ──
    # image_bytes → Bluesky / Mastodon / X (binary upload)
    # image_url   → Facebook / Instagram / Threads (need a public HTTPS URL)
    image, image_url = await _find_image(product)
    # If product already has a public imageUrl, prefer that for URL-based platforms
    image_url = image_url or product.get("imageUrl")

    # ── Phase 4: Tracking URL ──
    deeplink = product.get("deeplink") or product.get("siteUrl") or ""
    if not deeplink:
        return _record({"success": False, "error": "Product has no URL"})
    tracking_id, redirect = _tracking_url(deeplink)

    # ── Phase 5: Post to all enabled platforms ──
    recent_runs = metrics.get_recent_runs(500)
    uris = {}
    primary_uri = ""
    any_success = False

    for platform in platforms:
        # Anti-ban guardian: check daily limit, interval, and posting hours
        allowed, reason = check_allowed(platform, recent_runs)
        if not allowed:
            logger.info(f"Skipped by guardian: {reason}", platform)
            continue

        if platform == "bluesky":
            try:
                with Timer("bluesky_publish"):
                    uri = await post_to_bluesky(caption, redirect, image, product)
                uris["bluesky"] = uri
                primary_uri = primary_uri or uri
                any_success = True
                logger.info(f"Posted OK → {uri}", "bluesky")
            except AuthError as _err:
                logger.error(f"Bluesky auth error (permanent) — check credentials: {_err}", "bluesky")
            except RuntimeError as _err:
                _msg = str(_err)
                if "rate" in _msg.lower() or "429" in _msg.lower():
                    STATE["paused"] = True
                    STATE["pausedUntil"] = time.time() + RATE_LIMIT_COOLDOWN
                    logger.warn(f"Rate-limited — auto-paused for {RATE_LIMIT_COOLDOWN}s: {_msg}", "bluesky")
                logger.error(f"Post failed: {_msg}", "bluesky")
        else:
            logger.info("Attempting post…", platform)
            uri = await post_to_platform(
                platform, caption, redirect,
                image=image, image_url=image_url, product=product,
            )
            if uri:
                uris[platform] = uri
                primary_uri = primary_uri or uri
                any_success = True
                logger.info(f"Posted OK → {uri}", platform)
            else:
                logger.error("Post returned no URI — check connection in Accounts", platform)

    if not any_success:
        return _record({"success": False, "error": f"All platforms failed: {list(platforms)}"})

    budget_util.add_spend(0.001)
    metrics.mark_posted(product.get("siteUrl"), product.get("name"), product.get("source"))

    duration_ms = int((time.time() - started) * 1000)
    logger.info(f"Pipeline complete in {duration_ms}ms — posted to {list(uris.keys())}", "pipeline")

    return _record({
        "success": True,
        "product": product.get("name"),
        "productSource": product.get("source"),
        "imageSource": "feed" if image else "none",
        "captionChars": len(caption),
        "postUri": primary_uri,
        "postUris": uris,
        "platforms": list(uris.keys()),
        "deeplink": deeplink,
        "trackingId": tracking_id,
        "durationMs": duration_ms,
    })


# ── SLO calculation ──────────────────────────────────────────────────────────

SLO_TARGET = 90.0  # 90% — realistic for a bot posting hourly via third-party APIs
                   # 99.9% would deplete budget on any single transient failure

def calculate_slo(window: int = 500) -> dict:
    """Calculate 30-day SLO compliance and error budget."""
    runs = metrics.get_recent_runs(window)
    if not runs:
        return {"slo_pct": None, "error_budget_remaining_pct": 100.0, "total": 0,
                "slo_target": SLO_TARGET}
    total   = len(runs)
    success = sum(1 for r in runs if r.get("success"))
    slo_pct = round(success / total * 100, 2)
    # Error budget = fraction of allowed failures consumed
    # At SLO_TARGET=90%: 10% failures allowed per window
    allowed_failure_rate = (100 - SLO_TARGET) / 100
    actual_failure_rate  = (total - success) / total
    budget_consumed = min(1.0, actual_failure_rate / allowed_failure_rate) * 100 if allowed_failure_rate > 0 else 100.0
    return {
        "slo_pct": slo_pct,
        "slo_target": SLO_TARGET,
        "error_budget_remaining_pct": round(max(0.0, 100.0 - budget_consumed), 1),
        "error_budget_consumed_pct": round(min(100.0, budget_consumed), 1),
        "total": total,
        "success": success,
        "failures": total - success,
    }
