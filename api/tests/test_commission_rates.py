"""Tests for api/utils/commission_rates.py"""

import importlib
import json

import pytest


@pytest.fixture(autouse=True)
def isolated_module(tmp_path, monkeypatch):
    """Point DATA_DIR at tmp_path and reload the module for each test."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.commission_rates as mod
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(mod, "RATES_FILE", tmp_path / "commission_rates.json")
    importlib.reload(mod)
    yield mod


# ── get_rate ─────────────────────────────────────────────────────────────────

def test_get_rate_known_network(isolated_module):
    assert isolated_module.get_rate("sovrn") == 0.05


def test_get_rate_unknown_network_returns_default(isolated_module):
    assert isolated_module.get_rate("unknown_network_xyz") == 0.05


def test_get_rate_case_insensitive(isolated_module):
    assert isolated_module.get_rate("SOVRN") == isolated_module.get_rate("sovrn")
    assert isolated_module.get_rate("AdmItAd") == isolated_module.get_rate("admitad")


def test_get_rate_travelpayouts(isolated_module):
    assert isolated_module.get_rate("travelpayouts") == 0.08


# ── set_rate ─────────────────────────────────────────────────────────────────

def test_set_rate_persists(isolated_module, tmp_path):
    isolated_module.set_rate("sovrn", 0.12)
    assert isolated_module.get_rate("sovrn") == 0.12
    # Also confirm the file was written
    data = json.loads((tmp_path / "commission_rates.json").read_text())
    assert data["sovrn"] == 0.12


def test_set_rate_overrides_default(isolated_module):
    isolated_module.set_rate("default", 0.10)
    assert isolated_module.get_rate("unknown_network_xyz") == 0.10


def test_set_rate_raises_for_negative(isolated_module):
    with pytest.raises(ValueError):
        isolated_module.set_rate("sovrn", -0.01)


def test_set_rate_raises_for_above_one(isolated_module):
    with pytest.raises(ValueError):
        isolated_module.set_rate("sovrn", 1.01)


def test_set_rate_boundary_zero_ok(isolated_module):
    isolated_module.set_rate("sovrn", 0.0)
    assert isolated_module.get_rate("sovrn") == 0.0


def test_set_rate_boundary_one_ok(isolated_module):
    isolated_module.set_rate("sovrn", 1.0)
    assert isolated_module.get_rate("sovrn") == 1.0


# ── get_all_rates ─────────────────────────────────────────────────────────────

def test_get_all_rates_contains_all_defaults(isolated_module):
    rates = isolated_module.get_all_rates()
    for key in isolated_module.DEFAULT_RATES:
        assert key in rates


def test_get_all_rates_saved_rate_appears(isolated_module):
    isolated_module.set_rate("sovrn", 0.15)
    assert isolated_module.get_all_rates()["sovrn"] == 0.15


# ── estimated_monthly_commission ──────────────────────────────────────────────

def test_estimated_monthly_commission_zero_clicks(isolated_module):
    assert isolated_module.estimated_monthly_commission(0) == 0.0


def test_estimated_monthly_commission_formula(isolated_module):
    # clicks=100, conversion_rate=0.01, rate=default(0.05), *30 = 1.5
    result = isolated_module.estimated_monthly_commission(100, "default", 0.01)
    assert result == round(100 * 0.01 * 0.05 * 30, 4)


def test_estimated_monthly_commission_uses_network_rate(isolated_module):
    # travelpayouts rate is 0.08
    result = isolated_module.estimated_monthly_commission(1000, "travelpayouts", 0.02)
    assert result == round(1000 * 0.02 * 0.08 * 30, 4)
