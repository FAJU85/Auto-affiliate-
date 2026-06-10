"""Post to social platforms using stored credentials from social-connections.json."""

import base64
import hashlib
import hmac
import json
import os
import secrets as _secrets
import time
import urllib.parse
from pathlib import Path

import httpx

from .utils import logger
from .utils.circuit_breaker import (
    mastodon_cb  as _mastodon_cb,
    x_cb         as _x_cb,
    threads_cb   as _threads_cb,
    tumblr_cb    as _tumblr_cb,
    facebook_cb  as _facebook_cb,
    instagram_cb as _instagram_cb,
)

DATA_DIR         = Path(os.environ.get("DATA_DIR", "/data"))
CONNECTIONS_FILE = DATA_DIR / "social-connections.json"
POST_TIMEOUT     = httpx.Timeout(connect=10, read=20, write=20, pool=5)


def _load_connections() -> dict:
    try:
        return json.loads(CONNECTIONS_FILE.read_text())
    except Exception:
        return {}


# ── OAuth 1.0a signing (RFC 5849 compliant) ─────────────────────────────────

def _pct(s: str) -> str:
    """Percent-encode per OAuth 1.0a — only unreserved chars are safe."""
    return urllib.parse.quote(str(s), safe="")   # safe="" → encodes everything including %


def _oauth1_sign(method: str, url: str, params: dict,
                 consumer_secret: str, token_secret: str) -> str:
    """Return base64 HMAC-SHA1 OAuth 1.0a signature."""
    # Step 1: build normalised parameter string
    param_str = "&".join(
        f"{_pct(k)}={_pct(v)}" for k, v in sorted(params.items())
    )
    # Step 2: build signature base string
    base_str = "&".join([
        _pct(method.upper()),
        _pct(url),
        _pct(param_str),
    ])
    # Step 3: signing key = percent-encoded consumer_secret & percent-encoded token_secret
    signing_key = f"{_pct(consumer_secret)}&{_pct(token_secret)}"
    sig = hmac.new(signing_key.encode(), base_str.encode(), hashlib.sha1).digest()
    return base64.b64encode(sig).decode()


def _oauth1_header(method: str, url: str, consumer_key: str, consumer_secret: str,
                   access_token: str, token_secret: str, extra_params: dict | None = None) -> str:
    ts    = str(int(time.time()))
    nonce = _secrets.token_hex(16)
    oauth_params: dict = {
        "oauth_consumer_key":     consumer_key,
        "oauth_nonce":            nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        ts,
        "oauth_token":            access_token,
        "oauth_version":          "1.0",
    }
    all_params = {**oauth_params, **(extra_params or {})}
    oauth_params["oauth_signature"] = _oauth1_sign(
        method, url, all_params, consumer_secret, token_secret
    )
    return "OAuth " + ", ".join(
        f'{k}="{_pct(v)}"' for k, v in sorted(oauth_params.items())
    )


# ── Platform posting functions ───────────────────────────────────────────────

_HASHTAG_MAP = [
    (["travel", "flight", "hotel", "airline", "travelpayouts", "vacation", "trip"], ["#travel", "#deals"]),
    (["fashion", "clothing", "apparel", "shoes", "dress", "shirt", "sneakers", "handbag"], ["#fashion", "#style"]),
    (["tech", "electronics", "laptop", "phone", "gadget", "camera", "earbuds", "smartwatch"], ["#TechDeals", "#Electronics"]),
    (["beauty", "skincare", "makeup", "cosmetics", "hair", "serum", "lipstick"], ["#beauty", "#selfcare"]),
    (["home", "furniture", "decor", "kitchen", "garden", "appliance"], ["#homedecor", "#deals"]),
    (["sport", "fitness", "gym", "outdoor", "running", "yoga", "workout"], ["#fitness", "#deals"]),
    (["pet", "dog", "cat", "animal", "bird"], ["#pets", "#deals"]),
    (["baby", "kids", "toy", "children", "nursery"], ["#kids", "#deals"]),
    (["health", "vitamin", "supplement", "wellness"], ["#health", "#wellness"]),
]

