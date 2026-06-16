import importlib


def _reload(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.activity_log as m
    importlib.reload(m)
    return m


def test_get_recent_initially_empty(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    assert m.get_recent() == []


def test_log_request_creates_entry(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    m.log_request("/api/status", "GET", status_code=200, latency_ms=12.5)
    entries = m.get_recent()
    assert len(entries) == 1


def test_entry_has_required_keys(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    m.log_request("/api/run", "POST", status_code=200, latency_ms=50.0)
    entry = m.get_recent(1)[0]
    for key in ("timestamp", "endpoint", "method", "status_code", "latency_ms", "extra"):
        assert key in entry


def test_get_recent_limit(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    for i in range(5):
        m.log_request(f"/api/ep{i}", "GET")
    assert len(m.get_recent(2)) == 2


def test_get_recent_most_recent_first(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    m.log_request("/api/first", "GET")
    m.log_request("/api/second", "GET")
    entries = m.get_recent()
    assert entries[0]["endpoint"] == "/api/second"


def test_activity_summary_has_required_keys(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    summary = m.activity_summary()
    for key in ("total_logged", "by_endpoint", "by_method", "avg_latency_ms"):
        assert key in summary


def test_by_endpoint_counts(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    m.log_request("/api/status", "GET")
    m.log_request("/api/status", "GET")
    m.log_request("/api/run", "POST")
    summary = m.activity_summary()
    assert summary["by_endpoint"]["/api/status"] == 2
    assert summary["by_endpoint"]["/api/run"] == 1


def test_avg_latency_none_when_no_data(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    m.log_request("/api/status", "GET")
    summary = m.activity_summary()
    assert summary["avg_latency_ms"] is None


def test_avg_latency_correct(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    m.log_request("/api/a", "GET", latency_ms=10.0)
    m.log_request("/api/b", "GET", latency_ms=20.0)
    summary = m.activity_summary()
    assert summary["avg_latency_ms"] == 15.0


def test_total_logged_count(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    for _ in range(3):
        m.log_request("/api/x", "GET")
    assert m.activity_summary()["total_logged"] == 3


def test_never_raises_on_bad_file(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    (tmp_path / "activity_log.jsonl").write_text("not json\n")
    assert m.get_recent() == []


def test_by_method_counts(tmp_path, monkeypatch):
    m = _reload(tmp_path, monkeypatch)
    m.log_request("/api/a", "GET")
    m.log_request("/api/b", "POST")
    m.log_request("/api/c", "GET")
    summary = m.activity_summary()
    assert summary["by_method"]["GET"] == 2
    assert summary["by_method"]["POST"] == 1
