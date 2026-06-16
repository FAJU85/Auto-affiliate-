"""Tests for api/utils/post_queue.py — 16 cases."""

import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _reload(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    for mod in list(sys.modules):
        if "post_queue" in mod:
            del sys.modules[mod]
    import api.utils.post_queue as pq
    importlib.reload(pq)
    return pq


def _future(minutes: int = 60) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past(minutes: int = 60) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


# 1. Empty queue returns empty list
def test_empty_queue(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    assert pq.get_queue() == []


# 2. enqueue returns item with required keys
def test_enqueue_returns_required_keys(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    item = pq.enqueue("Widget", "bluesky", _future())
    for key in ("id", "product_name", "platform", "scheduled_at", "created_at", "status", "caption"):
        assert key in item, f"missing key: {key}"


# 3. enqueue persists item
def test_enqueue_persists(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    item = pq.enqueue("Widget", "bluesky", _future())
    queue = pq.get_queue()
    assert len(queue) == 1
    assert queue[0]["id"] == item["id"]


# 4. get_queue returns items sorted by scheduled_at
def test_get_queue_sorted(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    t1 = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    t2 = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    pq.enqueue("A", "bluesky", t1)
    pq.enqueue("B", "bluesky", t2)
    q = pq.get_queue()
    assert q[0]["scheduled_at"] == t2
    assert q[1]["scheduled_at"] == t1


# 5. get_queue(status="pending") filters correctly
def test_get_queue_status_filter(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    item1 = pq.enqueue("A", "bluesky", _future(10))
    pq.enqueue("B", "bluesky", _future(20))
    pq.mark_sent(item1["id"])
    pending = pq.get_queue(status="pending")
    assert len(pending) == 1
    assert pending[0]["product_name"] == "B"


# 6. get_due returns only items due now
def test_get_due_returns_due(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    item = pq.enqueue("Past", "bluesky", _past(30))
    due = pq.get_due()
    assert any(it["id"] == item["id"] for it in due)


# 7. get_due excludes future items
def test_get_due_excludes_future(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    pq.enqueue("Future", "bluesky", _future(120))
    assert pq.get_due() == []


# 8. mark_sent updates status and returns True
def test_mark_sent(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    item = pq.enqueue("X", "bluesky", _future())
    assert pq.mark_sent(item["id"]) is True
    q = pq.get_queue()
    assert q[0]["status"] == "sent"


# 9. mark_failed updates status and returns True
def test_mark_failed(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    item = pq.enqueue("X", "bluesky", _future())
    assert pq.mark_failed(item["id"]) is True
    q = pq.get_queue()
    assert q[0]["status"] == "failed"


# 10. mark_sent returns False for unknown id
def test_mark_sent_unknown(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    assert pq.mark_sent("nonexistent") is False


# 11. cancel removes pending item and returns True
def test_cancel_removes_pending(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    item = pq.enqueue("X", "bluesky", _future())
    assert pq.cancel(item["id"]) is True
    assert pq.get_queue() == []


# 12. cancel returns False for unknown id
def test_cancel_unknown(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    assert pq.cancel("nonexistent") is False


# 13. id is unique across multiple enqueues
def test_unique_ids(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    ids = [pq.enqueue(f"P{i}", "bluesky", _future(i + 1))["id"] for i in range(10)]
    assert len(set(ids)) == 10


# 14. cancel returns False for non-pending (sent) item
def test_cancel_non_pending(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    item = pq.enqueue("X", "bluesky", _future())
    pq.mark_sent(item["id"])
    assert pq.cancel(item["id"]) is False
    # Item still in queue (as "sent")
    assert len(pq.get_queue()) == 1


# 15. prune removes sent/failed items older than 7 days
def test_prune_old_items(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    import json

    # Manually write an old sent item
    old_ts = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    old_item = {
        "id": "olditem",
        "product_name": "Old",
        "platform": "bluesky",
        "scheduled_at": old_ts,
        "created_at": old_ts,
        "status": "sent",
        "caption": None,
    }
    queue_file = tmp_path / "post_queue.json"
    queue_file.write_text(json.dumps([old_item]))

    # Enqueue a new item — triggers _save which prunes
    new_item = pq.enqueue("New", "bluesky", _future())
    q = pq.get_queue()
    ids = [it["id"] for it in q]
    assert "olditem" not in ids
    assert new_item["id"] in ids


# 16. get_due with custom now parameter
def test_get_due_custom_now(tmp_path, monkeypatch):
    pq = _reload(tmp_path, monkeypatch)
    future_ts = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    item = pq.enqueue("Scheduled", "mastodon", future_ts)

    # With default now — not due
    assert pq.get_due() == []

    # With custom now far in the future — due
    far_future = datetime.now(timezone.utc) + timedelta(hours=5)
    due = pq.get_due(now=far_future)
    assert any(it["id"] == item["id"] for it in due)
