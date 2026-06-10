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
    "mastodon":  {"name": "Mastodon",    "icon": "🐘", "auth": "oauth2",      "needs_instance": True},
    "threads":   {"name": "Threads",     "icon": "🧵", "auth": "oauth2"},
    "tumblr":    {"name": "Tumblr",      "icon": "📝", "auth": "oauth2"},
    "x":         {"name": "X (Twitter)", "icon": "𝕏",  "auth": "credentials"},
    "facebook":  {"name": "Facebook",    "icon": "📘", "auth": "credentials"},
    "instagram": {"name": "Instagram",   "icon": "📸", "auth": "credentials"},
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
    raw = body.get("instance", "").strip().rstrip("/")
    platform = body.get("platform", "mastodon")
    if not raw:
        raise HTTPException(400, "instance URL required")

    # Strip any path/username — keep only scheme + host
    # e.g. https://mastodon.social/@user  →  https://mastodon.social
    from urllib.parse import urlparse
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    instance = f"{parsed.scheme}://{parsed.netloc}"
    if not parsed.netloc:
        raise HTTPException(400, f"Could not parse instance URL: {raw}")

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

# ── Credentials store (X, Facebook, Instagram) ────────────────────────────────

@router.post("/social/{platform}/credentials")
async def store_credentials(platform: str, request: Request):
    if platform not in PLATFORMS:
        raise HTTPException(404, "Unknown platform")
    if PLATFORMS[platform].get("auth") != "credentials":
        raise HTTPException(400, "This platform uses OAuth, not credentials")

    body = await request.json()
    handle = body.get("handle", "")
    if not handle:
        raise HTTPException(400, "handle required")

    conns = load_connections()
    entry: dict = {"connected": True, "handle": handle, "connectedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ")}

    if platform == "x":
        entry["consumer_key"]    = body.get("consumer_key", "")
        entry["consumer_secret"] = body.get("consumer_secret", "")
        entry["access_token"]    = body.get("access_token", "")
        entry["access_secret"]   = body.get("access_secret", "")
    else:
        entry["password"] = body.get("password", "")

    conns[platform] = entry
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

    if platform == "mastodon":
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

# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"ok": True}
