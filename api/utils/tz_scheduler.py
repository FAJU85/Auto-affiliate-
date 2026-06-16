from datetime import datetime, timezone, timedelta

_OFFSETS = {
    "UTC": 0,
    "EST": -5, "EDT": -4,
    "CST": -6, "CDT": -5,
    "MST": -7, "MDT": -6,
    "PST": -8, "PDT": -7,
    "GMT": 0, "BST": 1,
    "CET": 1, "CEST": 2,
    "EET": 2, "EEST": 3,
    "IST": 5.5,
    "JST": 9,
    "AEST": 10, "AEDT": 11,
    "NZST": 12,
}

_PEAK_UTC_HOURS = (9, 12, 17, 19)  # typical peak engagement hours in UTC

_REGIONS = {
    "us_east": "EST",
    "us_west": "PST",
    "europe": "CET",
    "uk": "GMT",
    "india": "IST",
    "japan": "JST",
    "australia": "AEST",
}


def _tz_offset(tz: str) -> float:
    offset = _OFFSETS.get(tz.upper())
    if offset is None:
        raise ValueError(f"Unknown timezone: {tz!r}. Known: {sorted(_OFFSETS)}")
    return offset


def utc_to_local(dt_utc: datetime, tz: str) -> datetime:
    offset_hours = _tz_offset(tz)
    offset = timedelta(hours=offset_hours)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    local_dt = dt_utc + offset
    return local_dt.replace(tzinfo=None)


def local_to_utc(dt_local: datetime, tz: str) -> datetime:
    offset_hours = _tz_offset(tz)
    offset = timedelta(hours=offset_hours)
    utc_dt = dt_local - offset
    return utc_dt.replace(tzinfo=timezone.utc)


def convert(dt: datetime, from_tz: str, to_tz: str) -> datetime:
    utc = local_to_utc(dt, from_tz)
    return utc_to_local(utc, to_tz)


def optimal_post_times(tz: str, date: datetime | None = None) -> list[dict]:
    if date is None:
        date = datetime.now(timezone.utc)
    results = []
    for hour in _PEAK_UTC_HOURS:
        utc_dt = date.replace(hour=hour, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        local_dt = utc_to_local(utc_dt, tz)
        results.append({
            "utc": utc_dt.strftime("%H:%M"),
            "local": local_dt.strftime("%H:%M"),
            "tz": tz,
        })
    return results


def best_utc_hour_for_region(region: str) -> int:
    tz = _REGIONS.get(region.lower())
    if tz is None:
        raise ValueError(f"Unknown region: {region!r}. Known: {sorted(_REGIONS)}")
    offset = _tz_offset(tz)
    target_local = 18  # aim for 6pm local
    utc_hour = (target_local - int(offset)) % 24
    return utc_hour


def multi_region_schedule(utc_hour: int) -> list[dict]:
    result = []
    base = datetime(2000, 1, 1, utc_hour, 0, tzinfo=timezone.utc)
    for region, tz in _REGIONS.items():
        local = utc_to_local(base, tz)
        result.append({
            "region": region,
            "tz": tz,
            "local_hour": local.hour,
            "local_time": local.strftime("%H:%M"),
        })
    return sorted(result, key=lambda x: x["region"])
