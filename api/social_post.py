"""Post to social platforms using stored credentials from social-connections.json."""

import json
import os
from pathlib import Path

import httpx

from .utils import logger

DATA_DIR         = Path(os.environ.get("DATA_DIR", "/data"))
CONNECTIONS_FILE = DATA_DIR / "social-connections.json"
POST_TIMEOUT     = httpx.Timeout(connect=10, read=20, write=20, pool=5)


def _load_connections() -> dict:
    try:
        return json.loads(CONNECTIONS_FILE.read_text())
    except Exception:
        return {}


async def post_to_mastodon(caption: str, deeplink: str) -> str:
    conns = _load_connections()
    c = conns.get("mastodon", {})
    if not c.get("connected") or not c.get("access_token"):
        raise RuntimeError("Mastodon not connected — add credentials in Accounts")

    instance     = c.get("instance", "https://mastodon.social").rstrip("/")
    access_token = c["access_token"]
    text         = f"{caption}\n{deeplink}" if deeplink else caption
    if len(text) > 500:
        text = text[:499] + "…"

    async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
        r = await client.post(
            f"{instance}/api/v1/statuses",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"status": text, "visibility": "public"},
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Mastodon post failed HTTP {r.status_code}: {r.text[:200]}")
    uri = r.json().get("url", "")
    logger.info(f"Mastodon: posted {uri}")
    return uri


async def post_to_x(caption: str, deeplink: str) -> str:
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

    # OAuth 1.0a signing
    import time, hmac, hashlib, urllib.parse, base64, secrets as _secrets

    def _sign(method, url, params, oauth_params):
        all_params = {**params, **oauth_params}
        base = "&".join([
            urllib.parse.quote(method.upper(), safe=""),
            urllib.parse.quote(url, safe=""),
            urllib.parse.quote("&".join(f"{urllib.parse.quote(k,safe='%')}"
                                        f"={urllib.parse.quote(str(v),safe='%')}"
                                        for k, v in sorted(all_params.items())), safe=""),
        ])
        key = f"{urllib.parse.quote(consumer_secret,safe='%')}&{urllib.parse.quote(access_secret,safe='%')}"
        return base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()

    url = "https://api.twitter.com/2/tweets"
    ts  = str(int(time.time()))
    nonce = _secrets.token_hex(16)
    oauth = {
        "oauth_consumer_key":     consumer_key,
        "oauth_nonce":            nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp":        ts,
        "oauth_token":            access_token,
        "oauth_version":          "1.0",
    }
    oauth["oauth_signature"] = _sign("POST", url, {}, oauth)
    auth_header = "OAuth " + ", ".join(f'{k}="{urllib.parse.quote(str(v),safe="")}"'
                                        for k, v in sorted(oauth.items()))

    async with httpx.AsyncClient(timeout=POST_TIMEOUT) as client:
        r = await client.post(url,
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
            json={"text": text},
        )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"X post failed HTTP {r.status_code}: {r.text[:200]}")
    tweet_id = r.json().get("data", {}).get("id", "")
    handle   = c.get("handle", "").lstrip("@")
    uri = f"https://twitter.com/{handle}/status/{tweet_id}" if tweet_id else "https://twitter.com"
    logger.info(f"X: posted {uri}")
    return uri


async def post_to_platform(platform: str, caption: str, deeplink: str) -> str | None:
    """Post to a single platform. Returns URI on success, logs and returns None on failure."""
    try:
        if platform == "mastodon":
            return await post_to_mastodon(caption, deeplink)
        if platform == "x":
            return await post_to_x(caption, deeplink)
        # Threads, Tumblr, Facebook, Instagram — credentials stored but posting not yet implemented
        logger.warn(f"{platform}: posting not yet implemented — skipping")
        return None
    except Exception as err:
        logger.warn(f"{platform} post failed (non-fatal): {err}")
        return None
