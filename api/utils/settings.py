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
    "publishPlatforms": ["bluesky"],
    "postSystemPrompt": (
        "You are a Bluesky social media copywriter. "
        "Write ONE short affiliate post in ENGLISH ONLY. "
        "Rules: max 200 characters, no markdown (no **, no ##), no emojis unless essential, "
        "no hashtags, no URLs, no ALL CAPS words, conversational tone, one clear call-to-action. "
        "Reply with only the post text — nothing else."
    ),
    "postUserTemplate": (
        'Write a Bluesky post for this product in English: "{name}" — {category}, priced at {price}. '
        "Keep it under 200 characters. One sentence. No markdown, no hashtags, no URLs."
    ),
}

_cache: dict | None = None


def _prompt_looks_broken(prompt: str) -> bool:
    """True if the prompt was clearly saved in a bad state."""
    if not prompt or len(prompt) < 20:
        return True
    # Very short generic prompts from old defaults
    if prompt.strip() in ("Write a short affiliate post.", "{name}"):
        return True
    return False


def get_settings() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        raw = json.loads(SETTINGS_FILE.read_text())
        # Reset prompts to current defaults if they look broken/stale
        if _prompt_looks_broken(raw.get("postSystemPrompt", "")):
            raw.pop("postSystemPrompt", None)
        if _prompt_looks_broken(raw.get("postUserTemplate", "")):
            raw.pop("postUserTemplate", None)
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
