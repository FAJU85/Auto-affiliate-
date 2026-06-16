from api.utils.revenue_estimator import estimate, estimate_from_runs, roi


def test_estimate_zero_clicks():
    r = estimate(0)
    assert r["commission"] == 0.0
    assert r["conversions"] == 0.0


def test_estimate_structure():
    r = estimate(100)
    for key in ("clicks", "conversions", "gross_revenue", "commission", "conversion_rate", "avg_order_value", "commission_pct"):
        assert key in r


def test_estimate_math():
    r = estimate(100, conversion_rate=0.1, avg_order_value=100.0, commission_pct=0.1)
    assert r["conversions"] == 10.0
    assert r["gross_revenue"] == 1000.0
    assert r["commission"] == 100.0


def test_estimate_from_runs_empty():
    r = estimate_from_runs([])
    assert r["clicks"] == 0
    assert r["commission"] == 0.0


def test_estimate_from_runs_sums_clicks():
    runs = [
        {"success": True, "clicks": 100, "platform": "bluesky", "timestamp": "2026-06-16T10:00:00+00:00"},
        {"success": True, "clicks": 50, "platform": "x", "timestamp": "2026-06-16T11:00:00+00:00"},
    ]
    r = estimate_from_runs(runs)
    assert r["clicks"] == 150


def test_estimate_from_runs_excludes_failed():
    runs = [
        {"success": False, "clicks": 999, "platform": "bluesky", "timestamp": "2026-06-16T10:00:00+00:00"},
        {"success": True, "clicks": 10, "platform": "x", "timestamp": "2026-06-16T11:00:00+00:00"},
    ]
    r = estimate_from_runs(runs)
    assert r["clicks"] == 10


def test_estimate_from_runs_excludes_old():
    runs = [
        {"success": True, "clicks": 500, "platform": "bluesky", "timestamp": "2025-01-01T00:00:00+00:00"},
    ]
    r = estimate_from_runs(runs, days=30)
    assert r["clicks"] == 0


def test_estimate_from_runs_by_platform():
    runs = [
        {"success": True, "clicks": 100, "platform": "bluesky", "timestamp": "2026-06-16T10:00:00+00:00"},
        {"success": True, "clicks": 50, "platform": "x", "timestamp": "2026-06-16T11:00:00+00:00"},
    ]
    r = estimate_from_runs(runs)
    assert "bluesky" in r["by_platform"]
    assert "x" in r["by_platform"]


def test_estimate_from_runs_posts_count():
    runs = [
        {"success": True, "clicks": 10, "platform": "bluesky", "timestamp": "2026-06-16T10:00:00+00:00"},
        {"success": True, "clicks": 10, "platform": "x", "timestamp": "2026-06-16T11:00:00+00:00"},
    ]
    r = estimate_from_runs(runs)
    assert r["posts"] == 2


def test_roi_zero_spend():
    r = roi(0, 100.0)
    assert r["roi_pct"] is None
    assert r["profit"] == 100.0


def test_roi_positive():
    r = roi(50.0, 100.0)
    assert r["roi_pct"] == 100.0
    assert r["profit"] == 50.0


def test_roi_negative():
    r = roi(200.0, 100.0)
    assert r["profit"] == -100.0
    assert r["roi_pct"] == -50.0


def test_roi_structure():
    r = roi(10.0, 15.0)
    for key in ("spend", "commission", "profit", "roi_pct"):
        assert key in r
