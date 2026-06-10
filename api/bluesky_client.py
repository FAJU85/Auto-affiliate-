"""Bluesky posting via the atproto library (app-password login).

Env: BSKY_HANDLE, BSKY_APP_PASSWORD

Reliability:
  - Circuit breaker: opens after 3 consecutive failures, recovers after 5 min
  - Retry: up to 3 attempts with exponential back-off
  - Timeout: 30 s on login + post
  - Grapheme-safe truncation: always preserves the deeplink
"""

import asyncio
import json
import os
import socket
import threading
import time
import unicodedata
from pathlib import Path

from atproto import Client, models

from .utils import logger
from .utils.circuit_breaker import bluesky_cb
from .utils.telemetry import Timer, record_saturation

GRAPHEME_LIMIT  = 300
LOGIN_TIMEOUT   = 20   # seconds
POST_TIMEOUT    = 20   # seconds
LOCK_TIMEOUT    = 25   # seconds — fail fast if a previous thread holds the lock (stuck network call)
MAX_RETRIES     = 3
SESSION_TTL     = 90 * 60  # 90 minutes — refresh before Bluesky access token expires

# Cap all blocking socket calls at the OS level so atproto's login never hangs indefinitely.
socket.setdefaulttimeout(LOGIN_TIMEOUT + 2)

DATA_DIR        = Path(os.environ.get("DATA_DIR", "/data"))
SESSION_FILE    = DATA_DIR / "bsky-session.json"

_session_lock   = threading.Lock()
_cached_client: Client | None = None
_session_expiry: float = 0.0


def _save_session(client: Client) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        sess = client.export_session_string()
        SESSION_FILE.write_text(json.dumps({"session": sess, "ts": time.time()}))
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Bluesky session save failed: {err}")


def _load_session() -> str | None:
    try:
        data = json.loads(SESSION_FILE.read_text())
        age = time.time() - float(data.get("ts", 0))
        if age < SESSION_TTL:
            return data.get("session")
    except Exception:
        pass
    return None


def _invalidate_session() -> None:
    global _cached_client, _session_expiry
    _cached_client = None
    _session_expiry = 0.0
    try:
        SESSION_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _get_or_create_client(handle: str, password: str) -> Client:
    """Return a live Client, reusing a saved session when possible."""
    global _cached_client, _session_expiry

    if not _session_lock.acquire(timeout=LOCK_TIMEOUT):
        # A previous thread is still in a blocking network call — fail fast rather than deadlock
        logger.warn("Bluesky: session lock timed out — previous login attempt is still running")
        raise RuntimeError(
            f"Bluesky session lock timed out after {LOCK_TIMEOUT}s — "
            "a previous login is still running. Try again shortly."
        )
    try:
        if _cached_client is not None and time.time() < _session_expiry:
            logger.info("Bluesky: reusing in-memory session")
            return _cached_client

        client = Client()

        # Try resuming a persisted session first — avoids createSession rate limit
        saved = _load_session()
        if saved:
            try:
                with Timer("bluesky_resume"):
                    client.login(session_string=saved)
                _cached_client = client
                _session_expiry = time.time() + SESSION_TTL
                logger.info(f"Bluesky: resumed persisted session for @{handle}")
                return client
            except Exception as err:
                logger.warn(f"Bluesky: session resume failed ({err}) — re-logging in")
                try:
                    SESSION_FILE.unlink(missing_ok=True)
                except Exception:
                    pass

        # Full login
        logger.info(f"Bluesky: full login for @{handle}")
        with Timer("bluesky_login"):
            client.login(handle, password)
        _save_session(client)
        _cached_client = client
        _session_expiry = time.time() + SESSION_TTL
        logger.info(f"Bluesky: authenticated as @{handle}")
        return client
    finally:
        _session_lock.release()


# ── Grapheme helpers ─────────────────────────────────────────────────────────

def _grapheme_len(s: str) -> int:
    """Count Unicode grapheme clusters using unicodedata (no extra deps)."""
    # Approximate: count non-combining characters (close enough for ASCII + emoji)
    try:
        import regex  # type: ignore  # optional fast path
        return len(regex.findall(r"\X", s))
    except ImportError:
        pass
    # Fallback: strip combining marks and count
    count = 0
    for ch in s:
        if unicodedata.category(ch) not in ("Mn", "Mc", "Me"):
            count += 1
    return count


