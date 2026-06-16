from collections import defaultdict
from datetime import datetime


def _hour(ts: str) -> int | None:
    try:
        return datetime.fromisoformat(ts).hour
    except Exception:
        return None


def _weekday(ts: str) -> int | None:
    try:
        return datetime.fromisoformat(ts).weekday()
    except Exception:
        return None


_WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def peak_hours(runs: list[dict]) -> list[dict]:
    counts: dict[int, int] = defaultdict(int)
    for r in runs:
        if not r.get("success"):
            continue
        h = _hour(r.get("timestamp", ""))
        if h is not None:
            counts[h] += int(r.get("clicks", 0))
    return sorted(
        [{"hour": h, "clicks": c} for h, c in counts.items()],
        key=lambda x: x["clicks"],
        reverse=True,
    )


def peak_weekdays(runs: list[dict]) -> list[dict]:
    counts: dict[int, int] = defaultdict(int)
    for r in runs:
        if not r.get("success"):
            continue
        d = _weekday(r.get("timestamp", ""))
        if d is not None:
            counts[d] += int(r.get("clicks", 0))
    return sorted(
        [{"weekday": _WEEKDAY_NAMES[d], "weekday_num": d, "clicks": c} for d, c in counts.items()],
        key=lambda x: x["clicks"],
        reverse=True,
    )


def platform_breakdown(runs: list[dict]) -> list[dict]:
    clicks: dict[str, int] = defaultdict(int)
    posts: dict[str, int] = defaultdict(int)
    for r in runs:
        if not r.get("success"):
            continue
        p = (r.get("platform") or "unknown").lower()
        posts[p] += 1
        clicks[p] += int(r.get("clicks", 0))
    all_platforms = set(clicks) | set(posts)
    result = [
        {
            "platform": p,
            "posts": posts[p],
            "clicks": clicks[p],
            "avg_clicks": round(clicks[p] / posts[p], 2) if posts[p] else 0.0,
        }
        for p in all_platforms
    ]
    return sorted(result, key=lambda x: x["clicks"], reverse=True)


def audience_summary(runs: list[dict]) -> dict:
    hours = peak_hours(runs)
    days = peak_weekdays(runs)
    platforms = platform_breakdown(runs)
    return {
        "best_hour": hours[0]["hour"] if hours else None,
        "best_weekday": days[0]["weekday"] if days else None,
        "best_platform": platforms[0]["platform"] if platforms else None,
        "peak_hours": hours[:3],
        "peak_weekdays": days[:3],
        "platform_breakdown": platforms,
    }
