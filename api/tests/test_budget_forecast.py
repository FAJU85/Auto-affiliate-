"""Tests for budget forecasting & spend alerts (Build #14)."""

import pytest
from datetime import datetime, timezone, timedelta


def _ts(days_ago: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


def _run(clicks: int = 0, days_ago: float = 0) -> dict:
    return {"success": True, "clicks": clicks, "timestamp": _ts(days_ago)}


class TestSpendAlert:
    def test_no_alert_below_threshold(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        importlib.reload(b)
        # zero spend → no alert
        assert b.spend_alert(cap=2.0) is None

    def test_warning_at_80pct(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        importlib.reload(b)
        b.add_spend(1.61)  # 80.5% of $2.00 cap
        alert = b.spend_alert(cap=2.0)
        assert alert is not None
        assert alert["level"] == "warning"

    def test_critical_at_100pct(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        importlib.reload(b)
        b.add_spend(2.5)  # over cap
        alert = b.spend_alert(cap=2.0)
        assert alert is not None
        assert alert["level"] == "critical"

    def test_none_when_cap_is_zero(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        importlib.reload(b)
        assert b.spend_alert(cap=0) is None

    def test_alert_contains_pct_of_cap(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        importlib.reload(b)
        b.add_spend(1.8)
        alert = b.spend_alert(cap=2.0)
        assert alert is not None
        assert "pct_of_cap" in alert
        assert alert["pct_of_cap"] >= 80.0


class TestComputeRoi:
    def test_roi_calculated_correctly(self):
        from api.utils.budget import compute_roi
        result = compute_roi(monthly_commission=10.0, monthly_spend=2.0)
        assert result["roi"] == pytest.approx(5.0)

    def test_no_spend_returns_free_status(self):
        from api.utils.budget import compute_roi
        result = compute_roi(monthly_commission=5.0, monthly_spend=0.0)
        assert result["roi"] is None
        assert result["status"] == "free"
        assert result["profitable"] is True

    def test_roi_below_1_is_poor(self):
        from api.utils.budget import compute_roi
        result = compute_roi(monthly_commission=0.5, monthly_spend=2.0)
        assert result["status"] == "poor"
        assert result["profitable"] is False

    def test_roi_above_10_is_excellent(self):
        from api.utils.budget import compute_roi
        result = compute_roi(monthly_commission=25.0, monthly_spend=2.0)
        assert result["status"] == "excellent"
        assert result["profitable"] is True

    def test_roi_3_to_10_is_good(self):
        from api.utils.budget import compute_roi
        result = compute_roi(monthly_commission=8.0, monthly_spend=2.0)
        assert result["status"] == "good"

    def test_returns_required_keys(self):
        from api.utils.budget import compute_roi
        result = compute_roi(monthly_commission=5.0, monthly_spend=1.0)
        for key in ("roi", "status", "monthly_commission_usd", "monthly_spend_usd", "profitable"):
            assert key in result


class TestRevenueForecast:
    def test_returns_required_keys(self):
        from api.utils.budget import revenue_forecast
        result = revenue_forecast([])
        for key in ("posts_analysed", "total_clicks", "projected_monthly_usd", "days_history"):
            assert key in result

    def test_zero_clicks_zero_projection(self):
        from api.utils.budget import revenue_forecast
        runs = [_run(clicks=0) for _ in range(5)]
        result = revenue_forecast(runs)
        assert result["projected_monthly_usd"] == 0.0

    def test_clicks_increase_projection(self):
        from api.utils.budget import revenue_forecast
        runs = [_run(clicks=10) for _ in range(10)]
        result = revenue_forecast(runs)
        assert result["projected_monthly_usd"] > 0

    def test_old_runs_excluded(self):
        from api.utils.budget import revenue_forecast
        old = [_run(clicks=100, days_ago=60)]  # 60 days ago, outside 30-day window
        result = revenue_forecast(old, days_history=30)
        # Old runs (beyond 30 days) should be excluded from recent projection
        assert result["posts_analysed"] == 0

    def test_failed_runs_excluded(self):
        from api.utils.budget import revenue_forecast
        runs = [{"success": False, "clicks": 100, "timestamp": _ts(1)}]
        result = revenue_forecast(runs)
        assert result["posts_analysed"] == 0
        assert result["total_clicks"] == 0


class TestMonthlyForecast:
    def test_returns_required_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        importlib.reload(b)
        result = b.get_monthly_forecast(cap=2.0)
        for key in ("daily_avg_usd", "monthly_est_usd", "cap_usd", "cap_pct", "on_track"):
            assert key in result

    def test_on_track_when_no_spend(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        importlib.reload(b)
        result = b.get_monthly_forecast(cap=2.0)
        assert result["on_track"] is True
        assert result["monthly_est_usd"] == 0.0
