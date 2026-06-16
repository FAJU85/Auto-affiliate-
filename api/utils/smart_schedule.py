"""Smart scheduling: compute peak engagement hours from run history.

Analyses click-weighted post history to recommend the best hours to post.
The pipeline uses this to skip posting in low-engagement windows when
SMART_SCHEDULE=1 is set and enough history exists (≥MIN_DATA_POINTS runs).
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

MIN_DATA_POINTS = 20   # need at least this many successful posts to trust the data
TOP_HOURS = 4          # how many peak hours to recommend per day

# Platform-agnostic peak hours (UTC) used as fallback when no history exists.
# Based on published research for US/EU audiences.
_DEFAULT_PEAK_HOURS = [9, 12, 18, 21]

_PLATFORM_PEAKS: dict[str, list[int]] = {
    "bluesky":   [8, 12, 17, 20],
    "mastodon":  [9, 13, 18, 21],
    "x":         [9, 12, 17, 20],
    "instagram": [11, 14, 19, 21],
    "facebook":  [9, 13, 18, 20],
    "threads":   [10, 14, 18, 21],
    "tumblr":    [7, 10, 19, 23],
}


def compute_peak_hours(runs: list[dict], n: int = TOP_HOURS) -> list[int]:
    """Return the top-n peak UTC hours derived from successful run history.

    Falls back to ``_DEFAULT_PEAK_HOURS`` when there is insufficient data.
    """
    successes = [r for r in runs if r.get("success")]
    if len(successes) < MIN_DATA_POINTS:
        return list(_DEFAULT_PEAK_HOURS[:n])

    hour_scores: dict[int, float] = defaultdict(float)
    for r in successes:
        ts = r.get("timestamp", "")
        try:
            hour = int(str(ts)[11:13])
        except (ValueError, TypeError):
            continue
        if not 0 <= hour <= 23:
            continue
        clicks = int(r.get("clicks", 0))
        hour_scores[hour] += 1 + clicks  # 1 base + click bonus

    if not hour_scores:
        return list(_DEFAULT_PEAK_HOURS[:n])

    ranked = sorted(hour_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted([h for h, _ in ranked[:n]])


def peak_hours_for_platform(platform: str, runs: list[dict]) -> list[int]:
    """Return peak hours for a specific platform, blending history with priors."""
    history_peaks = compute_peak_hours(runs, n=TOP_HOURS)
    platform_priors = _PLATFORM_PEAKS.get(platform.lower(), _DEFAULT_PEAK_HOURS)

    # If enough history, trust it; otherwise blend with platform priors
    successes = [r for r in runs if r.get("success")]
    if len(successes) >= MIN_DATA_POINTS:
        return history_peaks

    # Blend: union of history and priors, capped at TOP_HOURS
    merged = sorted(set(history_peaks[:2] + platform_priors[:2]))[:TOP_HOURS]
    return merged


def is_peak_hour(current_hour: int, runs: list[dict]) -> bool:
    """Return True if current_hour falls within peak posting hours."""
    if not _smart_schedule_enabled():
        return True  # disabled → always OK to post
    peaks = compute_peak_hours(runs)
    return current_hour in peaks


def _smart_schedule_enabled() -> bool:
    return os.environ.get("SMART_SCHEDULE", "").strip() in ("1", "true", "yes")


def optimal_cron(runs: list[dict], n: int = TOP_HOURS) -> str:
    """Generate a cron expression that fires at the top-n peak hours (minute 0)."""
    hours = compute_peak_hours(runs, n=n)
    if not hours:
        return "0 9,12,18,21 * * *"
    return "0 " + ",".join(str(h) for h in hours) + " * * *"


def schedule_summary(runs: list[dict]) -> dict:
    """Return a summary dict for the /api/schedule/optimal endpoint."""
    peaks = compute_peak_hours(runs)
    cron = optimal_cron(runs)
    successes = [r for r in runs if r.get("success")]
    data_points = len(successes)

    hour_scores: dict[int, float] = defaultdict(float)
    for r in successes:
        ts = r.get("timestamp", "")
        try:
            hour = int(str(ts)[11:13])
        except (ValueError, TypeError):
            continue
        if 0 <= hour <= 23:
            hour_scores[hour] += 1 + int(r.get("clicks", 0))

    hourly = [
        {"hour": h, "score": round(hour_scores.get(h, 0), 2), "peak": h in peaks}
        for h in range(24)
    ]

    return {
        "peak_hours": peaks,
        "optimal_cron": cron,
        "data_points": data_points,
        "sufficient_data": data_points >= MIN_DATA_POINTS,
        "hourly": hourly,
        "platform_priors": _PLATFORM_PEAKS,
    }
