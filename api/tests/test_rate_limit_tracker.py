import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.rate_limit_tracker as m
    importlib.reload(m)
    return m


def test_is_limited_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.is_limited("twitter") is False


def test_record_hit_returns_status(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.record_hit("twitter", limit=5)
    for key in ("platform", "hits_in_window", "limit", "remaining", "is_limited", "reset_at", "window_seconds"):
        assert key in s


def test_record_hit_increments(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_hit("twitter", limit=5)
    m.record_hit("twitter", limit=5)
    s = m.get_status("twitter")
    assert s["hits_in_window"] == 2


def test_remaining_decreases(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_hit("twitter", limit=5)
    s = m.get_status("twitter")
    assert s["remaining"] == 4


def test_is_limited_at_limit(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for _ in range(3):
        m.record_hit("twitter", limit=3)
    assert m.is_limited("twitter") is True


def test_not_limited_below_limit(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_hit("twitter", limit=5)
    assert m.is_limited("twitter") is False


def test_get_status_none_for_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_status("twitter") is None


def test_reset_platform(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for _ in range(3):
        m.record_hit("twitter", limit=3)
    m.reset_platform("twitter")
    assert m.is_limited("twitter") is False


def test_reset_unknown_returns_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.reset_platform("nonexistent") is False


def test_reset_at_set_after_hit(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_hit("twitter", limit=5)
    s = m.get_status("twitter")
    assert s["reset_at"] is not None


def test_rate_limit_summary_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.rate_limit_summary() == []


def test_rate_limit_summary_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_hit("twitter", limit=5)
    s = m.rate_limit_summary()
    assert len(s) == 1
    assert s[0]["platform"] == "twitter"


def test_rate_limit_summary_sorted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_hit("twitter", limit=5)
    m.record_hit("bluesky", limit=10)
    platforms = [x["platform"] for x in m.rate_limit_summary()]
    assert platforms == sorted(platforms)


def test_multiple_platforms_independent(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for _ in range(3):
        m.record_hit("twitter", limit=3)
    assert m.is_limited("twitter") is True
    assert m.is_limited("bluesky") is False
