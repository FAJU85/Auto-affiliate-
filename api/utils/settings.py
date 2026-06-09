"""Settings persistence in /data/settings.json with sane defaults."""

import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULTS = {
    "spaceHost": "",
    "cronSchedule": "0 * * * *",
    "maxPostLength": 300,
    "dailyCostCap": 2.00,
    "alertThreshold": 1.50,
    "rateLimitWaitMs": 120000,
    "postingHours": "8-22",
    "postsPerDay": 1,
    "schedulerEnabled": True,
    "postSystemPrompt": (
        "Write a short, persuasive affiliate post for social media. Max 200 chars. "
        "Use power words (deal, save, exclusive, limited). Natural, conversational tone. "
        "Do not include URLs or hashtags — those are added automatically."
    ),
    "postUserTemplate": (
        'Product: "{name}" ({category}). Description: {description}. Price: {price}. '
        "Trending topic: {trend}. Write a punchy post with a clear CTA. No URLs, no hashtags."
    ),
}

_cache: dict | None = None


def get_settings() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        raw = json.loads(SETTINGS_FILE.read_text())
        _cache = {**DEFAULTS, **raw}
    except Exception:
        _cache = dict(DEFAULTS)
    return _cache


def _write(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(SETTINGS_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(SETTINGS_FILE)


def save_settings(updates: dict) -> dict:
    global _cache
    current = get_settings()
    _cache = {**current, **updates}
    _write(_cache)
    return _cache


def get_space_host() -> str:
    host = os.environ.get("SPACE_HOST", "")
    if not host:
        space_id = os.environ.get("SPACE_ID", "")
        if space_id:
            host = f"https://{space_id.replace('/', '-')}.hf.space"
    if host and not host.startswith("http"):
        host = "https://" + host
    return host.rstrip("/")
