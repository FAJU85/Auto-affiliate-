import importlib
from datetime import datetime, timezone, timedelta


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.post_scheduler as m
    importlib.reload(m)
    return m


_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
_FUTURE = _NOW + timedelta(hours=2)
_PAST = _NOW - timedelta(hours=1)


def test_schedule_returns_id(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    job_id = m.schedule_post("bluesky", "hello", _FUTURE)
    assert isinstance(job_id, str) and len(job_id) == 8


def test_list_jobs_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.list_jobs() == []


def test_list_jobs_returns_scheduled(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.schedule_post("bluesky", "hello", _FUTURE)
    assert len(m.list_jobs()) == 1


def test_get_due_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_due(_NOW) == []


def test_get_due_future_not_returned(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.schedule_post("bluesky", "hello", _FUTURE)
    assert m.get_due(_NOW) == []


def test_get_due_past_returned(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.schedule_post("bluesky", "hello", _PAST)
    assert len(m.get_due(_NOW)) == 1


def test_mark_done(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    jid = m.schedule_post("bluesky", "hello", _PAST)
    assert m.mark_done(jid) is True
    assert m.list_jobs(status="done")[0]["id"] == jid


def test_mark_done_removes_from_due(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    jid = m.schedule_post("bluesky", "hello", _PAST)
    m.mark_done(jid)
    assert m.get_due(_NOW) == []


def test_mark_failed(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    jid = m.schedule_post("x", "hello", _PAST)
    assert m.mark_failed(jid, "network error") is True
    failed = m.list_jobs(status="failed")
    assert failed[0]["error"] == "network error"


def test_cancel_pending(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    jid = m.schedule_post("bluesky", "hi", _FUTURE)
    assert m.cancel(jid) is True
    assert m.list_jobs(status="cancelled")[0]["id"] == jid


def test_cancel_done_fails(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    jid = m.schedule_post("bluesky", "hi", _PAST)
    m.mark_done(jid)
    assert m.cancel(jid) is False


def test_queue_stats_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.queue_stats()
    for key in ("total", "pending", "done", "failed", "cancelled"):
        assert key in s


def test_queue_stats_counts(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.schedule_post("bluesky", "a", _FUTURE)
    jid = m.schedule_post("x", "b", _PAST)
    m.mark_done(jid)
    s = m.queue_stats()
    assert s["total"] == 2
    assert s["pending"] == 1
    assert s["done"] == 1


def test_list_jobs_sorted_by_scheduled_at(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.schedule_post("bluesky", "later", _FUTURE)
    m.schedule_post("x", "sooner", _PAST)
    jobs = m.list_jobs()
    assert jobs[0]["scheduled_at"] < jobs[1]["scheduled_at"]
