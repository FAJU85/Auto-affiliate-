"""Affiliate link click tracking stored in /data/clicks.json."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CLICKS_FILE = DATA_DIR / "clicks.json"
MAX_CLICKS = 10_000


def _load() -> list:
    try:
        return json.loads(CLICKS_FILE.read_text())
    except Exception:
        return []


def _save(data: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(CLICKS_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(CLICKS_FILE)


def record_click(
    product_name: str,
    url: str,
    platform: str = "unknown",
    source: str = "unknown",
) -> dict:
    """Append a click event and return it."""
    event = {
        "id": uuid.uuid4().hex,
        "product_name": product_name,
        "url": url,
        "platform": platform,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    clicks = _load()
    clicks.append(event)
    # Prune to last MAX_CLICKS
    if len(clicks) > MAX_CLICKS:
        clicks = clicks[-MAX_CLICKS:]
    _save(clicks)
    return event


def get_clicks(limit: int = 100) -> list:
    """Return last `limit` clicks, most recent first."""
    clicks = _load()
    return list(reversed(clicks[-limit:])) if clicks else []


def clicks_today() -> int:
    """Count of clicks recorded today (UTC date)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sum(1 for c in _load() if str(c.get("timestamp", ""))[:10] == today)


def clicks_summary() -> dict:
    """Return {total, today, by_platform, by_source}."""
    clicks = _load()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    by_platform: dict = {}
    by_source: dict = {}
    today_count = 0
    for c in clicks:
        p = c.get("platform", "unknown")
        s = c.get("source", "unknown")
        by_platform[p] = by_platform.get(p, 0) + 1
        by_source[s] = by_source.get(s, 0) + 1
        if str(c.get("timestamp", ""))[:10] == today:
            today_count += 1
    return {
        "total": len(clicks),
        "today": today_count,
        "by_platform": by_platform,
        "by_source": by_source,
    }
