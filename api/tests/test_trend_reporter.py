from datetime import datetime, timezone, timedelta
from api.utils.trend_reporter import daily_trend, momentum, velocity, trend_report

_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)


def _run(days_ago: float, clicks: int = 10):
    ts = (_NOW - timedelta(days=days_ago)).isoformat()
    return {"success": True, "clicks": clicks, "timestamp": ts}


def test_daily_trend_length():
    result = daily_trend([], days=7, now=_NOW)
    assert len(result) == 7


def test_daily_trend_structure():
    result = daily_trend([], days=3, now=_NOW)
    for entry in result:
        assert "date" in entry
        assert "clicks" in entry


def test_daily_trend_zeros_for_no_runs():
    result = daily_trend([], days=3, now=_NOW)
    assert all(e["clicks"] == 0 for e in result)


def test_daily_trend_counts_clicks():
    runs = [_run(days_ago=0, clicks=50)]
    result = daily_trend(runs, days=1, now=_NOW)
    assert result[0]["clicks"] == 50


def test_daily_trend_sorted_asc():
    result = daily_trend([], days=5, now=_NOW)
    dates = [r["date"] for r in result]
    assert dates == sorted(dates)


def test_momentum_flat():
    runs = [_run(days_ago=i, clicks=10) for i in range(6)]
    m = momentum(runs, window=3, now=_NOW)
    assert m == 0.0


def test_momentum_positive():
    recent = [_run(days_ago=i, clicks=100) for i in range(3)]
    older = [_run(days_ago=i, clicks=10) for i in range(3, 6)]
    m = momentum(recent + older, window=3, now=_NOW)
    assert m > 0


def test_momentum_negative():
    recent = [_run(days_ago=i, clicks=5) for i in range(3)]
    older = [_run(days_ago=i, clicks=100) for i in range(3, 6)]
    m = momentum(recent + older, window=3, now=_NOW)
    assert m < 0


def test_momentum_empty():
    assert momentum([], window=3, now=_NOW) == 0.0


def test_velocity_flat():
    runs = [_run(days_ago=i, clicks=10) for i in range(7)]
    v = velocity(runs, days=7, now=_NOW)
    assert v == 0.0


def test_velocity_increasing():
    runs = [_run(days_ago=6 - i, clicks=i * 10) for i in range(7)]
    v = velocity(runs, days=7, now=_NOW)
    assert v > 0


def test_trend_report_structure():
    r = trend_report([], days=7, now=_NOW)
    for key in ("days", "total_clicks", "avg_clicks_per_day", "peak_clicks", "peak_day", "momentum", "velocity", "direction", "trend"):
        assert key in r


def test_trend_report_direction_flat():
    r = trend_report([], days=7, now=_NOW)
    assert r["direction"] == "flat"


def test_trend_report_total():
    runs = [_run(days_ago=i, clicks=10) for i in range(7)]
    r = trend_report(runs, days=7, now=_NOW)
    assert r["total_clicks"] == 70


def test_trend_report_days():
    r = trend_report([], days=14, now=_NOW)
    assert r["days"] == 14
    assert len(r["trend"]) == 14
