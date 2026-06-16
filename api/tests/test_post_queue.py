import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.post_queue as m
    importlib.reload(m)
    return m


def test_enqueue_returns_id(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello world")
    assert isinstance(item_id, str) and len(item_id) > 0


def test_enqueue_invalid_priority(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        m.enqueue("twitter", "Hello", priority=99)


def test_get_item_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello world")
    item = m.get_item(item_id)
    for key in ("id", "platform", "content", "priority", "status", "created_at", "sent_at", "error"):
        assert key in item


def test_get_item_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_item("nonexistent") is None


def test_initial_status_pending(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello")
    assert m.get_item(item_id)["status"] == "pending"


def test_update_status_sent(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello")
    assert m.update_status(item_id, "sent") is True
    assert m.get_item(item_id)["status"] == "sent"
    assert m.get_item(item_id)["sent_at"] is not None


def test_update_status_failed_with_error(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello")
    m.update_status(item_id, "failed", error="timeout")
    assert m.get_item(item_id)["error"] == "timeout"


def test_update_status_invalid(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello")
    with pytest.raises(ValueError):
        m.update_status(item_id, "invalid_status")


def test_update_status_unknown_item(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.update_status("nonexistent", "sent") is False


def test_get_pending_returns_pending(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello")
    pending = m.get_pending()
    assert any(i["id"] == item_id for i in pending)


def test_get_pending_excludes_sent(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello")
    m.update_status(item_id, "sent")
    assert m.get_pending() == []


def test_get_pending_by_platform(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.enqueue("twitter", "Hello")
    m.enqueue("bluesky", "Hello")
    pending = m.get_pending(platform="twitter")
    assert all(i["platform"] == "twitter" for i in pending)


def test_get_pending_sorted_by_priority(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.enqueue("twitter", "Low", priority=3)
    m.enqueue("twitter", "High", priority=1)
    pending = m.get_pending()
    assert pending[0]["priority"] == 1


def test_cancel(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.enqueue("twitter", "Hello")
    assert m.cancel(item_id) is True
    assert m.get_item(item_id)["status"] == "cancelled"


def test_queue_stats(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.enqueue("twitter", "Hello")
    m.enqueue("bluesky", "World")
    s = m.queue_stats()
    for key in ("total", "pending", "sent", "failed", "cancelled"):
        assert key in s
    assert s["total"] == 2
    assert s["pending"] == 2
