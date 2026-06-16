from datetime import datetime, timezone, timedelta
from api.utils.click_heatmap import (
    build_heatmap, peak_hour, peak_day, hourly_distribution,
    weekday_distribution, heatmap_summary,
)

_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)  # Monday noon


def _run(hours_ago: float = 0, clicks: int = 1):
    ts = (_NOW - timedelta(hours=hours_ago)).isoformat()
    return {"clicks": clicks, "timestamp": ts}


def test_build_heatmap_empty():
    h = build_heatmap([])
    assert h["total_clicks"] == 0
    assert "Mon" in h["grid"]


def test_build_heatmap_structure():
    h = build_heatmap([])
    assert set(h["grid"].keys()) == {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    assert "12" in h["grid"]["Mon"]


def test_build_heatmap_counts():
    runs = [_run(hours_ago=0, clicks=5)]
    h = build_heatmap(runs)
    assert h["total_clicks"] == 5
    assert h["grid"]["Mon"]["12"] == 5


def test_peak_hour_empty():
    assert peak_hour([]) is None


def test_peak_hour_correct():
    runs = [_run(hours_ago=0, clicks=10), _run(hours_ago=2, clicks=1)]
    ph = peak_hour(runs)
    assert ph == 12


def test_peak_day_empty():
    assert peak_day([]) is None


def test_peak_day_correct():
    runs = [_run(hours_ago=0, clicks=10)]
    assert peak_day(runs) == "Mon"


def test_hourly_distribution_length():
    result = hourly_distribution([])
    assert len(result) == 24


def test_hourly_distribution_structure():
    result = hourly_distribution([])
    for entry in result:
        assert "hour" in entry
        assert "clicks" in entry
        assert "pct" in entry


def test_hourly_distribution_pct_sums():
    runs = [_run(hours_ago=0, clicks=5), _run(hours_ago=1, clicks=5)]
    result = hourly_distribution(runs)
    total_pct = sum(e["pct"] for e in result)
    assert abs(total_pct - 100.0) < 0.1


def test_weekday_distribution_length():
    result = weekday_distribution([])
    assert len(result) == 7


def test_weekday_distribution_structure():
    result = weekday_distribution([])
    for entry in result:
        assert "day" in entry
        assert "clicks" in entry
        assert "pct" in entry


def test_weekday_distribution_pct_sums():
    runs = [_run(hours_ago=0, clicks=10)]
    result = weekday_distribution(runs)
    total_pct = sum(e["pct"] for e in result)
    assert abs(total_pct - 100.0) < 0.1


def test_heatmap_summary_structure():
    s = heatmap_summary([])
    for key in ("total_clicks", "peak_hour", "peak_day", "peak_hour_label", "has_data"):
        assert key in s


def test_heatmap_summary_no_data():
    s = heatmap_summary([])
    assert s["has_data"] is False
    assert s["peak_hour"] is None


def test_heatmap_summary_with_data():
    runs = [_run(hours_ago=0, clicks=5)]
    s = heatmap_summary(runs)
    assert s["has_data"] is True
    assert s["peak_hour"] == 12
    assert "12:00" in s["peak_hour_label"]
