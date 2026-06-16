import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.webhook_log as m
    importlib.reload(m)
    return m


def test_log_event_returns_dict(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    r = m.log_event("click", {"product": "p1"})
    assert isinstance(r, dict)


def test_log_event_not_duplicate_first_time(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    r = m.log_event("click", {"product": "p1"})
    assert r["duplicate"] is False


def test_log_event_duplicate_within_window(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.log_event("click", {"product": "p1"})
    r2 = m.log_event("click", {"product": "p1"})
    assert r2["duplicate"] is True


def test_log_event_no_dedupe(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.log_event("click", {"product": "p1"})
    r2 = m.log_event("click", {"product": "p1"}, dedupe=False)
    assert r2["duplicate"] is False


def test_log_event_different_payload_not_dup(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.log_event("click", {"product": "p1"})
    r2 = m.log_event("click", {"product": "p2"})
    assert r2["duplicate"] is False


def test_get_events_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_events() == []


def test_get_events_returns_logged(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.log_event("purchase", {"order": "123"})
    events = m.get_events()
    assert len(events) == 1


def test_get_events_filter_by_type(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.log_event("click", {"p": "1"})
    m.log_event("purchase", {"p": "2"}, dedupe=False)
    clicks = m.get_events(event_type="click")
    assert len(clicks) == 1
    assert clicks[0]["event_type"] == "click"


def test_mark_replayed(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    r = m.log_event("click", {"p": "1"})
    assert m.mark_replayed(r["id"]) is True
    events = m.get_events()
    assert events[0]["replayed"] is True


def test_mark_replayed_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.mark_replayed("nope") is False


def test_event_stats_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.event_stats()
    assert s["total"] == 0


def test_event_stats_by_type(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.log_event("click", {"p": "1"})
    m.log_event("purchase", {"p": "2"}, dedupe=False)
    s = m.event_stats()
    assert s["total"] == 2
    assert s["by_type"]["click"] == 1


def test_event_stats_replayed_count(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    r = m.log_event("click", {"p": "1"})
    m.mark_replayed(r["id"])
    assert m.event_stats()["replayed"] == 1
