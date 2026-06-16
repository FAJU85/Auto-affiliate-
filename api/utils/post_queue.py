"""Scheduled post queue stored in /data/post_queue.json.

Each item:
  {
    "id":           str  (uuid4 hex),
    "product_name": str,
    "platform":     str,
    "scheduled_at": str  (ISO UTC),
    "created_at":   str  (ISO UTC),
    "status":       "pending" | "sent" | "failed",
    "caption":      str | None,
  }
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR   = Path(os.environ.get("DATA_DIR", "/data"))
QUEUE_FILE = DATA_DIR / "post_queue.json"

_PRUNE_DAYS = 7


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _load() -> list:
    try:
        return json.loads(QUEUE_FILE.read_text())
    except Exception:
        return []


def _save(items: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = _now_utc() - timedelta(days=_PRUNE_DAYS)
    items = [
        it for it in items
        if it.get("status") == "pending" or _parse(it.get("created_at", "")) > cutoff
    ]
    tmp = str(QUEUE_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(items, indent=2))
    Path(tmp).rename(QUEUE_FILE)


def enqueue(
    product_name: str,
    platform: str,
    scheduled_at: str,
    caption: str | None = None,
) -> dict:
    """Add a new item to the queue and return it."""
    items = _load()
    item: dict = {
        "id":           uuid.uuid4().hex,
        "product_name": product_name,
        "platform":     platform,
        "scheduled_at": scheduled_at,
        "created_at":   _iso(_now_utc()),
        "status":       "pending",
        "caption":      caption,
    }
    items.append(item)
    _save(items)
    return item


def get_queue(status: str | None = None) -> list[dict]:
    """Return all items, optionally filtered by status, sorted by scheduled_at."""
    items = _load()
    if status is not None:
        items = [it for it in items if it.get("status") == status]
    return sorted(items, key=lambda it: it.get("scheduled_at", ""))


def get_due(now: datetime | None = None) -> list[dict]:
    """Return pending items whose scheduled_at <= now (default UTC now)."""
    if now is None:
        now = _now_utc()
    return [
        it for it in get_queue(status="pending")
        if _parse(it.get("scheduled_at", "")) <= now
    ]


def _set_status(item_id: str, status: str) -> bool:
    items = _load()
    for it in items:
        if it.get("id") == item_id:
            it["status"] = status
            _save(items)
            return True
    return False


def mark_sent(item_id: str) -> bool:
    """Mark item as sent. Returns True if found."""
    return _set_status(item_id, "sent")


def mark_failed(item_id: str) -> bool:
    """Mark item as failed. Returns True if found."""
    return _set_status(item_id, "failed")


def cancel(item_id: str) -> bool:
    """Remove a pending item from the queue. Returns True if removed."""
    items = _load()
    for it in items:
        if it.get("id") == item_id:
            if it.get("status") != "pending":
                return False
            items.remove(it)
            _save(items)
            return True
    return False
