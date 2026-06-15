"""Persistent retry queue for failed social posts.

Failed posts are saved to DATA_DIR/retry_queue.json and re-attempted
every 15 minutes (up to MAX_ATTEMPTS total). Entries expire after 24h.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
QUEUE_FILE = DATA_DIR / "retry_queue.json"

MAX_ATTEMPTS = 3
RETRY_INTERVAL_S = 900   # 15 minutes
EXPIRY_S = 86_400        # 24 hours


def _queue_file() -> Path:
    return Path(os.environ.get("DATA_DIR", str(DATA_DIR))) / "retry_queue.json"


def _load() -> list[dict]:
    f = _queue_file()
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text())
    except Exception:
        return []


def _save(entries: list[dict]) -> None:
    f = _queue_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(entries, indent=2))


def enqueue(
    platform: str,
    caption: str,
    redirect_url: str,
    product: dict[str, Any],
    image_url: str | None = None,
    error: str = "",
) -> None:
    """Add a failed post to the retry queue."""
    entries = _load()
    entries.append({
        "platform": platform,
        "caption": caption,
        "redirect_url": redirect_url,
        "product": product,
        "image_url": image_url,
        "error": error,
        "attempts": 1,
        "created_at": time.time(),
        "next_retry_at": time.time() + RETRY_INTERVAL_S,
    })
    _save(entries)


def get_due() -> list[dict]:
    """Return entries that are due for retry (not expired, not over max attempts)."""
    now = time.time()
    return [
        e for e in _load()
        if e.get("attempts", 0) < MAX_ATTEMPTS
        and e.get("next_retry_at", 0) <= now
        and (now - e.get("created_at", now)) < EXPIRY_S
    ]


def mark_success(entry: dict) -> None:
    """Remove a successfully retried entry from the queue."""
    entries = [e for e in _load() if e is not entry and not _same(e, entry)]
    _save(entries)


def mark_failed(entry: dict, error: str = "") -> None:
    """Increment attempt count and reschedule, or drop if max attempts reached."""
    entries = _load()
    updated = []
    for e in entries:
        if _same(e, entry):
            e["attempts"] = e.get("attempts", 1) + 1
            e["last_error"] = error
            e["next_retry_at"] = time.time() + RETRY_INTERVAL_S
            if e["attempts"] < MAX_ATTEMPTS:
                updated.append(e)
            # else drop — exhausted retries
        else:
            updated.append(e)
    _save(updated)


def _same(a: dict, b: dict) -> bool:
    return (
        a.get("platform") == b.get("platform")
        and a.get("created_at") == b.get("created_at")
        and a.get("redirect_url") == b.get("redirect_url")
    )


def queue_depth() -> int:
    return len(_load())


def clear_expired() -> int:
    """Remove entries older than EXPIRY_S or at max attempts. Returns count removed."""
    now = time.time()
    entries = _load()
    keep = [
        e for e in entries
        if e.get("attempts", 0) < MAX_ATTEMPTS
        and (now - e.get("created_at", now)) < EXPIRY_S
    ]
    _save(keep)
    return len(entries) - len(keep)
