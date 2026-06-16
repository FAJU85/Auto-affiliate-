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
from .feeds.amazon import get_amazon_product
from .social_post import post_to_platform
from .utils.platform_guardian import check_allowed
from .utils import budget as budget_util
from .utils import logger, metrics, settings
from .utils.telemetry import Timer
from .utils.product_scorer import pick_best, pick_best_with_freshness, score_product
from .utils import retry_queue
from .utils.price_tracker import record_price, check_price_drop
from .utils import ab_test as ab

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
    """Fetch candidates from all configured networks and return the highest-scoring one.

    Scoring weights: commission 40%, price band 30%, has image 20%, description 10%.
    This ensures we always post the most revenue-valuable product available, not
    just whichever network responds first.
    """
    candidates: list[dict] = []

    async def _try(name: str, fn, key: str) -> None:
        p = await _try_network(name, fn, key)
        if p:
            candidates.append(p)

    # Gather one candidate from each configured network concurrently
    tasks = []
    if os.environ.get("SOVRN_API_KEY"):
        tasks.append(_try("SOVRN", get_sovrn_product, "sovrn_fetch"))
    if os.environ.get("TAKEADS_API_KEY"):
        tasks.append(_try("TakeAds", get_takeads_product, "takeads_fetch"))
    if os.environ.get("ADMITAD_FEED_URL"):
        tasks.append(_try("Admitad", get_admitad_product, "admitad_fetch"))
    if os.environ.get("TRAVELPAYOUTS_TOKEN"):
        tasks.append(_try("Travelpayouts", get_travelpayouts_product, "travelpayouts_fetch"))
    if os.environ.get("AMAZON_ASSOCIATE_TAG"):
        tasks.append(_try("Amazon", get_amazon_product, "amazon_fetch"))

    if not tasks:
        logger.warn("All product networks unconfigured — no product available", "pipeline")
        return None

    await asyncio.gather(*tasks)

    if not candidates:
        logger.warn("All product networks failed — no product available", "pipeline")
        return None

    runs = metrics.get_recent_runs(500)
    best = pick_best_with_freshness(candidates, runs)
    if len(candidates) > 1 and best:
        from .utils.product_scorer import score_product as _sp
        score = _sp(best)
        logger.info(
            f"Scored {len(candidates)} candidates — best: {best['name']!r} "
            f"({best['source']}) score={score.total:.0%}",
            "pipeline",
        )
    return best


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

    # Smart schedule soft gate: skip low-engagement hours when enabled
    import os as _os
    from datetime import datetime as _dt, timezone as _tz
    if _os.environ.get("SMART_SCHEDULE", "").strip() in ("1", "true", "yes"):
        from .utils.smart_schedule import is_peak_hour
        current_hour = _dt.now(_tz.utc).hour
        runs = metrics.get_recent_runs(500)
        if not is_peak_hour(current_hour, runs):
            logger.info(f"Smart schedule: hour {current_hour:02d} UTC is off-peak — skipping", "pipeline")
            return {"ok": False, "skipped": True, "reason": f"off-peak hour {current_hour:02d} UTC"}

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

    # ── Price drop detection ──
    price_drop = check_price_drop(product)
    if price_drop:
        logger.info(
            f"Price drop detected: {price_drop['name']!r} "
            f"${price_drop['old_price']:.2f} → ${price_drop['new_price']:.2f} "
            f"(-{price_drop['drop_pct']:.0%})",
            "price"
        )
    # Record current price for future comparison (always, win or lose)
    record_price(product)

    # ── Guard: dedup (1h hard block — prevents exact repeat within same session) ──
    if metrics.was_posted_within(product.get("siteUrl"), product.get("name"), hours=1):
        return _record({
            "success": False, "error": "Product already posted recently (dedup skip)",
            "product": product.get("name"), "productSource": product.get("source"),
        })

    # ── Phase 2: Caption (base — used when platform-specific fails or for single platform) ──
    trends = await get_trends()
    with Timer("caption_gen"):
        if price_drop:
            # Price-drop captions bypass the normal template to highlight the deal
            drop_product = {**product, "description": (
                f"PRICE DROP {price_drop['drop_pct']:.0%} OFF! "
                f"Was ${price_drop['old_price']:.2f}, now ${price_drop['new_price']:.2f}. "
                f"{product.get('description', '')}"
            )}
            caption = await ai_text.generate_post_text(drop_product, trends)
        else:
            caption = await ai_text.generate_post_text(product, trends)
    logger.info(f"Caption ({len(caption)} chars): {caption[:80]}…", "ai")

    # ── Phase 3: Image (non-blocking — failure is fine) ──
    # image_bytes → Bluesky / Mastodon / X (binary upload)
    # image_url   → Facebook / Instagram / Threads (need a public HTTPS URL)
    image, image_url = await _find_image(product)
    # If product already has a public imageUrl, prefer that for URL-based platforms
    image_url = image_url or product.get("imageUrl")

    # ── Phase 4: Tracking URL + A/B assignment ──
    deeplink = product.get("deeplink") or product.get("siteUrl") or ""
    if not deeplink:
        return _record({"success": False, "error": "Product has no URL"})
    tracking_id, redirect = _tracking_url(deeplink)

    # Assign A/B variant for this post — B gets a curiosity-hook caption style
    ab_variant = ab.assign_variant(tracking_id)
    if ab_variant == "B" and not price_drop:
        # Re-generate caption with variant B style injected via system prompt modifier
        variant_style = ab.get_variant_style("B")
        ab_product = {**product, "_ab_style": variant_style}
        caption = await ai_text.generate_post_text(ab_product, trends)
        logger.info(f"A/B variant B caption: {caption[:60]}…", "ab")
    logger.info(f"A/B variant: {ab_variant}", "ab")

    # ── Phase 5: Post to all enabled platforms ──
    recent_runs = metrics.get_recent_runs(500)
    uris = {}
    primary_uri = ""
    any_success = False
    # Pre-generate per-platform captions concurrently when posting to multiple platforms
    platform_captions: dict[str, str] = {}
    if len(platforms) > 1:
        async def _gen_caption(plat: str) -> None:
            c = await ai_text.generate_platform_caption(product, trends, platform=plat)
            platform_captions[plat] = c
        await asyncio.gather(*[_gen_caption(p) for p in platforms])

    for platform in platforms:
        plat_caption = platform_captions.get(platform, caption)
        # Anti-ban guardian: check daily limit, interval, and posting hours
        allowed, reason = check_allowed(platform, recent_runs)
        if not allowed:
            logger.info(f"Skipped by guardian: {reason}", platform)
            continue

        if platform == "bluesky":
            try:
                with Timer("bluesky_publish"):
                    uri = await post_to_bluesky(plat_caption, redirect, image, product)
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
                retry_queue.enqueue("bluesky", plat_caption, redirect, product, error=_msg)
        else:
            logger.info("Attempting post…", platform)
            uri = await post_to_platform(
                platform, plat_caption, redirect,
                image=image, image_url=image_url, product=product,
            )
            if uri:
                uris[platform] = uri
                primary_uri = primary_uri or uri
                any_success = True
                logger.info(f"Posted OK → {uri}", platform)
            else:
                logger.error("Post returned no URI — check connection in Accounts", platform)
                retry_queue.enqueue(platform, plat_caption, redirect, product,
                                    image_url=image_url, error="no URI returned")

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


