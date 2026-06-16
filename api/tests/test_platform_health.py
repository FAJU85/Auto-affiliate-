import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.platform_health as m
    importlib.reload(m)
    return m


def test_is_healthy_unknown_platform(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.is_healthy("twitter") is True


def test_error_rate_no_events(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.error_rate("twitter") is None


def test_record_success(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("twitter", success=True)
    assert m.error_rate("twitter") == 0.0


def test_record_failure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("twitter", success=False, error="timeout")
    assert m.error_rate("twitter") == 1.0


def test_error_rate_mixed(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("twitter", success=True)
    m.record("twitter", success=False)
    assert m.error_rate("twitter") == 0.5


def test_is_healthy_below_threshold(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("twitter", success=True)
    m.record("twitter", success=True)
    m.record("twitter", success=False)
    assert m.is_healthy("twitter") is True  # 33% < 50%


def test_is_healthy_above_threshold(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("twitter", success=False)
    m.record("twitter", success=False)
    m.record("twitter", success=True)
    assert m.is_healthy("twitter") is False  # 67% > 50%


def test_pause_makes_unhealthy(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.pause_platform("twitter")
    assert m.is_healthy("twitter") is False


def test_resume_restores_health(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.pause_platform("twitter")
    m.resume_platform("twitter")
    assert m.is_healthy("twitter") is True


def test_resume_unknown_returns_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.resume_platform("nonexistent") is False


def test_get_status_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("twitter", success=True)
    s = m.get_status("twitter")
    for key in ("platform", "paused", "healthy", "error_rate", "events_in_window", "failures_in_window"):
        assert key in s


def test_get_status_counts(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("twitter", success=True)
    m.record("twitter", success=False)
    s = m.get_status("twitter")
    assert s["events_in_window"] == 2
    assert s["failures_in_window"] == 1


def test_health_summary_includes_all_platforms(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    summary = m.health_summary()
    platforms = [s["platform"] for s in summary]
    for p in ("twitter", "instagram", "bluesky"):
        assert p in platforms


def test_health_summary_sorted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    summary = m.health_summary()
    platforms = [s["platform"] for s in summary]
    assert platforms == sorted(platforms)