def _truncate_graphemes(text: str, limit: int) -> str:
    """Truncate `text` to at most `limit` graphemes."""
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
    truncated_caption = _truncate_graphemes(caption.strip(), max(0, caption_budget - 1))
    if len(caption.strip()) > caption_budget:
        truncated_caption = truncated_caption.rstrip() + "…"
    return truncated_caption + link_part


# ── Facets ───────────────────────────────────────────────────────────────────

def _link_facets(full_text: str, deeplink: str) -> list | None:
    if not deeplink:
        return None
    raw = full_text.encode("utf-8")
    target = deeplink.encode("utf-8")
    start = raw.find(target)
    if start < 0:
        return None
    return [
        models.AppBskyRichtextFacet.Main(
            index=models.AppBskyRichtextFacet.ByteSlice(
                byte_start=start, byte_end=start + len(target)
            ),
            features=[models.AppBskyRichtextFacet.Link(uri=deeplink)],
        )
    ]


# ── Image embed ──────────────────────────────────────────────────────────────

def _build_embed(client: Client, image_bytes: bytes | None, product: dict):
    if not image_bytes:
        return None
    if len(image_bytes) > 1_000_000:
        logger.warn(f"Bluesky image too large ({len(image_bytes)} bytes) — skipping")
        return None
    try:
        upload = client.upload_blob(image_bytes)
        alt = product.get("name", "Product image")[:280]
        return models.AppBskyEmbedImages.Main(
            images=[models.AppBskyEmbedImages.Image(alt=alt, image=upload.blob)]
        )
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Bluesky image upload failed: {err}")
        return None


# ── Core sync post (runs in thread pool) ─────────────────────────────────────

def _post_sync(caption: str, deeplink: str, image_bytes: bytes | None, product: dict) -> str:
    handle   = (os.environ.get("BSKY_HANDLE",        "") or "").strip()
    password = (os.environ.get("BSKY_APP_PASSWORD", "") or "").strip()
    if not handle or not password:
        raise RuntimeError(
            "Bluesky credentials missing — set BSKY_HANDLE and BSKY_APP_PASSWORD "
            f"in Space Secrets (BSKY_HANDLE {'set' if handle else 'MISSING'}, "
            f"BSKY_APP_PASSWORD {'set' if password else 'MISSING'})"
        )

    client = _get_or_create_client(handle, password)

    full_text = _build_post_text(caption, deeplink)
    facets    = _link_facets(full_text, deeplink)
    embed     = _build_embed(client, image_bytes, product)

    logger.info(f"Posting to Bluesky as @{handle}: {len(full_text)} chars")
    with Timer("bluesky_post"):
        response = client.send_post(text=full_text, facets=facets, embed=embed)

    uri = response.uri
    logger.info(f"Posted to Bluesky: {uri}")
    return uri


# ── Public async API ─────────────────────────────────────────────────────────

async def post_to_bluesky(
    caption: str,
    deeplink: str,
    image_bytes: bytes | None,
    product: dict,
) -> str:
    """Post to Bluesky with circuit breaker + retry."""

    async def _attempt() -> str:
        return await asyncio.wait_for(
            asyncio.to_thread(_post_sync, caption, deeplink, image_bytes, product),
            timeout=LOGIN_TIMEOUT + POST_TIMEOUT,
        )

    last_err: Exception = RuntimeError("No attempt made")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with Timer("bluesky_total") as t:
                uri = await bluesky_cb.call(_attempt)
            return uri
        except asyncio.TimeoutError as e:
            last_err = TimeoutError(f"Bluesky timed out on attempt {attempt}")
            logger.warn(str(last_err))
        except RuntimeError as e:
            # Circuit breaker open — don't retry
            if "Circuit breaker" in str(e):
                raise
            last_err = e
            logger.warn(f"Bluesky attempt {attempt} failed: {e}")
        except Exception as e:  # noqa: BLE001
            last_err = e
            msg = str(e).lower()
            if "rate" in msg or "429" in msg:
                record_saturation("bluesky")
                wait = 60 * attempt
                logger.warn(f"Bluesky rate-limited — waiting {wait}s")
                await asyncio.sleep(wait)
            elif any(x in msg for x in ("expired", "revoked", "deleted", "unauthorized", "401")):
                logger.warn(f"Bluesky auth error — invalidating session: {e}")
                _invalidate_session()
            else:
                logger.warn(f"Bluesky attempt {attempt} failed: {e}")

        if attempt < MAX_RETRIES:
            await asyncio.sleep(2 ** attempt)  # 2s, 4s

    raise last_err
