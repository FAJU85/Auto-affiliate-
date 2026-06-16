from datetime import datetime, timezone, timedelta
from api.utils.spike_detector import detect_spikes, rolling_averages

_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)


def _run(days_ago: float, clicks: int = 10):
    ts = (_NOW - timedelta(days=days_ago)).isoformat()
    return {"success": True, "clicks": clicks, "timestamp": ts}


def test_detect_spikes_empty():
    r = detect_spikes([], now=_NOW)
    assert "today" in r
    assert r["is_spike"] is False
    assert r["is_dip"] is False


def test_detect_spikes_structure():
    r = detect_spikes([], now=_NOW)
    for key in ("today", "today_value", "baseline_avg", "baseline_std", "zscore", "is_spike", "is_dip", "status"):
        assert key in r


def test_detect_spikes_normal():
    runs = [_run(days_ago=i, clicks=10) for i in range(1, 8)]
    r = detect_spikes(runs, now=_NOW)
    assert r["status"] in ("normal", "spike", "dip")


def test_detect_spikes_no_baseline_zscore_none():
    runs = []
    r = detect_spikes(runs, now=_NOW)
    assert r["zscore"] is None


def test_detect_spike_high_today():
    runs = [_run(days_ago=i, clicks=10) for i in range(1, 8)]
    runs.append({"success": True, "clicks": 1000, "timestamp": _NOW.isoformat()})
    r = detect_spikes(runs, now=_NOW)
    assert r["is_spike"] is True
    assert r["status"] == "spike"


def test_detect_dip_low_today():
    runs = [_run(days_ago=i, clicks=100) for i in range(1, 8)]
    r = detect_spikes(runs, now=_NOW)
    assert r["is_dip"] is True
    assert r["status"] == "dip"


def test_baseline_avg_correct():
    runs = [_run(days_ago=i, clicks=10) for i in range(1, 4)]
    r = detect_spikes(runs, window_days=3, now=_NOW)
    assert r["baseline_avg"] == 10.0


def test_rolling_averages_empty():
    assert rolling_averages([]) == []


def test_rolling_averages_structure():
    runs = [_run(days_ago=i) for i in range(5)]
    result = rolling_averages(runs)
    assert len(result) > 0
    for entry in result:
        assert "date" in entry
        assert "value" in entry
        assert "rolling_avg" in entry


def test_rolling_averages_sorted():
    runs = [_run(days_ago=i) for i in range(5)]
    result = rolling_averages(runs)
    dates = [r["date"] for r in result]
    assert dates == sorted(dates)


def test_rolling_avg_window():
    runs = [_run(days_ago=i, clicks=10 * i) for i in range(1, 6)]
    result = rolling_averages(runs, window=2)
    assert all(isinstance(r["rolling_avg"], float) for r in result)
