"""Per-affiliate-feed health tracking in /data/feed_health.json.

Tracks success/failure rate and product counts for each feed,
surfacing health status (healthy / degraded / down).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
FEED_HEALTH_FILE = DATA_DIR / "feed_health.json"

MAX_ENTRIES = 100


def _load() -> dict:
    try:
        return json.loads(FEED_HEALTH_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(FEED_HEALTH_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(FEED_HEALTH_FILE)


def record_feed_result(feed_name: str, success: bool, product_count: int = 0) -> None:
    """Append a result entry for a feed; prune to last MAX_ENTRIES per feed."""
    data = _load()
    entries = data.get(feed_name, [])
    entries.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "product_count": product_count,
        }
    )
    # Keep rolling window
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]
    data[feed_name] = entries
    _save(data)


def feed_health(feed_name: str, window: int = 20) -> dict:
    """Return health stats for a single feed over the last `window` entries."""
    data = _load()
    entries = data.get(feed_name, [])
    window_entries = entries[-window:] if entries else []

    total_calls = len(window_entries)
    successes = sum(1 for e in window_entries if e["success"])
    failures = total_calls - successes
    success_rate_pct = (successes / total_calls * 100) if total_calls > 0 else 0.0
    avg_products = (
        sum(e["product_count"] for e in window_entries) / total_calls
        if total_calls > 0
        else 0.0
    )
    last_called = entries[-1]["timestamp"] if entries else None

    if success_rate_pct >= 80:
        status = "healthy"
    elif success_rate_pct >= 50:
        status = "degraded"
    else:
        status = "down"

    return {
        "feed_name": feed_name,
        "total_calls": total_calls,
        "successes": successes,
        "failures": failures,
        "success_rate_pct": round(success_rate_pct, 1),
        "avg_products": round(avg_products, 2),
        "last_called": last_called,
        "status": status,
    }


def all_feeds_health(window: int = 20) -> list:
    """Return health stats for all feeds that have recorded data."""
    data = _load()
    return [feed_health(name, window=window) for name in data]


def is_feed_healthy(feed_name: str, window: int = 20) -> bool:
    """Return True if the feed is healthy or degraded (not down)."""
    return feed_health(feed_name, window=window)["status"] != "down"
