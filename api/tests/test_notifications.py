import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.notifications as m
    importlib.reload(m)
    return m


def test_push_returns_id(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    nid = m.push("hello")
    assert isinstance(nid, str) and len(nid) == 8


def test_push_invalid_level(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        m.push("msg", level="bad")


def test_get_unread_after_push(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.push("test notification")
    assert len(m.get_unread()) == 1


def test_mark_read(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    nid = m.push("alert")
    assert m.mark_read(nid) is True
    assert m.get_unread() == []


def test_mark_read_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.mark_read("nope") is False


def test_mark_all_read(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.push("a")
    m.push("b")
    count = m.mark_all_read()
    assert count == 2
    assert m.get_unread() == []


def test_mark_all_read_already_read(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    nid = m.push("a")
    m.mark_read(nid)
    assert m.mark_all_read() == 0


def test_get_unread_filter_by_level(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.push("info msg", level="info")
    m.push("error msg", level="error")
    errors = m.get_unread(level="error")
    assert len(errors) == 1
    assert errors[0]["level"] == "error"


def test_get_all_limit(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for i in range(5):
        m.push(f"msg {i}")
    assert len(m.get_all(limit=3)) == 3


def test_delete_notification(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    nid = m.push("to delete")
    assert m.delete(nid) is True
    assert m.get_unread() == []


def test_delete_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.delete("nope") is False


def test_notification_stats_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.notification_stats()
    assert s["total"] == 0
    assert s["unread"] == 0


def test_notification_stats_counts(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.push("a", level="info")
    m.push("b", level="error")
    s = m.notification_stats()
    assert s["total"] == 2
    assert s["unread"] == 2
    assert s["by_level"]["error"] == 1
