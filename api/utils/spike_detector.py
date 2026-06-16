import statistics
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def _bucket_by_day(runs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in runs:
        try:
            ts = datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00"))
            day = ts.strftime("%Y-%m-%d")
            counts[day] += int(r.get("clicks", 1))
        except Exception:
            pass
    return dict(counts)


def _zscore(value: float, baseline: list[float]) -> float | None:
    if len(baseline) < 2:
        return None
    mean = sum(baseline) / len(baseline)
    std = statistics.stdev(baseline)
    if std == 0:
        return None
    return (value - mean) / std


def detect_spikes(
    runs: list[dict],
    window_days: int = 7,
    spike_zscore: float = 2.0,
    now: datetime | None = None,
) -> dict:
    if now is None:
        now = datetime.now(timezone.utc)
    buckets = _bucket_by_day(runs)

    baseline_days = [
        (now - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(1, window_days + 1)
    ]
    baseline_values = [buckets.get(d, 0) for d in baseline_days]
    today = now.strftime("%Y-%m-%d")
    today_value = buckets.get(today, 0)

    z = _zscore(today_value, baseline_values)
    baseline_mean = sum(baseline_values) / len(baseline_values) if baseline_values else 0.0
    if z is None and baseline_values:
        # stdev=0 (all baseline identical): spike if today > 2x mean, dip if today < mean/2
        is_spike = today_value > baseline_mean * (spike_zscore + 1) if baseline_mean > 0 else False
        is_dip = today_value < baseline_mean / (spike_zscore + 1) if baseline_mean > 0 else False
    else:
        is_spike = z is not None and z >= spike_zscore
        is_dip = z is not None and z <= -spike_zscore

    return {
        "today": today,
        "today_value": today_value,
        "baseline_avg": round(sum(baseline_values) / len(baseline_values), 2) if baseline_values else 0.0,
        "baseline_std": round(statistics.stdev(baseline_values), 2) if len(baseline_values) >= 2 else 0.0,
        "zscore": round(z, 3) if z is not None else None,
        "is_spike": is_spike,
        "is_dip": is_dip,
        "status": "spike" if is_spike else ("dip" if is_dip else "normal"),
    }


def rolling_averages(runs: list[dict], window: int = 7) -> list[dict]:
    buckets = _bucket_by_day(runs)
    if not buckets:
        return []
    sorted_days = sorted(buckets.keys())
    result = []
    for i, day in enumerate(sorted_days):
        start = max(0, i - window + 1)
        window_vals = [buckets[sorted_days[j]] for j in range(start, i + 1)]
        result.append({
            "date": day,
            "value": buckets[day],
            "rolling_avg": round(sum(window_vals) / len(window_vals), 2),
        })
    return result
