from collections import defaultdict
from datetime import datetime, timezone, timedelta


def _bucket_by_day(runs: list[dict], now: datetime) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in runs:
        try:
            ts = datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00"))
            day = ts.strftime("%Y-%m-%d")
            counts[day] += int(r.get("clicks", 1))
        except Exception:
            pass
    return dict(counts)


def _day_range(now: datetime, days: int) -> list[str]:
    return [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]


def daily_trend(runs: list[dict], days: int = 7, now: datetime | None = None) -> list[dict]:
    if now is None:
        now = datetime.now(timezone.utc)
    buckets = _bucket_by_day(runs, now)
    return [{"date": d, "clicks": buckets.get(d, 0)} for d in _day_range(now, days)]


def momentum(runs: list[dict], window: int = 3, now: datetime | None = None) -> float:
    if now is None:
        now = datetime.now(timezone.utc)
    buckets = _bucket_by_day(runs, now)
    recent = [buckets.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), 0) for i in range(window)]
    older = [buckets.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), 0) for i in range(window, window * 2)]
    recent_avg = sum(recent) / window if window else 0.0
    older_avg = sum(older) / window if window else 0.0
    if older_avg == 0:
        return 0.0 if recent_avg == 0 else 1.0
    return round((recent_avg - older_avg) / older_avg, 4)


def velocity(runs: list[dict], days: int = 7, now: datetime | None = None) -> float:
    trend = daily_trend(runs, days=days, now=now)
    if len(trend) < 2:
        return 0.0
    values = [t["clicks"] for t in trend]
    diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
    return round(sum(diffs) / len(diffs), 4)


def trend_report(runs: list[dict], days: int = 7, now: datetime | None = None) -> dict:
    if now is None:
        now = datetime.now(timezone.utc)
    trend = daily_trend(runs, days=days, now=now)
    clicks = [t["clicks"] for t in trend]
    total = sum(clicks)
    avg = round(total / len(clicks), 2) if clicks else 0.0
    peak = max(clicks) if clicks else 0
    peak_day = trend[clicks.index(peak)]["date"] if clicks else None
    mom = momentum(runs, window=min(3, days // 2 or 1), now=now)
    vel = velocity(runs, days=days, now=now)
    direction = "up" if vel > 0 else ("down" if vel < 0 else "flat")
    return {
        "days": days,
        "total_clicks": total,
        "avg_clicks_per_day": avg,
        "peak_clicks": peak,
        "peak_day": peak_day,
        "momentum": mom,
        "velocity": vel,
        "direction": direction,
        "trend": trend,
    }