def _pick_hashtags(product: dict) -> list[str]:
    haystack = " ".join(filter(None, [product.get("source"), product.get("category"), product.get("name", "")])).lower()
    for keywords, tags in _HASHTAG_MAP:
        if any(k in haystack for k in keywords):
            return tags
    return ["#deals", "#shopping"]


async def _upload_mastodon_image(instance: str, auth_header: dict, image: bytes) -> str | None:
    """Upload image to Mastodon and return media_id, or None on failure.

    Uses /api/v2/media (async upload). Polls until processing completes (up to 15s).
    Note: to change the app label shown on posts ("Auto Affiliate Bot"), rename the
    OAuth app at {instance}/settings/applications in your Mastodon account settings.
    """
    import asyncio
    upload_timeout = httpx.Timeout(connect=10, read=60, write=60, pool=5)
    try:
        async with httpx.AsyncClient(timeout=upload_timeout) as client:
            r = await client.post(
                f"{instance}/api/v2/media",
                headers=auth_header,
                files={"file": ("product.jpg", image, "image/jpeg")},
                data={"description": "Product image"},
            )
        if r.status_code == 202:
            # Async processing — poll /api/v1/media/:id until ready
            media_id = r.json().get("id")
            if not media_id:
                return None
            async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
                for _ in range(6):  # up to ~15s
                    await asyncio.sleep(2.5)
                    poll = await client.get(f"{instance}/api/v1/media/{media_id}", headers=auth_header)
                    if poll.status_code == 200:
                        logger.info(f"Mastodon image ready: {media_id}", "mastodon")
                        return media_id
            logger.warn("Mastodon image processing timed out — posting without image", "mastodon")
            return None
        if r.status_code in (200, 201):
            media_id = r.json().get("id")
            logger.info(f"Mastodon image uploaded: {media_id}", "mastodon")
            return media_id
        logger.warn(f"Mastodon image upload HTTP {r.status_code}: {r.text[:200]}", "mastodon")
        return None
    except Exception as err:
        logger.warn(f"Mastodon image upload error (non-fatal): {err}", "mastodon")
        return None


async def _post_mastodon(caption: str, deeplink: str, image: bytes | None = None, product: dict | None = None) -> str:
    conns = _load_connections()
    c = conns.get("mastodon", {})
    if not c.get("connected") or not c.get("access_token"):
        raise RuntimeError("Mastodon not connected — add credentials in Accounts")

    instance     = c.get("instance", "https://mastodon.social").rstrip("/")
    access_token = c["access_token"]
    auth_header  = {"Authorization": f"Bearer {access_token}"}

    # The AI already embedded the CTA phrase inside the caption (chosen by product type).
    # We just add hashtags and the URL on separate lines.
    # mastodon.social is plain-text only — Mastodon auto-shortens any URL to 23 visible chars.
    hashtags = " ".join(_pick_hashtags(product or {}))

    # Format:
    #   {caption with AI-chosen CTA at the end}
    #
    #   {hashtags}
    #
    #   {tracking url}   ← shows as 23-char truncated link, fully clickable
    parts = [p for p in [caption, hashtags, deeplink] if p]
    text = "\n\n".join(parts)

    # Trim caption if needed (Mastodon counts URLs as 23 chars)
    url_chars = 23 if deeplink else 0
    visible = len(caption) + len(hashtags) + url_chars + 4  # 4 = 2 separators × 2
    if visible > 498:
        trim_to = max(0, 498 - len(hashtags) - url_chars - 8)
        caption = caption[:trim_to].rstrip() + "…"
        parts = [p for p in [caption, hashtags, deeplink] if p]
        text = "\n\n".join(parts)

    # Upload image
    media_ids = []
    if image:
        mid = await _upload_mastodon_image(instance, auth_header, image)
        if mid:
            media_ids = [mid]

    payload: dict = {"status": text, "visibility": "public"}
    if media_ids:
        payload["media_ids"] = media_ids

    async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
        r = await client.post(
            f"{instance}/api/v1/statuses",
            headers=auth_header,
            json=payload,
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    uri = r.json().get("url", "")
    logger.info(f"Posted {uri}", "mastodon")
    return uri


async def _upload_x_image(consumer_key: str, consumer_secret: str,
                          access_token: str, access_secret: str,
                          image: bytes) -> str | None:
    """Upload image to Twitter media upload endpoint, return media_id_string or None."""
    upload_url = "https://upload.twitter.com/1/media/upload.json"
    # Media upload uses multipart form — OAuth header must NOT include form params
    auth = _oauth1_header("POST", upload_url, consumer_key, consumer_secret, access_token, access_secret)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=60, write=60, pool=5)) as client:
            r = await client.post(
                upload_url,
                headers={"Authorization": auth},
                files={"media": ("image.jpg", image, "image/jpeg")},
            )
        if r.status_code in (200, 201):
            media_id = r.json().get("media_id_string")
            logger.info(f"X image uploaded: {media_id}", "x")
            return media_id
        logger.warn(f"X image upload HTTP {r.status_code}: {r.text[:200]} — posting without image", "x")
    except Exception as err:
        logger.warn(f"X image upload error (non-fatal): {err}", "x")
    return None


