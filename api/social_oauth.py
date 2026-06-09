"""FastAPI backend for the affiliate-posting bot (HuggingFace Spaces, port 7860)."""

import csv
import io
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter()

DASHBOARD = Path(__file__).resolve().parent.parent / "src" / "dashboard.html"

# Env vars surfaced in /api/debug and used to compute setup warnings.
ENV_KEYS = [
    "BSKY_HANDLE", "BSKY_APP_PASSWORD", "SOVRN_API_KEY", "GROQ_API_KEY",
    "MISTRAL_API_KEY", "ADMITAD_CLIENT_ID", "TAKEADS_API_KEY",
    "TRAVELPAYOUTS_TOKEN", "SPACE_HOST", "CRON_SCHEDULE",
]
REQUIRED_VARS = ["BSKY_HANDLE", "BSKY_APP_PASSWORD"]

NETWORKS = [
    {"key": "sovrn", "name": "SOVRN Commerce", "env": "SOVRN_API_KEY"},
    {"key": "admitad", "name": "Admitad", "env": "ADMITAD_CLIENT_ID"},
    {"key": "takeads", "name": "TakeAds", "env": "TAKEADS_API_KEY"},
    {"key": "travelpayouts", "name": "Travelpayouts", "env": "TRAVELPAYOUTS_TOKEN"},
]

scheduler = AsyncIOScheduler(timezone="UTC")


