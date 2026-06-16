from datetime import datetime, timezone
from api.utils.seasonal_detector import (
    current_season, active_holidays, is_seasonal, seasonal_context, boost_seasonal,
)

_JUN = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
_DEC = datetime(2026, 12, 15, 12, 0, tzinfo=timezone.utc)
_NOV = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
_FEB = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)


def test_june_is_summer():
    assert current_season(_JUN) == "summer"


def test_december_is_winter():
    assert current_season(_DEC) == "winter"


def test_active_holidays_december():
    holidays = active_holidays(_DEC)
    assert "christmas" in holidays


def test_active_holidays_november():
    holidays = active_holidays(_NOV)
    assert "black_friday" in holidays


def test_active_holidays_february():
    holidays = active_holidays(_FEB)
    assert "valentines" in holidays


def test_is_seasonal_beach_in_june():
    p = {"name": "Beach Towel", "description": "perfect for summer", "category": "Sports"}
    assert is_seasonal(p, _JUN) is True


def test_is_seasonal_christmas_gift_in_december():
    p = {"name": "Christmas Gift Set", "description": "holiday special", "category": "Toys"}
    assert is_seasonal(p, _DEC) is True


def test_is_seasonal_false_for_unrelated():
    p = {"name": "Plain Notebook", "description": "lined paper", "category": "Office"}
    assert is_seasonal(p, _JUN) is False


def test_seasonal_context_has_keys():
    ctx = seasonal_context(_JUN)
    assert "season" in ctx
    assert "active_holidays" in ctx


def test_seasonal_context_correct_season():
    assert seasonal_context(_JUN)["season"] == "summer"


def test_boost_seasonal_puts_seasonal_first():
    seasonal = {"name": "Beach Ball", "description": "summer fun", "category": "Sports"}
    plain = {"name": "Stapler", "description": "office use", "category": "Office"}
    result = boost_seasonal([plain, seasonal], now=_JUN)
    assert result[0] == seasonal


def test_boost_seasonal_empty():
    assert boost_seasonal([], now=_JUN) == []


def test_active_holidays_returns_list():
    assert isinstance(active_holidays(_JUN), list)
