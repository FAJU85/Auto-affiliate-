from collections import defaultdict
from datetime import datetime


_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _parse_runs(runs: list[dict]) -> list[datetime]:
    timestamps = []
    for r in runs:
        try:
            ts = datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00"))
            clicks = int(r.get("clicks", 1))
            for _ in range(clicks):
                timestamps.append(ts)
        except Exception:
            pass
    return timestamps


def build_heatmap(runs: list[dict]) -> dict:
    grid: dict[int, dict[int, int]] = {d: {h: 0 for h in range(24)} for d in range(7)}
    for ts in _parse_runs(runs):
        grid[ts.weekday()][ts.hour] += 1
    return {
        "grid": {_DAYS[d]: {str(h): grid[d][h] for h in range(24)} for d in range(7)},
        "total_clicks": sum(grid[d][h] for d in range(7) for h in range(24)),
    }


def peak_hour(runs: list[dict]) -> int | None:
    hour_counts: dict[int, int] = defaultdict(int)
    for ts in _parse_runs(runs):
        hour_counts[ts.hour] += 1
    if not hour_counts:
        return None
    return max(hour_counts, key=lambda h: hour_counts[h])


def peak_day(runs: list[dict]) -> str | None:
    day_counts: dict[int, int] = defaultdict(int)
    for ts in _parse_runs(runs):
        day_counts[ts.weekday()] += 1
    if not day_counts:
        return None
    best = max(day_counts, key=lambda d: day_counts[d])
    return _DAYS[best]


def hourly_distribution(runs: list[dict]) -> list[dict]:
    hour_counts: dict[int, int] = defaultdict(int)
    for ts in _parse_runs(runs):
        hour_counts[ts.hour] += 1
    total = sum(hour_counts.values()) or 1
    return [
        {"hour": h, "clicks": hour_counts.get(h, 0), "pct": round(hour_counts.get(h, 0) / total * 100, 1)}
        for h in range(24)
    ]


def weekday_distribution(runs: list[dict]) -> list[dict]:
    day_counts: dict[int, int] = defaultdict(int)
    for ts in _parse_runs(runs):
        day_counts[ts.weekday()] += 1
    total = sum(day_counts.values()) or 1
    return [
        {"day": _DAYS[d], "clicks": day_counts.get(d, 0), "pct": round(day_counts.get(d, 0) / total * 100, 1)}
        for d in range(7)
    ]


def heatmap_summary(runs: list[dict]) -> dict:
    ph = peak_hour(runs)
    pd = peak_day(runs)
    hourly = hourly_distribution(runs)
    total = sum(e["clicks"] for e in hourly)
    return {
        "total_clicks": total,
        "peak_hour": ph,
        "peak_day": pd,
        "peak_hour_label": f"{ph:02d}:00–{ph:02d}:59 UTC" if ph is not None else None,
        "has_data": total > 0,
    }