def save_states(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(OAUTH_STATE_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(OAUTH_STATE_FILE)

def get_base_url() -> str:
    host = os.environ.get("SPACE_HOST", "")
    if not host:
        space_id = os.environ.get("SPACE_ID", "")
        if space_id:
            host = f"https://{space_id.replace('/', '-')}"
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

@router.post("/social/threads/callback")
async def threads_callback(code: str, state: str):
    client_id = os.environ.get("THREADS_APP_ID", "")
    client_secret = os.environ.get("THREADS_APP_SECRET", "")
    base = get_base_url()
    callback = f"{base}/oauth/social/callback?platform=threads"

def _next_run() -> str | None:
    job = scheduler.get_job("pipeline")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    _schedule_job()
    scheduler.start()
    logger.info(f"Scheduler started (cron={_cron()})")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Affiliate Bot", lifespan=lifespan)

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


@router.post("/social/tumblr/callback")
async def tumblr_callback(code: str, state: str):
    client_id     = os.environ.get("TUMBLR_CLIENT_ID", "")
    client_secret = os.environ.get("TUMBLR_CLIENT_SECRET", "")
    base = get_base_url()
    callback = f"{base}/oauth/social/callback?platform=tumblr"

@app.get("/", response_class=HTMLResponse)
async def home():
    if DASHBOARD.exists():
        return FileResponse(str(DASHBOARD))
    return HTMLResponse("<h1>Affiliate Bot</h1><p>Dashboard not found.</p>")

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
    return {"ok": True, "status": "healthy"}


# ── Status & stats ──────────────────────────────────────────────────────────

def _missing_vars() -> list:
    return [v for v in REQUIRED_VARS if not os.environ.get(v)]


def _stats() -> dict:
    runs = metrics.get_recent_runs(500)
    total = len(runs)
    success = sum(1 for r in runs if r.get("success"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    posts_today = sum(
        1 for r in runs if r.get("success") and str(r.get("timestamp", "")).startswith(today)
    )
    s = settings.get_settings()
    return {
        "totalRuns": total,
        "successRate": round(success / total * 100) if total else None,
        "postsToday": posts_today,
        "maxPostsPerDay": int(s.get("postsPerDay", 1)) * 24,
    }


@app.get("/api/status")
async def status():
    s = settings.get_settings()
    cap = float(s.get("dailyCostCap", 2.0))
    return {
        "pipeline": {
            "running": pipeline.STATE["running"],
            "paused": pipeline.STATE["paused"],
            "schedule": _cron(),
            "nextRun": None if pipeline.STATE["paused"] else _next_run(),
            "lastRun": pipeline.STATE["lastRun"],
        },
        "budget": {"spent": round(budget.get_daily_spend(), 4), "cap": cap},
        "stats": _stats(),
        "runs": metrics.get_recent_runs(20),
        "missingVars": _missing_vars(),
    }


@app.get("/api/stats")
async def stats(days: int = 7):
    runs = metrics.get_recent_runs(500)
    by_day: dict = defaultdict(lambda: {"date": "", "byNetwork": defaultdict(int)})
    for r in runs:
        if not r.get("success"):
            continue
        day = str(r.get("timestamp", ""))[:10]
        if not day:
            continue
        by_day[day]["date"] = day
        by_day[day]["byNetwork"][r.get("productSource") or "unknown"] += 1
    out = [
        {"date": d["date"], "byNetwork": dict(d["byNetwork"])}
        for d in by_day.values()
    ]
    out.sort(key=lambda x: x["date"])
    return out[-days:]


# ── Actions ─────────────────────────────────────────────────────────────────

@app.post("/api/run")
async def run():
    if pipeline.STATE["running"]:
        return {"ok": False, "error": "Pipeline already running"}
    import asyncio
    asyncio.create_task(pipeline.run_pipeline())
    return {"ok": True}


@app.post("/api/dry-run")
async def dry_run():
    return await pipeline.dry_run()


@app.post("/api/schedule/pause")
async def pause():
    pipeline.STATE["paused"] = True
    scheduler.pause()
    return {"ok": True, "paused": True}


@app.post("/api/schedule/resume")
async def resume():
    pipeline.STATE["paused"] = False
    scheduler.resume()
    return {"ok": True, "paused": False}


@app.get("/api/schedule/config")
async def schedule_config():
    return {"cron": _cron(), "nextRun": _next_run(), "paused": pipeline.STATE["paused"]}


# ── Logs & debug ────────────────────────────────────────────────────────────

@app.get("/api/logs")
async def logs(n: int = 100):
    return metrics_logs(n)


def metrics_logs(n: int) -> list:
    return logger.get_recent_logs(n)


@app.get("/api/debug")
async def debug():
    last = pipeline.STATE["lastRun"]
    recent_errors = [
        {"ts": r.get("timestamp"), "error": r.get("error")}
        for r in metrics.get_recent_runs(50) if r.get("error")
    ][-10:]
    return {
        "env": {k: bool(os.environ.get(k)) for k in ENV_KEYS},
        "networks": [
            {"key": n["key"], "enabled": bool(os.environ.get(n["env"]))}
            for n in NETWORKS
        ],
        "spaceHost": settings.get_space_host(),
        "lastRun": last,
        "recentErrors": recent_errors,
    }


@app.get("/api/env")
async def env_status():
    return {k: bool(os.environ.get(k)) for k in ENV_KEYS}


# ── Settings ────────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings_route():
    return settings.get_settings()


@app.post("/api/settings")
async def post_settings(request: Request):
    try:
        body = await request.json()
        saved = settings.save_settings(body)
        if "cronSchedule" in body:
            _schedule_job()
        return {"ok": True, "settings": saved}
    except Exception as err:  # noqa: BLE001
        return {"ok": False, "error": str(err)}


# ── Accounts & networks ─────────────────────────────────────────────────────

@app.get("/api/accounts")
async def accounts():
    connected = bool(os.environ.get("BSKY_HANDLE") and os.environ.get("BSKY_APP_PASSWORD"))
    return {
        "bluesky": {
            "connected": connected,
            "handle": os.environ.get("BSKY_HANDLE", ""),
            "method": "app-password",
        }
    }


@app.post("/api/accounts/bluesky/disconnect")
async def disconnect_bluesky():
    return {"ok": True, "note": "Bluesky uses env credentials; clear them in Space settings."}


@app.get("/api/networks")
async def networks():
    return [
        {"key": n["key"], "name": n["name"], "enabled": bool(os.environ.get(n["env"]))}
        for n in NETWORKS
    ]


@app.get("/api/network/test")
async def network_test(network: str = ""):
    found = next((n for n in NETWORKS if n["key"] == network), None)
    if not found:
        return {"ok": False, "error": "Unknown network"}
    enabled = bool(os.environ.get(found["env"]))
    return {"ok": enabled, "network": network, "enabled": enabled}


# ── History & clicks ────────────────────────────────────────────────────────

@app.get("/api/history")
async def history(n: int = 100):
    return metrics.get_recent_runs(n)


@app.get("/api/history.csv", response_class=PlainTextResponse)
async def history_csv(n: int = 500):
    runs = metrics.get_recent_runs(n)
    buf = io.StringIO()
    cols = ["timestamp", "success", "product", "productSource", "captionChars",
            "clicks", "postUri", "error"]
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for r in runs:
        writer.writerow(r)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


@app.get("/api/clicks")
async def clicks(days: int = 30):
    runs = metrics.get_recent_runs(500)
    by_day: dict = defaultdict(lambda: {"posts": 0, "clicks": 0})
    for r in runs:
        day = str(r.get("timestamp", ""))[:10]
        if not day:
            continue
        if r.get("success"):
            by_day[day]["posts"] += 1
        by_day[day]["clicks"] += int(r.get("clicks", 0))
    daily = []
    for day in sorted(by_day):
        d = by_day[day]
        ctr = round(d["clicks"] / d["posts"], 2) if d["posts"] else 0
        daily.append({"date": day, "posts": d["posts"], "clicks": d["clicks"], "ctr": ctr})
    daily = daily[-days:]
    return {"daily": daily, "total": metrics.get_total_clicks()}


# ── Dedup ───────────────────────────────────────────────────────────────────

@app.get("/api/dedup/stats")
async def dedup_stats():
    return {**metrics.get_dedup_status(), "bySource": metrics.get_dedup_by_source()}


@app.post("/api/dedup/reset")
async def dedup_reset():
    cleared = metrics.clear_posted_store()
    return {"ok": True, "cleared": cleared}


# ── Insights ────────────────────────────────────────────────────────────────

@app.get("/api/insights")
async def insights():
    return {
        "networkHealth": metrics.get_network_health(100),
        "dedup": metrics.get_dedup_status(),
        "totalClicks": metrics.get_total_clicks(),
    }


# ── AI generation ───────────────────────────────────────────────────────────

@app.post("/api/ai/generate")
async def ai_generate(request: Request):
    body = await request.json()
    product = {
        "name": body.get("productName", "this product"),
        "category": body.get("category", "general"),
        "description": body.get("description", ""),
    }
    text = await ai_text.generate_post_text(product, [])
    return {"text": text, "seoScore": None, "seoGrade": None}


# ── Redirect tracking ───────────────────────────────────────────────────────

@app.get("/r/{tracking_id}")
async def redirect(tracking_id: str):
    metrics.record_click(tracking_id)
    target = pipeline.resolve_redirect(tracking_id)
    if target:
        return RedirectResponse(target, status_code=302)
    return RedirectResponse("/", status_code=302)
