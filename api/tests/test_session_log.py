import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.session_log as m
    importlib.reload(m)
    return m


def test_start_session_returns_id(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session()
    assert isinstance(sid, str) and len(sid) > 0


def test_get_session_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session(meta={"run": 1})
    s = m.get_session(sid)
    for key in ("id", "started_at", "ended_at", "meta", "events"):
        assert key in s


def test_get_session_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_session("nonexistent") is None


def test_log_event_returns_true(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session()
    assert m.log_event(sid, "info", "hello") is True


def test_log_event_unknown_session(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.log_event("bad_id", "info", "hello") is False


def test_log_event_invalid_type(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session()
    with pytest.raises(ValueError):
        m.log_event(sid, "invalid_type", "msg")


def test_get_events_returns_all(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session()
    m.log_event(sid, "post", "posted to twitter")
    m.log_event(sid, "error", "failed bluesky")
    events = m.get_events(sid)
    assert len(events) == 2


def test_get_events_filtered_by_type(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session()
    m.log_event(sid, "post", "posted")
    m.log_event(sid, "error", "failed")
    events = m.get_events(sid, event_type="error")
    assert len(events) == 1
    assert events[0]["type"] == "error"


def test_end_session(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session()
    assert m.end_session(sid) is True
    assert m.get_session(sid)["ended_at"] is not None


def test_end_session_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.end_session("nonexistent") is False


def test_session_summary_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session()
    m.log_event(sid, "post", "posted")
    m.log_event(sid, "error", "failed")
    s = m.session_summary(sid)
    for key in ("id", "started_at", "ended_at", "event_count", "post", "error"):
        assert key in s


def test_session_summary_counts(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    sid = m.start_session()
    m.log_event(sid, "post", "p1")
    m.log_event(sid, "post", "p2")
    m.log_event(sid, "error", "e1")
    s = m.session_summary(sid)
    assert s["post"] == 2
    assert s["error"] == 1
    assert s["event_count"] == 3


def test_session_summary_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.session_summary("nonexistent") is None


def test_list_sessions_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.list_sessions() == []


def test_list_sessions_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.start_session()
    sessions = m.list_sessions()
    assert len(sessions) == 1
    for key in ("id", "started_at", "ended_at", "event_count"):
        assert key in sessions[0]
