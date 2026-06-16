"""Run history analytics — weekly/monthly summaries."""

from datetime import datetime, timezone, timedelta


def summarize_runs(runs: list[dict], days: int = 30) -> dict:
    """Filter runs to the last `days` days and return aggregated stats."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    filtered = []
    for r in runs:
        ts_str = r.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts >= cutoff:
            filtered.append(r)

    total_runs = len(filtered)
    successful_runs = sum(1 for r in filtered if r.get("success"))
    failed_runs = total_runs - successful_runs
    total_clicks = sum(int(r.get("clicks", 0)) for r in filtered if r.get("success"))

    avg_clicks_per_run = total_clicks / total_runs if total_runs else 0.0
    success_rate_pct = (successful_runs / total_runs * 100.0) if total_runs else 0.0

    by_platform: dict = {}
    for r in filtered:
        platform = r.get("platform") or "unknown"
        entry = by_platform.setdefault(platform, {"runs": 0, "clicks": 0})
        entry["runs"] += 1
        if r.get("success"):
            entry["clicks"] += int(r.get("clicks", 0))

    return {
        "period_days": days,
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "total_clicks": total_clicks,
        "avg_clicks_per_run": round(avg_clicks_per_run, 4),
        "success_rate_pct": round(success_rate_pct, 4),
        "by_platform": by_platform,
    }


def weekly_summary(runs: list[dict]) -> dict:
    """Return a 7-day summary of runs."""
    return summarize_runs(runs, days=7)


def monthly_summary(runs: list[dict]) -> dict:
    """Return a 30-day summary of runs."""
    return summarize_runs(runs, days=30)
