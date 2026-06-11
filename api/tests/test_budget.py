"""Unit + integration tests for daily budget cap enforcement (PF-05)."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch


@pytest.fixture()
def budget_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Force re-import with new DATA_DIR
    import importlib
    import api.utils.budget as bmod
    importlib.reload(bmod)
    yield tmp_path, bmod
    importlib.reload(bmod)


class TestGetDailySpend:
    def test_zero_when_no_file(self, budget_dir):
        _, bmod = budget_dir
        assert bmod.get_daily_spend() == 0.0

    def test_returns_todays_total(self, budget_dir):
        tmp, bmod = budget_dir
        today = bmod._today()
        (tmp / "budget.json").write_text(json.dumps({today: {"total": 1.23, "default": 1.23}}))
        assert bmod.get_daily_spend() == pytest.approx(1.23)

    def test_ignores_other_days(self, budget_dir):
        tmp, bmod = budget_dir
        (tmp / "budget.json").write_text(json.dumps({"2020-01-01": {"total": 99.0}}))
        assert bmod.get_daily_spend() == 0.0


class TestAddSpend:
    def test_accumulates_spend(self, budget_dir):
        _, bmod = budget_dir
        bmod.add_spend(0.001)
        bmod.add_spend(0.002)
        assert bmod.get_daily_spend() == pytest.approx(0.003)

    def test_tracks_provider(self, budget_dir):
        tmp, bmod = budget_dir
        bmod.add_spend(0.002, "mistral")
        today = bmod._today()
        data = json.loads((tmp / "budget.json").read_text())
        assert data[today]["mistral"] == pytest.approx(0.002)

    def test_prunes_to_90_days(self, budget_dir):
        tmp, bmod = budget_dir
        # Write 95 days of history
        old_data = {f"2025-01-{i:02d}": {"total": 0.001} for i in range(1, 96)}
        (tmp / "budget.json").write_text(json.dumps(old_data))
        bmod.add_spend(0.001)
        data = json.loads((tmp / "budget.json").read_text())
        assert len(data) <= 90

    def test_atomic_write(self, budget_dir):
        """Ensure .tmp file is renamed — no partial writes."""
        tmp, bmod = budget_dir
        bmod.add_spend(0.001)
        assert not list(tmp.glob("*.tmp"))
        assert (tmp / "budget.json").exists()


class TestMonthlyForecast:
    def test_on_track_when_no_data(self, budget_dir):
        _, bmod = budget_dir
        result = bmod.get_monthly_forecast(cap=2.0)
        assert result["on_track"] is True
        assert result["monthly_est_usd"] == 0.0

    def test_forecast_scales_daily_avg(self, budget_dir):
        tmp, bmod = budget_dir
        # 7 days at $0.10/day
        from datetime import date, timedelta
        days = {
            (date.today() - timedelta(days=i)).isoformat(): {"total": 0.10}
            for i in range(7)
        }
        (tmp / "budget.json").write_text(json.dumps(days))
        result = bmod.get_monthly_forecast(cap=2.0)
        assert result["monthly_est_usd"] == pytest.approx(3.0, abs=0.01)
        assert result["on_track"] is False
