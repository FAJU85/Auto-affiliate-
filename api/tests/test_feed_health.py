import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.feed_health as m
    importlib.reload(m)
    return m


def test_is_stale_unknown_feed(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.is_stale("sovrn") is True


def test_record_fetch_marks_not_stale(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=100)
    assert m.is_stale("sovrn", stale_hours=24) is False


def test_record_fetch_failed_still_stale(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=0, success=False, error="timeout")
    assert m.is_stale("sovrn") is True


def test_has_drift_false_initially(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=100)
    assert m.has_drift("sovrn") is False


def test_has_drift_detects_drop(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=100)
    m.record_fetch("sovrn", product_count=50)
    assert m.has_drift("sovrn") is True


def test_has_drift_small_change_ok(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=100)
    m.record_fetch("sovrn", product_count=95)
    assert m.has_drift("sovrn") is False


def test_has_drift_unknown_feed(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.has_drift("nonexistent") is False


def test_get_status_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=100)
    s = m.get_status("sovrn")
    for key in ("feed", "last_fetch_ts", "last_success_ts", "last_product_count",
                "baseline_count", "total_fetches", "failures", "is_stale", "has_drift"):
        assert key in s


def test_get_status_counts(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=100)
    m.record_fetch("sovrn", product_count=0, success=False)
    s = m.get_status("sovrn")
    assert s["total_fetches"] == 2
    assert s["failures"] == 1


def test_get_status_last_product_count(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=150)
    s = m.get_status("sovrn")
    assert s["last_product_count"] == 150


def test_baseline_set_on_first_success(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=200)
    m.record_fetch("sovrn", product_count=100)
    s = m.get_status("sovrn")
    assert s["baseline_count"] == 200


def test_feed_health_summary_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.feed_health_summary() == []


def test_feed_health_summary_sorted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_fetch("sovrn", product_count=100)
    m.record_fetch("admitad", product_count=50)
    feeds = [s["feed"] for s in m.feed_health_summary()]
    assert feeds == sorted(feeds)
