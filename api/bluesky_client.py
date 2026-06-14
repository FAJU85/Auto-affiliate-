"""Bluesky posting via direct AT Protocol HTTP calls (async httpx).

No threads, no locks — pure async with explicit per-call timeouts.

Env: BSKY_HANDLE, BSKY_APP_PASSWORD
"""

import asyncio
import json
import os
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .utils import logger
from .utils.circuit_breaker import bluesky_cb
from .utils.telemetry import Timer, record_saturation

BSKY_API        = "https://bsky.social/xrpc"
GRAPHEME_LIMIT  = 300
CONNECT_TIMEOUT = 10   # seconds — TCP handshake
READ_TIMEOUT    = 20   # seconds — waiting for response bytes
MAX_RETRIES     = 3
SESSION_TTL     = 80 * 60  # 80 minutes — refresh before Bluesky access token expires (1h)

_TIMEOUT = httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT,
                          write=READ_TIMEOUT, pool=5)

DATA_DIR      = Path(os.environ.get("DATA_DIR", "/data"))
SESSION_FILE  = DATA_DIR / "bsky-session.json"
RATELIMIT_FILE = DATA_DIR / "bsky-ratelimit.json"

# In-memory session cache: {accessJwt, did, expiry}
_session: dict = {}


# ── Persistent rate-limit guard ──────────────────────────────────────────────

