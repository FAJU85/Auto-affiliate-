import pytest
from datetime import datetime, timezone
from api.utils.tz_scheduler import (
    utc_to_local, local_to_utc, convert,
    optimal_post_times, best_utc_hour_for_region, multi_region_schedule,
)

_UTC_NOON = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)


def test_utc_to_local_est():
    local = utc_to_local(_UTC_NOON, "EST")
    assert local.hour == 7  # UTC-5


def test_utc_to_local_jst():
    local = utc_to_local(_UTC_NOON, "JST")
    assert local.hour == 21  # UTC+9


def test_utc_to_local_ist():
    local = utc_to_local(_UTC_NOON, "IST")
    assert local.hour == 17  # UTC+5.5 → 17:30
    assert local.minute == 30


def test_local_to_utc_est():
    local = datetime(2026, 6, 16, 7, 0)
    utc = local_to_utc(local, "EST")
    assert utc.hour == 12


def test_local_to_utc_cet():
    local = datetime(2026, 6, 16, 13, 0)
    utc = local_to_utc(local, "CET")
    assert utc.hour == 12


def test_convert_est_to_cet():
    dt = datetime(2026, 6, 16, 7, 0)
    result = convert(dt, from_tz="EST", to_tz="CET")
    assert result.hour == 13  # EST+5+1 = 13 CET


def test_convert_same_tz():
    dt = datetime(2026, 6, 16, 12, 0)
    result = convert(dt, from_tz="UTC", to_tz="UTC")
    assert result.hour == 12


def test_utc_to_local_unknown_tz():
    with pytest.raises(ValueError):
        utc_to_local(_UTC_NOON, "INVALID")


def test_optimal_post_times_length():
    result = optimal_post_times("EST", date=_UTC_NOON)
    assert len(result) == 4


def test_optimal_post_times_structure():
    result = optimal_post_times("EST", date=_UTC_NOON)
    for entry in result:
        assert "utc" in entry
        assert "local" in entry
        assert "tz" in entry


def test_optimal_post_times_tz_label():
    result = optimal_post_times("JST", date=_UTC_NOON)
    assert all(e["tz"] == "JST" for e in result)


def test_best_utc_hour_for_region_us_east():
    hour = best_utc_hour_for_region("us_east")
    assert 0 <= hour <= 23


def test_best_utc_hour_for_region_unknown():
    with pytest.raises(ValueError):
        best_utc_hour_for_region("mars")


def test_multi_region_schedule_length():
    result = multi_region_schedule(12)
    assert len(result) == 7  # 7 regions


def test_multi_region_schedule_structure():
    result = multi_region_schedule(12)
    for entry in result:
        assert "region" in entry
        assert "tz" in entry
        assert "local_hour" in entry
        assert "local_time" in entry


def test_multi_region_schedule_sorted():
    result = multi_region_schedule(12)
    regions = [r["region"] for r in result]
    assert regions == sorted(regions)
