"""Tests for smart scheduling (Build #10)."""

import pytest


def _make_runs(hours: list[int], clicks: int = 0) -> list[dict]:
    """Generate fake successful run history with given UTC hours."""
    return [
        {"success": True, "timestamp": f"2026-06-01T{h:02d}:00:00Z", "clicks": clicks}
        for h in hours
    ]


class TestComputePeakHours:
    def test_returns_default_when_insufficient_data(self):
        from api.utils.smart_schedule import compute_peak_hours, _DEFAULT_PEAK_HOURS
        runs = _make_runs([9, 12], clicks=0)  # only 2 points, below MIN_DATA_POINTS
        result = compute_peak_hours(runs)
        assert result == list(_DEFAULT_PEAK_HOURS[:4])

    def test_returns_top_n_hours_sorted(self):
        from api.utils.smart_schedule import compute_peak_hours, MIN_DATA_POINTS
        # 25 runs at hour 14, 5 runs at other hours
        runs = _make_runs([14] * 25 + [9, 10, 11, 12, 13], clicks=0)
        assert len([r for r in runs if r["success"]]) >= MIN_DATA_POINTS
        peaks = compute_peak_hours(runs, n=2)
        assert 14 in peaks

    def test_click_bonus_influences_ranking(self):
        from api.utils.smart_schedule import compute_peak_hours
        # Hour 20 has few runs but many clicks; hour 9 has many runs but zero clicks
        runs = (
            _make_runs([9] * 15, clicks=0)
            + _make_runs([20] * 10, clicks=5)
        )
        peaks = compute_peak_hours(runs, n=2)
        assert 20 in peaks  # click bonus should push hour 20 up

    def test_returns_sorted_list(self):
        from api.utils.smart_schedule import compute_peak_hours
        runs = _make_runs([21, 9, 18, 12] * 6)
        peaks = compute_peak_hours(runs)
        assert peaks == sorted(peaks)

    def test_n_parameter_limits_output(self):
        from api.utils.smart_schedule import compute_peak_hours
        runs = _make_runs(list(range(24)) * 2)
        assert len(compute_peak_hours(runs, n=3)) == 3

    def test_no_runs_returns_default(self):
        from api.utils.smart_schedule import compute_peak_hours, _DEFAULT_PEAK_HOURS
        assert compute_peak_hours([]) == list(_DEFAULT_PEAK_HOURS[:4])


class TestOptimalCron:
    def test_format_is_valid_cron(self):
        from api.utils.smart_schedule import optimal_cron
        cron = optimal_cron(_make_runs([9, 12, 18, 21] * 6))
        parts = cron.split()
        assert len(parts) == 5
        assert parts[0] == "0"  # always fires at minute 0
        assert parts[2] == parts[3] == parts[4] == "*"

    def test_peak_hours_appear_in_cron(self):
        from api.utils.smart_schedule import optimal_cron
        runs = _make_runs([9] * 8 + [12] * 8 + [18] * 8)
        cron = optimal_cron(runs, n=3)
        hours_part = cron.split()[1]
        hours = [int(h) for h in hours_part.split(",")]
        assert 9 in hours
        assert 12 in hours
        assert 18 in hours

    def test_empty_runs_returns_default_cron(self):
        from api.utils.smart_schedule import optimal_cron
        cron = optimal_cron([])
        assert "0 " in cron


class TestIsPeakHour:
    def test_always_true_when_disabled(self, monkeypatch):
        monkeypatch.delenv("SMART_SCHEDULE", raising=False)
        from api.utils.smart_schedule import is_peak_hour
        assert is_peak_hour(3, []) is True  # 3am is off-peak but disabled

    def test_peak_hour_returns_true(self, monkeypatch):
        monkeypatch.setenv("SMART_SCHEDULE", "1")
        from api.utils.smart_schedule import is_peak_hour, _DEFAULT_PEAK_HOURS
        peak = _DEFAULT_PEAK_HOURS[0]
        assert is_peak_hour(peak, []) is True

    def test_off_peak_returns_false(self, monkeypatch):
        monkeypatch.setenv("SMART_SCHEDULE", "1")
        from api.utils.smart_schedule import is_peak_hour, _DEFAULT_PEAK_HOURS
        # Pick an hour not in defaults
        off_peak = next(h for h in range(24) if h not in _DEFAULT_PEAK_HOURS)
        assert is_peak_hour(off_peak, []) is False


class TestScheduleSummary:
    def test_returns_required_keys(self):
        from api.utils.smart_schedule import schedule_summary
        result = schedule_summary([])
        for key in ("peak_hours", "optimal_cron", "data_points", "sufficient_data", "hourly", "platform_priors"):
            assert key in result

    def test_hourly_has_24_entries(self):
        from api.utils.smart_schedule import schedule_summary
        result = schedule_summary(_make_runs([9, 12] * 5))
        assert len(result["hourly"]) == 24

    def test_sufficient_data_false_below_threshold(self):
        from api.utils.smart_schedule import schedule_summary
        result = schedule_summary(_make_runs([9, 12]))
        assert result["sufficient_data"] is False

    def test_peak_hours_marked_in_hourly(self):
        from api.utils.smart_schedule import schedule_summary
        result = schedule_summary([])
        peaks = result["peak_hours"]
        for entry in result["hourly"]:
            if entry["hour"] in peaks:
                assert entry["peak"] is True


class TestPipelineSmartGate:
    @pytest.mark.asyncio
    async def test_pipeline_skips_off_peak_when_enabled(self, monkeypatch):
        monkeypatch.setenv("SMART_SCHEDULE", "1")
        # Patch is_peak_hour to return False (off-peak)
        from unittest.mock import patch
        from api import pipeline
        with patch("api.utils.smart_schedule.is_peak_hour", return_value=False):
            result = await pipeline.run_pipeline()
        assert result.get("skipped") is True
        assert "off-peak" in result.get("reason", "")

    @pytest.mark.asyncio
    async def test_pipeline_runs_on_peak_hour(self, monkeypatch):
        monkeypatch.setenv("SMART_SCHEDULE", "1")
        from unittest.mock import patch, AsyncMock
        from api import pipeline
        with patch("api.utils.smart_schedule.is_peak_hour", return_value=True), \
             patch.object(pipeline, "_execute", new=AsyncMock(return_value={"ok": True, "success": True})):
            result = await pipeline.run_pipeline()
        assert result.get("skipped") is not True

    @pytest.mark.asyncio
    async def test_pipeline_ignores_gate_when_disabled(self, monkeypatch):
        monkeypatch.delenv("SMART_SCHEDULE", raising=False)
        from unittest.mock import patch, AsyncMock
        from api import pipeline
        with patch.object(pipeline, "_execute", new=AsyncMock(return_value={"ok": True, "success": True})):
            result = await pipeline.run_pipeline()
        assert result.get("skipped") is not True
