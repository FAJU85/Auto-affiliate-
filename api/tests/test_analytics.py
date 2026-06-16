"""Tests for api/utils/analytics.py."""

from datetime import datetime, timezone, timedelta

from api.utils.analytics import summarize_runs, weekly_summary, monthly_summary


def _ts(days_ago: float = 0) -> str:
    """Return an ISO timestamp `days_ago` days in the past."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


# ── Empty / zero-state ────────────────────────────────────────────────────────

def test_empty_runs_returns_zeros():
    result = summarize_runs([])
    assert result["total_runs"] == 0
    assert result["successful_runs"] == 0
    assert result["failed_runs"] == 0
    assert result["total_clicks"] == 0
    assert result["avg_clicks_per_run"] == 0.0
    assert result["success_rate_pct"] == 0.0
    assert result["by_platform"] == {}


def test_success_rate_zero_when_no_runs():
    result = summarize_runs([])
    assert result["success_rate_pct"] == 0.0


# ── Success / failure counts ──────────────────────────────────────────────────

def test_all_successful_runs():
    runs = [
        {"timestamp": _ts(1), "success": True, "clicks": 2},
        {"timestamp": _ts(2), "success": True, "clicks": 3},
    ]
    result = summarize_runs(runs)
    assert result["successful_runs"] == 2
    assert result["failed_runs"] == 0


def test_failed_runs_counted_separately():
    runs = [
        {"timestamp": _ts(1), "success": True, "clicks": 5},
        {"timestamp": _ts(2), "success": False, "clicks": 0},
        {"timestamp": _ts(3), "success": False, "clicks": 0},
    ]
    result = summarize_runs(runs)
    assert result["successful_runs"] == 1
    assert result["failed_runs"] == 2
    assert result["total_runs"] == 3


def test_success_rate_100_when_all_succeed():
    runs = [
        {"timestamp": _ts(1), "success": True, "clicks": 1},
        {"timestamp": _ts(2), "success": True, "clicks": 2},
    ]
    result = summarize_runs(runs)
    assert result["success_rate_pct"] == 100.0


def test_success_rate_partial():
    runs = [
        {"timestamp": _ts(1), "success": True, "clicks": 1},
        {"timestamp": _ts(2), "success": False, "clicks": 0},
    ]
    result = summarize_runs(runs)
    assert result["success_rate_pct"] == 50.0


# ── Clicks ────────────────────────────────────────────────────────────────────

def test_total_clicks_sums_only_successful_runs():
    runs = [
        {"timestamp": _ts(1), "success": True, "clicks": 10},
        {"timestamp": _ts(2), "success": False, "clicks": 5},  # excluded
        {"timestamp": _ts(3), "success": True, "clicks": 3},
    ]
    result = summarize_runs(runs)
    assert result["total_clicks"] == 13


def test_avg_clicks_per_run():
    runs = [
        {"timestamp": _ts(1), "success": True, "clicks": 6},
        {"timestamp": _ts(2), "success": True, "clicks": 4},
    ]
    result = summarize_runs(runs)
    assert result["avg_clicks_per_run"] == 5.0


# ── Date window ───────────────────────────────────────────────────────────────

def test_old_runs_excluded():
    runs = [
        {"timestamp": _ts(5), "success": True, "clicks": 1},   # inside 7-day window
        {"timestamp": _ts(10), "success": True, "clicks": 100},  # outside 7-day window
    ]
    result = summarize_runs(runs, days=7)
    assert result["total_runs"] == 1
    assert result["total_clicks"] == 1


def test_all_runs_inside_window_included():
    runs = [{"timestamp": _ts(i), "success": True, "clicks": 1} for i in range(1, 6)]
    result = summarize_runs(runs, days=7)
    assert result["total_runs"] == 5


# ── Platform grouping ─────────────────────────────────────────────────────────

def test_by_platform_groups_correctly():
    runs = [
        {"timestamp": _ts(1), "success": True, "clicks": 3, "platform": "bluesky"},
        {"timestamp": _ts(2), "success": True, "clicks": 2, "platform": "bluesky"},
        {"timestamp": _ts(3), "success": True, "clicks": 5, "platform": "mastodon"},
    ]
    result = summarize_runs(runs)
    assert result["by_platform"]["bluesky"]["runs"] == 2
    assert result["by_platform"]["bluesky"]["clicks"] == 5
    assert result["by_platform"]["mastodon"]["runs"] == 1
    assert result["by_platform"]["mastodon"]["clicks"] == 5


def test_missing_platform_key_uses_unknown():
    runs = [
        {"timestamp": _ts(1), "success": True, "clicks": 4},  # no "platform" key
    ]
    result = summarize_runs(runs)
    assert "unknown" in result["by_platform"]
    assert result["by_platform"]["unknown"]["runs"] == 1


# ── weekly_summary / monthly_summary ─────────────────────────────────────────

def test_weekly_summary_uses_7_day_window():
    runs = [
        {"timestamp": _ts(6), "success": True, "clicks": 1},   # inside 7 days
        {"timestamp": _ts(8), "success": True, "clicks": 100},  # outside 7 days
    ]
    result = weekly_summary(runs)
    assert result["period_days"] == 7
    assert result["total_runs"] == 1


def test_monthly_summary_uses_30_day_window():
    runs = [
        {"timestamp": _ts(29), "success": True, "clicks": 1},   # inside 30 days
        {"timestamp": _ts(31), "success": True, "clicks": 100},  # outside 30 days
    ]
    result = monthly_summary(runs)
    assert result["period_days"] == 30
    assert result["total_runs"] == 1