def _save_ratelimit(reset_ts: float) -> None:
    """Persist the rate-limit reset timestamp so restarts respect it."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        RATELIMIT_FILE.write_text(json.dumps({"reset": reset_ts}))
    except Exception:
        pass

def _clear_ratelimit() -> None:
    try:
        RATELIMIT_FILE.unlink(missing_ok=True)
    except Exception:
        pass

def _ratelimit_until() -> float:
    """Return the epoch when the rate limit clears, or 0 if not limited."""
    try:
        data = json.loads(RATELIMIT_FILE.read_text())
        reset = float(data.get("reset", 0))
        if reset > time.time():
            return reset
        _clear_ratelimit()
    except Exception:
        pass
    return 0.0

def get_ratelimit_reset() -> float:
    """Public: return rate-limit reset epoch (0 = not limited)."""
    return _ratelimit_until()


# ── Session management ───────────────────────────────────────────────────────

def _load_cached_session() -> dict | None:
    if _session.get("expiry", 0) > time.time():
        return _session
    try:
        data = json.loads(SESSION_FILE.read_text())
        if data.get("expiry", 0) > time.time():
            _session.update(data)
            return _session
    except Exception:
        pass
    return None


def _save_session(access_jwt: str, did: str) -> None:
    expiry = time.time() + SESSION_TTL
    _session.update({"accessJwt": access_jwt, "did": did, "expiry": expiry})
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(json.dumps(_session))
    except Exception as err:
        logger.warn(f"Bluesky session save failed: {err}")


def _clear_session() -> None:
    _session.clear()
    try:
        SESSION_FILE.unlink(missing_ok=True)
    except Exception:
        pass


async def _get_session(handle: str, password: str) -> tuple[str, str]:
    """Return (access_jwt, did), logging in if needed."""
    cached = _load_cached_session()
    if cached:
        logger.info(f"Bluesky: reusing session for @{handle}")
        return cached["accessJwt"], cached["did"]

    # Check persistent rate-limit guard before attempting login
    rl_until = _ratelimit_until()
    if rl_until:
        reset_dt = datetime.fromtimestamp(rl_until, tz=timezone.utc)
        wait_s = int(rl_until - time.time())
        raise RuntimeError(
            f"Bluesky login blocked — rate limit active until "
            f"{reset_dt.strftime('%H:%M:%S')} UTC ({wait_s}s remaining). "
            f"No login will be attempted until then."
        )

    logger.info(f"Bluesky: logging in as @{handle}")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        with Timer("bluesky_login"):
            r = await client.post(
                f"{BSKY_API}/com.atproto.server.createSession",
                json={"identifier": handle, "password": password},
            )
    if r.status_code == 429:
        # Parse reset time and persist it so restarts respect the limit
        reset_ts_hdr = r.headers.get("RateLimit-Reset") or r.headers.get("X-RateLimit-Reset")
        retry_after  = int(r.headers.get("Retry-After", 300))
        reset_epoch  = float(reset_ts_hdr) if reset_ts_hdr else time.time() + retry_after
        _save_ratelimit(reset_epoch)
        reset_dt = datetime.fromtimestamp(reset_epoch, tz=timezone.utc)
        raise RuntimeError(
            f"Bluesky createSession rate-limited (429) — "
            f"too many login attempts. Resets at {reset_dt.strftime('%H:%M:%S')} UTC. "
            f"Login blocked automatically until then."
        )
    if r.status_code != 200:
        body = r.text[:300]
        raise RuntimeError(
            f"Bluesky login failed HTTP {r.status_code} — "
            f"check BSKY_HANDLE and BSKY_APP_PASSWORD in Space Secrets. Response: {body}"
        )
    data = r.json()
    access_jwt = data["accessJwt"]
    did = data["did"]
    _save_session(access_jwt, did)
    _clear_ratelimit()  # successful login — remove any stale rate limit guard
    logger.info(f"Bluesky: authenticated as @{handle} (did={did})")
    return access_jwt, did


# ── Grapheme helpers ─────────────────────────────────────────────────────────

def _grapheme_len(s: str) -> int:
    try:
        import regex  # type: ignore
        return len(regex.findall(r"\X", s))
    except ImportError:
        pass
    count = 0
    for ch in s:
        if unicodedata.category(ch) not in ("Mn", "Mc", "Me"):
            count += 1
    return count


def _truncate_graphemes(text: str, limit: int) -> str:
    try:
        import regex  # type: ignore
        clusters = regex.findall(r"\X", text)
    except ImportError:
        clusters = [ch for ch in text if unicodedata.category(ch) not in ("Mn", "Mc", "Me")]
    if len(clusters) <= limit:
        return text
    return "".join(clusters[:limit])


def _build_post_text(caption: str, deeplink: str) -> str:
    """Fit caption + deeplink within GRAPHEME_LIMIT. Deeplink is always preserved."""
    link_part = f"\n{deeplink}" if deeplink else ""
    link_graphemes = _grapheme_len(link_part)
    caption_budget = GRAPHEME_LIMIT - link_graphemes
    truncated = _truncate_graphemes(caption.strip(), max(0, caption_budget - 1))
    if len(caption.strip()) > caption_budget:
        truncated = truncated.rstrip() + "…"
    return truncated + link_part


# ── Facets ───────────────────────────────────────────────────────────────────

def _link_facets(full_text: str, deeplink: str) -> list:
    if not deeplink:
        return []
    raw = full_text.encode("utf-8")
    target = deeplink.encode("utf-8")
    start = raw.find(target)
    if start < 0:
        return []
    return [{
        "$type": "app.bsky.richtext.facet",
        "index": {"byteStart": start, "byteEnd": start + len(target)},
        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": deeplink}],
    }]


def _build_post_with_cta_link(caption: str, deeplink: str) -> tuple[str, list]:
    """Build post text + facets for Bluesky.

    If the caption contains a CTA phrase from settings, that phrase becomes the
    clickable link (no raw URL shown in the post — URL is hidden behind the CTA text).
    Falls back to appending the raw URL with a standard facet if no CTA phrase found.

    This is the Bluesky-native way to do "End Hair Loss Today 🔗" as a hyperlink.
    """
    from .utils.settings import get_settings
    cta_phrases: list[str] = get_settings().get("ctaPhrases") or []

    if deeplink and cta_phrases:
        text = _truncate_graphemes(caption.strip(), GRAPHEME_LIMIT)
        raw = text.encode("utf-8")
        for phrase in cta_phrases:
            encoded = phrase.strip().encode("utf-8")
            if not encoded:
                continue
            start = raw.find(encoded)
            if start >= 0:
                facet = [{
                    "$type": "app.bsky.richtext.facet",
                    "index": {"byteStart": start, "byteEnd": start + len(encoded)},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": deeplink}],
                }]
                logger.info(f"Bluesky: CTA facet '{phrase.strip()}' → {deeplink[:50]}")
                return text, facet

    # No CTA phrase found in caption — fallback: append raw URL
    full_text = _build_post_text(caption, deeplink)
    return full_text, _link_facets(full_text, deeplink)


# ── Image upload ─────────────────────────────────────────────────────────────

async def _upload_image(access_jwt: str, image_bytes: bytes) -> dict | None:
    if not image_bytes or len(image_bytes) > 1_000_000:
        if image_bytes:
            logger.warn(f"Bluesky: image too large ({len(image_bytes)} bytes) — skipping")
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{BSKY_API}/com.atproto.repo.uploadBlob",
                headers={
                    "Authorization": f"Bearer {access_jwt}",
                    "Content-Type": "image/jpeg",
                },
                content=image_bytes,
            )
        if r.status_code == 200:
            return r.json()["blob"]
        logger.warn(f"Bluesky blob upload HTTP {r.status_code} — skipping image")
    except Exception as err:
        logger.warn(f"Bluesky image upload failed (non-fatal): {err}")
    return None


# ── Core async post ───────────────────────────────────────────────────────────

def _bsky_credentials() -> tuple[str, str]:
    """Return (handle, password) — env vars take priority, then social-connections.json."""
    handle   = (os.environ.get("BSKY_HANDLE",        "") or "").strip()
    password = (os.environ.get("BSKY_APP_PASSWORD", "") or "").strip()
    if not handle or not password:
        import json as _json
        conn_file = Path(os.environ.get("DATA_DIR", "/data")) / "social-connections.json"
        try:
            conns = _json.loads(conn_file.read_text()) if conn_file.exists() else {}
            bsky = conns.get("bluesky", {})
            handle   = handle   or (bsky.get("handle")   or "").strip()
            password = password or (bsky.get("password") or "").strip()
        except Exception:
            pass
    return handle, password


async def _post_async(caption: str, deeplink: str, image_bytes: bytes | None, product: dict) -> str:
    handle, password = _bsky_credentials()
    if not handle or not password:
        raise RuntimeError(
            "Bluesky credentials missing — enter them in Accounts → Bluesky or set "
            "BSKY_HANDLE and BSKY_APP_PASSWORD in Space Secrets"
        )

    access_jwt, did = await _get_session(handle, password)

    full_text, facets = _build_post_with_cta_link(caption, deeplink)

    embed = None
    if image_bytes:
        blob = await _upload_image(access_jwt, image_bytes)
        if blob:
            embed = {
                "$type": "app.bsky.embed.images",
                "images": [{
                    "image": blob,
                    "alt": product.get("name", "Product image")[:300],
                }],
            }

    record: dict = {
        "$type": "app.bsky.feed.post",
        "text": full_text,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if facets:
        record["facets"] = facets
    if embed:
        record["embed"] = embed

    logger.info(f"Bluesky: posting as @{handle} ({len(full_text)} graphemes)")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        with Timer("bluesky_post"):
            r = await client.post(
                f"{BSKY_API}/com.atproto.repo.createRecord",
                headers={"Authorization": f"Bearer {access_jwt}"},
                json={"repo": did, "collection": "app.bsky.feed.post", "record": record},
            )

    if r.status_code != 200:
        body = r.text[:300]
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 60))
            raise RuntimeError(f"Bluesky posting rate-limited (429) — wait {retry_after}s")
        if r.status_code in (401, 403):
            _clear_session()
        raise RuntimeError(f"Bluesky createRecord HTTP {r.status_code}: {body}")

    uri = r.json()["uri"]
    logger.info(f"Bluesky: posted {uri}")
    return uri


# ── Public API with circuit breaker + retry ──────────────────────────────────

async def post_to_bluesky(
    caption: str,
    deeplink: str,
    image_bytes: bytes | None,
    product: dict,
) -> str:
    """Post to Bluesky. Circuit breaker + up to 3 retries with back-off."""

    last_err: Exception = RuntimeError("No attempt made")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with Timer("bluesky_total"):
                uri = await bluesky_cb.call(_post_async, caption, deeplink, image_bytes, product)
            return uri
        except asyncio.TimeoutError:
            last_err = TimeoutError(f"Bluesky timed out on attempt {attempt}")
            logger.warn(str(last_err))
        except RuntimeError as e:
            if "Circuit breaker" in str(e):
                raise
            last_err = e
            msg = str(e).lower()
            if "rate-limited" in msg or "429" in msg:
                # Don't keep retrying — we'll just deepen the rate limit hole
                logger.warn(f"Bluesky rate-limited on attempt {attempt} — aborting retries: {e}")
                raise
            if "401" in msg or "403" in msg or "unauthorized" in msg:
                _clear_session()
            logger.warn(f"Bluesky attempt {attempt} failed: {e}")
        except Exception as e:  # noqa: BLE001
            last_err = e
            msg = str(e).lower()
            if "rate" in msg or "429" in msg:
                record_saturation("bluesky")
                wait = 60 * attempt
                logger.warn(f"Bluesky rate-limited — waiting {wait}s")
                await asyncio.sleep(wait)
            elif any(x in msg for x in ("expired", "revoked", "deleted", "unauthorized")):
                _clear_session()
                logger.warn(f"Bluesky auth error — session cleared: {e}")
            else:
                logger.warn(f"Bluesky attempt {attempt} failed: {e}")

        if attempt < MAX_RETRIES:
            await asyncio.sleep(2 ** attempt)

    raise last_err
