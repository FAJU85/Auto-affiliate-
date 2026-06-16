"""Tests for api/utils/feed_health.py — Build #24."""

import importlib
import sys


def _reload_module(monkeypatch, tmp_path):
    """Reload feed_health with DATA_DIR pointed at tmp_path."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    if "api.utils.feed_health" in sys.modules:
        del sys.modules["api.utils.feed_health"]
    import api.utils.feed_health as fh
    importlib.reload(fh)
    return fh


def test_empty_all_feeds_health(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    assert fh.all_feeds_health() == []


def test_record_persists(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    fh.record_feed_result("sovrn", True, product_count=5)
    data = fh._load()
    assert "sovrn" in data
    assert len(data["sovrn"]) == 1
    assert data["sovrn"][0]["success"] is True
    assert data["sovrn"][0]["product_count"] == 5


def test_100pct_success_is_healthy(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for _ in range(10):
        fh.record_feed_result("sovrn", True, product_count=3)
    h = fh.feed_health("sovrn")
    assert h["status"] == "healthy"
    assert h["success_rate_pct"] == 100.0


def test_60pct_success_is_degraded(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for i in range(10):
        fh.record_feed_result("takeads", i < 6, product_count=2)
    h = fh.feed_health("takeads")
    assert h["status"] == "degraded"
    assert h["success_rate_pct"] == 60.0


def test_30pct_success_is_down(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for i in range(10):
        fh.record_feed_result("admitad", i < 3, product_count=1)
    h = fh.feed_health("admitad")
    assert h["status"] == "down"
    assert h["success_rate_pct"] == 30.0


def test_is_feed_healthy_true_for_healthy(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for _ in range(10):
        fh.record_feed_result("sovrn", True)
    assert fh.is_feed_healthy("sovrn") is True


def test_is_feed_healthy_true_for_degraded(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for i in range(10):
        fh.record_feed_result("sovrn", i < 6)
    assert fh.is_feed_healthy("sovrn") is True


def test_is_feed_healthy_false_for_down(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for i in range(10):
        fh.record_feed_result("sovrn", i < 3)
    assert fh.is_feed_healthy("sovrn") is False


def test_avg_products_computed_correctly(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    fh.record_feed_result("sovrn", True, product_count=10)
    fh.record_feed_result("sovrn", True, product_count=20)
    fh.record_feed_result("sovrn", True, product_count=30)
    h = fh.feed_health("sovrn")
    assert h["avg_products"] == 20.0


def test_last_called_is_iso_string(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    fh.record_feed_result("sovrn", True)
    h = fh.feed_health("sovrn")
    assert isinstance(h["last_called"], str)
    # Must parse as ISO datetime
    from datetime import datetime
    datetime.fromisoformat(h["last_called"])


def test_last_called_none_when_no_data(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    h = fh.feed_health("unknown_feed")
    assert h["last_called"] is None


def test_multiple_feeds_tracked_independently(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for _ in range(5):
        fh.record_feed_result("sovrn", True)
    for i in range(10):
        fh.record_feed_result("admitad", i < 2)
    s = fh.feed_health("sovrn")
    a = fh.feed_health("admitad")
    assert s["status"] == "healthy"
    assert a["status"] == "down"
    assert s["total_calls"] == 5
    assert a["total_calls"] == 10


def test_all_feeds_health_returns_one_per_feed(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    fh.record_feed_result("sovrn", True)
    fh.record_feed_result("takeads", False)
    fh.record_feed_result("admitad", True)
    results = fh.all_feeds_health()
    names = {r["feed_name"] for r in results}
    assert names == {"sovrn", "takeads", "admitad"}
    assert len(results) == 3


def test_rolling_window_prunes_to_max_entries(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for i in range(105):
        fh.record_feed_result("sovrn", True)
    data = fh._load()
    assert len(data["sovrn"]) == 100


def test_window_parameter_limits_stats(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    # First 10 fail, last 5 succeed
    for _ in range(10):
        fh.record_feed_result("sovrn", False)
    for _ in range(5):
        fh.record_feed_result("sovrn", True)
    # window=5 should only see the last 5 (all successes)
    h = fh.feed_health("sovrn", window=5)
    assert h["success_rate_pct"] == 100.0
    assert h["status"] == "healthy"


def test_zero_success_rate_is_down(monkeypatch, tmp_path):
    fh = _reload_module(monkeypatch, tmp_path)
    for _ in range(5):
        fh.record_feed_result("travelpayouts", False)
    h = fh.feed_health("travelpayouts")
    assert h["status"] == "down"
    assert h["success_rate_pct"] == 0.0
    assert h["successes"] == 0
    assert h["failures"] == 5
