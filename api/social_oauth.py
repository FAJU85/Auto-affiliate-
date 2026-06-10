"""
Social media OAuth backend — FastAPI on port 8000 (internal).
Node.js proxies /api/social/* → http://localhost:8000/social/*
"""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter()

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CONNECTIONS_FILE = DATA_DIR / "social-connections.json"
OAUTH_STATE_FILE = DATA_DIR / "oauth-states.json"

# ── Persistence helpers ────────────────────────────────────────────────────────

def load_connections() -> dict:
    try:
        return json.loads(CONNECTIONS_FILE.read_text())
    except Exception:
        return {}

def save_connections(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(CONNECTIONS_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(CONNECTIONS_FILE)

def load_states() -> dict:
    try:
        return json.loads(OAUTH_STATE_FILE.read_text())
    except Exception:
        return {}

_OAUTH_STATE_TTL = 600  # 10 minutes — enough for any OAuth flow

def save_states(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Prune expired states before saving
    cutoff = time.time() - _OAUTH_STATE_TTL
    data = {k: v for k, v in data.items() if float(v.get("ts", 0)) > cutoff}
    tmp = str(OAUTH_STATE_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(OAUTH_STATE_FILE)

def get_base_url() -> str:
    host = os.environ.get("SPACE_HOST", "")
    if not host:
        space_id = os.environ.get("SPACE_ID", "")
        if space_id:
            # SPACE_ID is "owner/space-name" → "owner-space-name.hf.space"
            host = f"https://{space_id.replace('/', '-')}.hf.space"
    if host and not host.startswith("http"):
        host = "https://" + host
    return host.rstrip("/")

# ── Platform registry ──────────────────────────────────────────────────────────

PLATFORMS = {
    "mastodon":     {"name": "Mastodon",      "icon": "🐘", "auth": "oauth2",   "needs_instance": True},
    "threads":      {"name": "Threads",        "icon": "🧵", "auth": "oauth2"},
    "tumblr":       {"name": "Tumblr",         "icon": "📝", "auth": "oauth2"},
    "plurk":        {"name": "Plurk",          "icon": "📣", "auth": "oauth1"},
    "nostr":        {"name": "Nostr",          "icon": "⚡", "auth": "keypair"},
    "truth_social": {"name": "Truth Social",   "icon": "🇺🇸", "auth": "mastodon", "needs_instance": True, "default_instance": "https://truthsocial.com"},
    "counter":      {"name": "CounterSocial",  "icon": "🛡️", "auth": "mastodon", "needs_instance": True, "default_instance": "https://counter.social"},
    "pillowfort":   {"name": "Pillowfort",     "icon": "🐾", "auth": "credentials"},
    "squabblr":     {"name": "Squabblr",       "icon": "💬", "auth": "credentials"},
    "spill":        {"name": "Spill",          "icon": "🫗",  "auth": "credentials"},
    "substack":     {"name": "Substack",       "icon": "📰", "auth": "credentials"},
    "semble":       {"name": "Semble",         "icon": "🔗", "auth": "credentials"},
}

# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/social/status")
async def status():
    conns = load_connections()
    result = {}
    for key, meta in PLATFORMS.items():
        c = conns.get(key, {})
        result[key] = {
            "name":      meta["name"],
            "icon":      meta["icon"],
            "auth":      meta["auth"],
            "connected": bool(c.get("connected")),
            "handle":    c.get("handle"),
            "instance":  c.get("instance"),
            "connectedAt": c.get("connectedAt"),
        }
    return result

@router.delete("/social/{platform}/disconnect")
async def disconnect(platform: str):
    if platform not in PLATFORMS:
        raise HTTPException(404, "Unknown platform")
    conns = load_connections()
    conns.pop(platform, None)
    save_connections(conns)
    return {"ok": True}

# ── Mastodon-compatible OAuth2 (Mastodon, Truth Social, CounterSocial) ─────────

@router.post("/social/mastodon/register")
async def mastodon_register(request: Request):
    """Register an OAuth app on the Mastodon instance and return auth URL."""
    body = await request.json()
    instance = body.get("instance", "").rstrip("/")
    platform = body.get("platform", "mastodon")
    if not instance:
        raise HTTPException(400, "instance URL required")

    base = get_base_url()
    if not base:
        raise HTTPException(503, "SPACE_HOST not configured")

    callback = f"{base}/oauth/social/callback?platform={platform}"

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{instance}/api/v1/apps", data={
            "client_name":   "Auto Affiliate Bot",
            "redirect_uris": callback,
            "scopes":        "read write",
            "website":       base,
        })
        if r.status_code not in (200, 201):
            raise HTTPException(502, f"Mastodon app registration failed: {r.text[:200]}")
        app_data = r.json()

    state = secrets.token_urlsafe(24)
    states = load_states()
    states[state] = {
        "platform":      platform,
        "instance":      instance,
        "client_id":     app_data["client_id"],
        "client_secret": app_data["client_secret"],
        "callback":      callback,
        "ts":            time.time(),
    }
    save_states(states)

    auth_url = (
        f"{instance}/oauth/authorize"
        f"?client_id={app_data['client_id']}"
        f"&redirect_uri={callback}"
        f"&response_type=code"
        f"&scope=read+write"
        f"&state={state}"
    )
    return {"url": auth_url, "state": state}

# ── Threads (Meta) OAuth2 ──────────────────────────────────────────────────────

@router.get("/social/threads/auth")
async def threads_auth():
    client_id = os.environ.get("THREADS_APP_ID", "")
    if not client_id:
        raise HTTPException(503, "THREADS_APP_ID not set")
    base = get_base_url()
    if not base:
        raise HTTPException(503, "SPACE_HOST not configured")

    callback = f"{base}/oauth/social/callback?platform=threads"
    state = secrets.token_urlsafe(24)
    states = load_states()
    states[state] = {"platform": "threads", "ts": time.time()}
    save_states(states)

    auth_url = (
        "https://www.threads.net/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={callback}"
        f"&scope=threads_basic,threads_content_publish"
        f"&response_type=code"
        f"&state={state}"
    )
    return {"url": auth_url}

@router.post("/social/threads/callback")
async def threads_callback(code: str, state: str):
    client_id = os.environ.get("THREADS_APP_ID", "")
    client_secret = os.environ.get("THREADS_APP_SECRET", "")
    base = get_base_url()
    callback = f"{base}/oauth/social/callback?platform=threads"

    async with httpx.AsyncClient() as client:
        r = await client.post("https://graph.threads.net/oauth/access_token", data={
            "client_id":     client_id,
            "client_secret": client_secret,
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  callback,
        })
        token_data = r.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(502, f"No access_token: {token_data}")

    async with httpx.AsyncClient() as client:
        me = (await client.get(
            "https://graph.threads.net/v1.0/me",
            params={"fields": "id,username", "access_token": access_token}
        )).json()

    conns = load_connections()
    conns["threads"] = {
        "connected":     True,
        "handle":        me.get("username", me.get("id", "")),
        "access_token":  access_token,
        "user_id":       me.get("id", ""),
        "connectedAt":   time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_connections(conns)
    return {"ok": True, "handle": conns["threads"]["handle"]}

# ── Tumblr OAuth2 ──────────────────────────────────────────────────────────────

@router.get("/social/tumblr/auth")
async def tumblr_auth():
    client_id = os.environ.get("TUMBLR_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(503, "TUMBLR_CLIENT_ID not set")
    base = get_base_url()
    callback = f"{base}/oauth/social/callback?platform=tumblr"
    state = secrets.token_urlsafe(24)
    states = load_states()
    states[state] = {"platform": "tumblr", "ts": time.time()}
    save_states(states)

    auth_url = (
        "https://www.tumblr.com/oauth2/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={callback}"
        f"&response_type=code"
        f"&scope=write"
        f"&state={state}"
    )
    return {"url": auth_url}

@router.post("/social/tumblr/callback")
async def tumblr_callback(code: str, state: str):
    client_id     = os.environ.get("TUMBLR_CLIENT_ID", "")
    client_secret = os.environ.get("TUMBLR_CLIENT_SECRET", "")
    base = get_base_url()
    callback = f"{base}/oauth/social/callback?platform=tumblr"

    async with httpx.AsyncClient() as client:
        r = await client.post("https://api.tumblr.com/v2/oauth2/token", data={
            "grant_type":    "authorization_code",
            "code":          code,
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  callback,
        })
        token_data = r.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(502, f"No access_token: {token_data}")

    async with httpx.AsyncClient() as client:
        me = (await client.get(
            "https://api.tumblr.com/v2/user/info",
            headers={"Authorization": f"Bearer {access_token}"}
        )).json()

    handle = me.get("response", {}).get("user", {}).get("name", "")
    conns = load_connections()
    conns["tumblr"] = {
        "connected":      True,
        "handle":         handle,
        "access_token":   access_token,
        "refresh_token":  token_data.get("refresh_token", ""),
        "connectedAt":    time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_connections(conns)
    return {"ok": True, "handle": handle}

# ── Nostr (keypair) ────────────────────────────────────────────────────────────

@router.post("/social/nostr/connect")
async def nostr_connect(request: Request):
    body = await request.json()
    nsec = body.get("nsec", "").strip()
    npub = body.get("npub", "").strip()
    if not nsec:
        raise HTTPException(400, "nsec (private key) required")

    conns = load_connections()
    conns["nostr"] = {
        "connected":   True,
        "handle":      npub or "nostr",
        "nsec":        nsec,
        "connectedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_connections(conns)
    return {"ok": True}

# ── Credentials store (Pillowfort, Squabblr, Spill, Substack, Semble) ─────────

@router.post("/social/{platform}/credentials")
async def store_credentials(platform: str, request: Request):
    if platform not in PLATFORMS:
        raise HTTPException(404, "Unknown platform")
    if PLATFORMS[platform]["auth"] != "credentials":
        raise HTTPException(400, "This platform uses OAuth, not credentials")

    body = await request.json()
    handle   = body.get("handle", "")
    password = body.get("password", "")
    if not handle:
        raise HTTPException(400, "handle required")

    conns = load_connections()
    conns[platform] = {
        "connected":   True,
        "handle":      handle,
        "password":    password,
        "connectedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_connections(conns)
    return {"ok": True, "handle": handle}

# ── Unified OAuth callback (called from Node.js /oauth/social/callback) ────────

@router.get("/social/callback")
async def oauth_callback(
    platform: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    if error:
        return JSONResponse({"ok": False, "error": error})
    if not code or not state:
        return JSONResponse({"ok": False, "error": "Missing code or state"})

    states = load_states()
    state_data = states.pop(state, None)
    if not state_data:
        return JSONResponse({"ok": False, "error": "Invalid or expired state"})
    save_states(states)

    if platform in ("mastodon", "truth_social", "counter"):
        return await _mastodon_complete(platform, code, state_data)
    elif platform == "threads":
        return await threads_callback(code, state)
    elif platform == "tumblr":
        return await tumblr_callback(code, state)
    else:
        return JSONResponse({"ok": False, "error": f"Unknown platform: {platform}"})

async def _mastodon_complete(platform: str, code: str, state_data: dict):
    instance      = state_data["instance"]
    client_id     = state_data["client_id"]
    client_secret = state_data["client_secret"]
    callback      = state_data["callback"]

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{instance}/oauth/token", data={
            "client_id":     client_id,
            "client_secret": client_secret,
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  callback,
            "scope":         "read write",
        })
        token_data = r.json()

    access_token = token_data.get("access_token")
    if not access_token:
        return JSONResponse({"ok": False, "error": f"No token: {token_data}"})

    async with httpx.AsyncClient(timeout=10) as client:
        me = (await client.get(
            f"{instance}/api/v1/accounts/verify_credentials",
            headers={"Authorization": f"Bearer {access_token}"}
        )).json()

    conns = load_connections()
    conns[platform] = {
        "connected":     True,
        "handle":        me.get("acct", me.get("username", "")),
        "instance":      instance,
        "access_token":  access_token,
        "client_id":     client_id,
        "client_secret": client_secret,
        "connectedAt":   time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_connections(conns)
    return {"ok": True, "handle": conns[platform]["handle"]}

# ── Plurk OAuth1 ───────────────────────────────────────────────────────────────

@router.get("/social/plurk/auth")
async def plurk_auth():
    consumer_key    = os.environ.get("PLURK_CONSUMER_KEY", "")
    consumer_secret = os.environ.get("PLURK_CONSUMER_SECRET", "")
    if not consumer_key:
        raise HTTPException(503, "PLURK_CONSUMER_KEY not set")
    base = get_base_url()
    callback = f"{base}/oauth/social/callback?platform=plurk"

    from requests_oauthlib import OAuth1Session
    oauth = OAuth1Session(consumer_key, client_secret=consumer_secret, callback_uri=callback)
    fetch_response = oauth.fetch_request_token("https://www.plurk.com/OAuth/request_token")
    resource_owner_key    = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")

    states = load_states()
    temp_state = secrets.token_urlsafe(16)
    states[resource_owner_key] = {
        "platform":              "plurk",
        "resource_owner_key":    resource_owner_key,
        "resource_owner_secret": resource_owner_secret,
        "temp_state":            temp_state,
        "ts":                    time.time(),
    }
    save_states(states)

    auth_url = f"https://www.plurk.com/OAuth/authorize?oauth_token={resource_owner_key}"
    return {"url": auth_url}

@router.post("/social/plurk/callback")
async def plurk_callback(oauth_token: str, oauth_verifier: str):
    consumer_key    = os.environ.get("PLURK_CONSUMER_KEY", "")
    consumer_secret = os.environ.get("PLURK_CONSUMER_SECRET", "")

    states = load_states()
    state_data = states.pop(oauth_token, None)
    if not state_data:
        raise HTTPException(400, "Invalid OAuth token")
    save_states(states)

    from requests_oauthlib import OAuth1Session
    oauth = OAuth1Session(
        consumer_key, client_secret=consumer_secret,
        resource_owner_key=state_data["resource_owner_key"],
        resource_owner_secret=state_data["resource_owner_secret"],
        verifier=oauth_verifier,
    )
    tokens = oauth.fetch_access_token("https://www.plurk.com/OAuth/access_token")

    oauth2 = OAuth1Session(
        consumer_key, client_secret=consumer_secret,
        resource_owner_key=tokens["oauth_token"],
        resource_owner_secret=tokens["oauth_token_secret"],
    )
    me = oauth2.get("https://www.plurk.com/APP/Users/me").json()
    handle = me.get("nick_name", me.get("display_name", ""))

    conns = load_connections()
    conns["plurk"] = {
        "connected":             True,
        "handle":                handle,
        "oauth_token":           tokens["oauth_token"],
        "oauth_token_secret":    tokens["oauth_token_secret"],
        "connectedAt":           time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_connections(conns)
    return {"ok": True, "handle": handle}

# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"ok": True}