# ── Retry runner (called every 15 minutes by APScheduler) ─────────────────────

async def retry_failed_posts() -> dict:
    """Re-attempt queued failed posts. Called on a 15-minute schedule."""
    due = retry_queue.get_due()
    if not due:
        return {"retried": 0, "succeeded": 0, "failed": 0}

    succeeded = 0
    failed = 0
    for entry in due:
        platform = entry["platform"]
        caption = entry["caption"]
        redirect = entry["redirect_url"]
        product = entry["product"]
        image_url = entry.get("image_url")

        try:
            if platform == "bluesky":
                uri = await post_to_bluesky(caption, redirect, None, product)
            else:
                uri = await post_to_platform(
                    platform, caption, redirect,
                    image=None, image_url=image_url, product=product,
                )
            if uri:
                logger.info(f"Retry succeeded → {uri}", f"retry:{platform}")
                retry_queue.mark_success(entry)
                succeeded += 1
            else:
                retry_queue.mark_failed(entry, error="no URI on retry")
                failed += 1
        except AuthError as e:
            # Permanent auth failure — drop from queue, no point retrying
            retry_queue.mark_failed(entry, error=f"auth:{e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            retry_queue.mark_failed(entry, error=str(e))
            failed += 1

    retry_queue.clear_expired()
    logger.info(f"Retry run: {len(due)} due, {succeeded} OK, {failed} failed", "retry")
    return {"retried": len(due), "succeeded": succeeded, "failed": failed}


# ── SLO calculation ──────────────────────────────────────────────────────────

SLO_TARGET = 90.0  # 90% — realistic for a bot posting hourly via third-party APIs
                   # 99.9% would deplete budget on any single transient failure

_SLO_MIN_RUNS = 5  # require at least this many runs before reporting error budget exhaustion

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
    # Do not report budget exhausted until we have a statistically meaningful run count.
    # A single startup failure (e.g. "No platforms configured") must not trigger HALT.
    if total < _SLO_MIN_RUNS:
        budget_consumed = min(budget_consumed, 99.9)  # never shows as fully exhausted
    return {
        "slo_pct": slo_pct,
        "slo_target": SLO_TARGET,
        "error_budget_remaining_pct": round(max(0.0, 100.0 - budget_consumed), 1),
        "error_budget_consumed_pct": round(min(100.0, budget_consumed), 1),
        "total": total,
        "success": success,
        "failures": total - success,
    }
