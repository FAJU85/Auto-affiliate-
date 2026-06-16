from __future__ import annotations

from datetime import datetime, timezone, timedelta
from api.utils.smart_schedule import next_fire_time, _DEFAULT_PEAK_HOURS


def _now_at_hour(h: int) -> datetime:
    return datetime.now(timezone.utc).replace(hour=h, minute=30, second=0, microsecond=0)


def test_returns_all_required_keys():
    result = next_fire_time([])
    assert {"next_utc", "next_local", "hours_until", "peak_hours"} <= result.keys()


def test_hours_until_is_non_negative():
    result = next_fire_time([])
    assert result["hours_until"] >= 0


def test_next_utc_is_valid_iso_string():
    result = next_fire_time([])
    dt = datetime.fromisoformat(result["next_utc"])
    assert dt.tzinfo is not None


def test_tz_offset_2_local_is_2h_ahead():
    result = next_fire_time([], tz_offset_hours=2)
    utc = datetime.fromisoformat(result["next_utc"])
    local = datetime.fromisoformat(result["next_local"])
    diff = local.utcoffset()
    assert diff == timedelta(hours=2)
    assert local == utc.astimezone(utc.astimezone(local.tzinfo).tzinfo)


def test_empty_runs_returns_valid_result():
    result = next_fire_time([])
    assert result["peak_hours"] == list(_DEFAULT_PEAK_HOURS)
    assert result["hours_until"] >= 0


def test_peak_hours_list_is_non_empty():
    result = next_fire_time([])
    assert len(result["peak_hours"]) > 0


def test_next_utc_is_strictly_after_now():
    result = next_fire_time([])
    dt = datetime.fromisoformat(result["next_utc"])
    assert dt > datetime.now(timezone.utc)


def test_next_fire_time_is_always_in_future():
    result = next_fire_time([])
    utc_dt = datetime.fromisoformat(result["next_utc"])
    assert utc_dt > datetime.now(timezone.utc)


def test_next_utc_minute_is_zero():
    result = next_fire_time([])
    dt = datetime.fromisoformat(result["next_utc"])
    assert dt.minute == 0
    assert dt.second == 0


def test_next_utc_hour_is_in_peak_hours():
    result = next_fire_time([])
    dt = datetime.fromisoformat(result["next_utc"])
    assert dt.hour in result["peak_hours"]


def test_tz_offset_negative():
    result = next_fire_time([], tz_offset_hours=-5)
    local = datetime.fromisoformat(result["next_local"])
    assert local.utcoffset() == timedelta(hours=-5)


def test_hours_until_matches_next_utc():
    result = next_fire_time([])
    now = datetime.now(timezone.utc)
    dt = datetime.fromisoformat(result["next_utc"])
    expected = (dt - now).total_seconds() / 3600
    assert abs(result["hours_until"] - expected) < 0.01