async def _post_x(caption: str, deeplink: str, image: bytes | None = None) -> str:
    conns = _load_connections()
    c = conns.get("x", {})
    if not c.get("connected"):
        raise RuntimeError("X (Twitter) not connected — add credentials in Accounts")

    consumer_key    = c.get("consumer_key", "")
    consumer_secret = c.get("consumer_secret", "")
    access_token    = c.get("access_token", "")
    access_secret   = c.get("access_secret", "")

    if not all([consumer_key, consumer_secret, access_token, access_secret]):
        raise RuntimeError("X credentials incomplete — add all 4 API keys in Accounts")

    text = f"{caption}\n{deeplink}" if deeplink else caption
    if len(text) > 280:
        text = text[:279] + "…"

    # Upload image first if provided
    media_id = None
    if image:
        media_id = await _upload_x_image(consumer_key, consumer_secret, access_token, access_secret, image)

    url    = "https://api.twitter.com/2/tweets"
    header = _oauth1_header("POST", url, consumer_key, consumer_secret, access_token, access_secret)
    body: dict = {"text": text}
    if media_id:
        body["media"] = {"media_ids": [media_id]}

    async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
        r = await client.post(
            url,
            headers={"Authorization": header, "Content-Type": "application/json"},
            json=body,
        )
    if r.status_code == 403:
        raise RuntimeError(
            "X post blocked (403) — app needs 'Read and Write' OAuth 1.0a permissions. "
            "Fix: developer.twitter.com → your app → Settings → User authentication settings → "
            "enable OAuth 1.0a with Read+Write → regenerate and re-enter your Access Token & Secret."
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    tweet_id = r.json().get("data", {}).get("id", "")
    handle   = c.get("handle", "").lstrip("@")
    uri = f"https://twitter.com/{handle}/status/{tweet_id}" if tweet_id else "https://twitter.com"
    logger.info(f"Posted {uri}", "x")
    return uri


async def _post_facebook(caption: str, deeplink: str, image_url: str | None = None) -> str:
    """Post to a Facebook Page via Graph API.

    Credentials stored in social-connections.json under 'facebook':
      page_id, page_access_token (long-lived page token), connected
    """
    conns = _load_connections()
    c = conns.get("facebook", {})
    if not c.get("connected") or not c.get("page_access_token"):
        raise RuntimeError("Facebook not connected — add Page Access Token in Accounts")

    page_id    = c.get("page_id", "me")
    page_token = c["page_access_token"]
    base       = "https://graph.facebook.com/v19.0"

    # Build post message: caption + CTA already in caption, append link for Facebook card
    message = f"{caption}\n\n{deeplink}" if deeplink else caption
    if len(message) > 2000:
        message = message[:1999] + "…"

    async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
        if image_url:
            # Photo post — includes image preview and message
            r = await client.post(f"{base}/{page_id}/photos", params={
                "url":          image_url,
                "message":      message,
                "access_token": page_token,
            })
        else:
            # Link post — Facebook generates a link preview card from the URL
            r = await client.post(f"{base}/{page_id}/feed", params={
                "message":      caption,
                "link":         deeplink or "",
                "access_token": page_token,
            })

    if r.status_code not in (200, 201):
        raise RuntimeError(f"Facebook API HTTP {r.status_code}: {r.text[:300]}")
    post_id = r.json().get("id", "")
    uri = f"https://facebook.com/{post_id}" if post_id else "https://facebook.com"
    logger.info(f"Posted {uri}", "facebook")
    return uri


async def _post_instagram(caption: str, deeplink: str, image_url: str | None = None) -> str:
    """Post to Instagram Business account via Meta Graph API.

    Credentials stored under 'instagram':
      ig_user_id, access_token (page token with instagram_content_publish scope)

    Instagram Graph API requires a PUBLIC image URL — binary upload is not supported.
    We use the product's original imageUrl (not our downloaded bytes).
    If no image URL is available, posts as a text-only Reel caption (not supported
    for feed — skipped with a warning).
    """
    conns = _load_connections()
    c = conns.get("instagram", {})
    if not c.get("connected") or not c.get("access_token"):
        raise RuntimeError("Instagram not connected — add credentials in Accounts")

    ig_user_id   = c.get("ig_user_id", "")
    access_token = c["access_token"]
    if not ig_user_id:
        raise RuntimeError("Instagram ig_user_id missing — reconnect in Accounts")

    if not image_url:
        raise RuntimeError(
            "Instagram feed posts require an image URL. "
            "No product image available for this product — skipping Instagram."
        )

    base = "https://graph.facebook.com/v19.0"
    full_caption = f"{caption}\n\n{deeplink}" if deeplink else caption
    if len(full_caption) > 2200:
        full_caption = full_caption[:2199] + "…"

    async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
        # Step 1: create media container
        r1 = await client.post(f"{base}/{ig_user_id}/media", params={
            "image_url":    image_url,
            "caption":      full_caption,
            "access_token": access_token,
        })
        if r1.status_code not in (200, 201):
            raise RuntimeError(f"Instagram container HTTP {r1.status_code}: {r1.text[:300]}")
        container_id = r1.json().get("id")
        if not container_id:
            raise RuntimeError(f"Instagram: no container id returned: {r1.text[:200]}")

        # Step 2: publish
        r2 = await client.post(f"{base}/{ig_user_id}/media_publish", params={
            "creation_id":  container_id,
            "access_token": access_token,
        })
        if r2.status_code not in (200, 201):
            raise RuntimeError(f"Instagram publish HTTP {r2.status_code}: {r2.text[:300]}")
        media_id = r2.json().get("id", "")

    handle = c.get("handle", "").lstrip("@")
    uri = f"https://instagram.com/p/{media_id}" if media_id else "https://instagram.com"
    logger.info(f"Posted {uri}", "instagram")
    return uri


async def _post_threads(caption: str, deeplink: str) -> str:
    conns = _load_connections()
    c = conns.get("threads", {})
    if not c.get("connected") or not c.get("access_token"):
        raise RuntimeError("Threads not connected — connect via OAuth in Accounts")

    access_token = c["access_token"]
    user_id      = c.get("user_id", "me")
    text         = f"{caption}\n{deeplink}" if deeplink else caption
    if len(text) > 500:
        text = text[:499] + "…"

    base = "https://graph.threads.net/v1.0"
    async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
        r = await client.post(f"{base}/{user_id}/threads", params={
            "media_type":   "TEXT",
            "text":         text,
            "access_token": access_token,
        })
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Threads container failed HTTP {r.status_code}: {r.text[:200]}")
        container_id = r.json().get("id")
        if not container_id:
            raise RuntimeError(f"Threads: no container id: {r.text[:200]}")

        r2 = await client.post(f"{base}/{user_id}/threads_publish", params={
            "creation_id":  container_id,
            "access_token": access_token,
        })
        if r2.status_code not in (200, 201):
            raise RuntimeError(f"Threads publish failed HTTP {r2.status_code}: {r2.text[:200]}")
        post_id = r2.json().get("id", "")

    handle = c.get("handle", "")
    uri = f"https://www.threads.net/@{handle}/post/{post_id}" if post_id and handle else "https://www.threads.net"
    logger.info(f"Posted {uri}", "threads")
    return uri


async def _post_tumblr(caption: str, deeplink: str) -> str:
    conns = _load_connections()
    c = conns.get("tumblr", {})
    if not c.get("connected") or not c.get("access_token"):
        raise RuntimeError("Tumblr not connected — connect via OAuth in Accounts")

    access_token = c["access_token"]
    blog_name    = c.get("handle", "")
    if not blog_name:
        raise RuntimeError("Tumblr handle/blog name missing — reconnect in Accounts")

    text = f"{caption}\n{deeplink}" if deeplink else caption

    async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
        r = await client.post(
            f"https://api.tumblr.com/v2/blog/{blog_name}/posts",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"content": [{"type": "text", "text": text}]},
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Tumblr post failed HTTP {r.status_code}: {r.text[:200]}")
    post_id = r.json().get("response", {}).get("id", "")
    uri = f"https://{blog_name}.tumblr.com/post/{post_id}" if post_id else f"https://{blog_name}.tumblr.com"
    logger.info(f"Posted {uri}", "tumblr")
    return uri


# ── Public dispatcher with circuit breakers ──────────────────────────────────

async def post_to_mastodon(caption: str, deeplink: str, image: bytes | None = None, product: dict | None = None) -> str:
    return await _mastodon_cb.call(_post_mastodon, caption, deeplink, image, product)


async def post_to_x(caption: str, deeplink: str, image: bytes | None = None) -> str:
    return await _x_cb.call(_post_x, caption, deeplink, image)


async def post_to_facebook(caption: str, deeplink: str, image_url: str | None = None) -> str:
    return await _facebook_cb.call(_post_facebook, caption, deeplink, image_url)


async def post_to_instagram(caption: str, deeplink: str, image_url: str | None = None) -> str:
    return await _instagram_cb.call(_post_instagram, caption, deeplink, image_url)


async def post_to_threads(caption: str, deeplink: str) -> str:
    return await _threads_cb.call(_post_threads, caption, deeplink)


async def post_to_tumblr(caption: str, deeplink: str) -> str:
    return await _tumblr_cb.call(_post_tumblr, caption, deeplink)


async def post_to_platform(platform: str, caption: str, deeplink: str,
                           image: bytes | None = None, product: dict | None = None) -> str | None:
    """Post to a single platform. Returns URI on success, logs and returns None on failure."""
    try:
        if platform == "mastodon":
            return await post_to_mastodon(caption, deeplink, image, product)
        if platform == "x":
            return await post_to_x(caption, deeplink, image)
        if platform == "threads":
            return await post_to_threads(caption, deeplink)
        if platform == "tumblr":
            return await post_to_tumblr(caption, deeplink)
        if platform == "facebook":
            image_url = (product or {}).get("imageUrl")
            return await post_to_facebook(caption, deeplink, image_url)
        if platform == "instagram":
            image_url = (product or {}).get("imageUrl")
            return await post_to_instagram(caption, deeplink, image_url)
        logger.warn("Unknown platform — skipping", platform)
        return None
    except RuntimeError as err:
        if "Circuit breaker" in str(err):
            logger.warn(f"Circuit breaker open — skipping until recovery: {err}", platform)
        else:
            logger.error(f"Post failed: {err}", platform)
        return None
    except Exception as err:
        logger.error(f"Post failed: {err}", platform)
        return None
