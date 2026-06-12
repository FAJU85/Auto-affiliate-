"""Anti-ban platform guardian — enforces per-platform daily limits, intervals,
posting hours, hashtag caps, and FTC disclosure.

Rules are based on 2026 platform policies. All limits are conservative —
well below platform hard caps to avoid triggering spam classifiers.

Key rules per platform:
  Twitter/X  : 3/day, 2h interval, max 2 hashtags, #ad required, bio bot-label
  Bluesky    : 6/day, 90min interval, max 3 hashtags, #ad required
  Threads    : 6/day, 90min interval, MAX 1 HASHTAG (API hard limit), #ad required
  Facebook   : 3/day, 30min interval, max 3 hashtags, #ad required
  Instagram  : 3/day, 2h interval, max 20 hashtags, #ad required
  Mastodon   : 4/day, 2h interval, max 4 hashtags, #ad required
  Tumblr     : 4/day, 90min interval, max 10 hashtags, #ad required
"""

from datetime import datetime, timezone

# ── Per-platform rules ────────────────────────────────────────────────────────
# daily_limit       : max posts per calendar day (UTC)
# min_interval_min  : minimum minutes between consecutive posts to this platform
# max_hashtags      : hard cap — trim silently if over
# posting_hours     : (start_hour, end_hour) UTC inclusive range — skip outside
# disclosure_tag    : FTC-compliant tag appended to every post

RULES: dict[str, dict] = {
    "bluesky": {
        "daily_limit":        6,
        "min_interval_min":  90,
        "max_hashtags":       3,
        "posting_hours":   (7, 23),
        "disclosure_tag":  "#ad",
    },
    "mastodon": {
        "daily_limit":        4,
        "min_interval_min": 120,
        "max_hashtags":       4,
        "posting_hours":   (8, 22),
        "disclosure_tag":  "#ad",
    },
    "x": {
        "daily_limit":        3,    # Free tier ~17/day; 3 is very safe
        "min_interval_min": 120,
        "max_hashtags":       2,
        "posting_hours":   (8, 22),
        "disclosure_tag":  "#ad",
    },
    "threads": {
        "daily_limit":        6,
        "min_interval_min":  90,
        "max_hashtags":       1,    # Threads API hard limit — DO NOT increase
        "posting_hours":   (7, 23),
        "disclosure_tag":  "#ad",
    },
    "facebook": {
        "daily_limit":        3,    # Hard cap is 25; 3 for quality + safety
        "min_interval_min":  30,    # Platform recommends 20 min; use 30
        "max_hashtags":       3,
        "posting_hours":   (8, 21),
        "disclosure_tag":  "#ad",
    },
    "instagram": {
        "daily_limit":        3,
        "min_interval_min": 120,
        "max_hashtags":      20,    # Official limit 30; use 20 for safety
        "posting_hours":   (8, 21),
        "disclosure_tag":  "#ad",
    },
    "tumblr": {
        "daily_limit":        4,
        "min_interval_min":  90,
        "max_hashtags":      10,
        "posting_hours":   (8, 22),
        "disclosure_tag":  "#ad",
    },
}

_FALLBACK = {
    "daily_limit": 4,
    "min_interval_min": 90,
    "max_hashtags": 5,
    "posting_hours": (8, 22),
    "disclosure_tag": "#ad",
}


def get_rules(platform: str) -> dict:
    return RULES.get(platform, _FALLBACK)


def check_allowed(platform: str, recent_runs: list) -> tuple[bool, str]:
    """Check whether it's safe to post to this platform right now.

    Returns (allowed: bool, reason: str).
    recent_runs: list of run dicts from metrics.get_recent_runs().
    """
    rules = get_rules(platform)
    now = datetime.now(timezone.utc)

    # 1. Posting hours guard
    h_start, h_end = rules["posting_hours"]
    if not (h_start <= now.hour < h_end):
        return False, f"outside posting hours ({h_start}:00–{h_end}:00 UTC, now {now.hour}:00)"

    # 2. Collect timestamps of previous successful posts to this platform
    platform_times: list[datetime] = []
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for run in recent_runs:
        if not run.get("success"):
            continue
        if platform not in run.get("platforms", []):
            continue
        try:
            ts = datetime.fromisoformat(run["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            platform_times.append(ts)
        except Exception:
            continue

    # 3. Daily limit
    posts_today = sum(1 for t in platform_times if t >= today_start)
    daily_limit = rules["daily_limit"]
    if posts_today >= daily_limit:
        return False, f"daily limit reached ({posts_today}/{daily_limit} posts today)"

    # 4. Minimum interval
    if platform_times:
        last_post = max(platform_times)
        elapsed_min = (now - last_post).total_seconds() / 60
        min_interval = rules["min_interval_min"]
        if elapsed_min < min_interval:
            wait_min = int(min_interval - elapsed_min)
            return False, f"too soon — wait {wait_min}m more (min interval: {min_interval}m)"

    return True, "ok"


def enforce_hashtags(hashtags: list[str], platform: str) -> list[str]:
    """Trim hashtag list to this platform's maximum. Silently drops excess."""
    limit = get_rules(platform)["max_hashtags"]
    return hashtags[:limit]


def disclosure_tag(platform: str) -> str:
    """Return the FTC-required disclosure tag for this platform."""
    return get_rules(platform).get("disclosure_tag", "#ad")


def all_rules_summary() -> list[dict]:
    """Return all platform rules for display in the dashboard."""
    return [
        {
            "platform": p,
            "dailyLimit": r["daily_limit"],
            "minIntervalMin": r["min_interval_min"],
            "maxHashtags": r["max_hashtags"],
            "postingHours": f"{r['posting_hours'][0]:02d}:00–{r['posting_hours'][1]:02d}:00 UTC",
            "disclosureTag": r["disclosure_tag"],
        }
        for p, r in RULES.items()
    ]
