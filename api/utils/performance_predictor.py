from datetime import datetime, timezone
from collections import defaultdict

_PLATFORM_BASE: dict[str, float] = {
    "bluesky":   1.2,
    "mastodon":  0.9,
    "x":         1.5,
    "twitter":   1.5,
    "instagram": 2.0,
    "facebook":  1.3,
    "threads":   1.1,
    "tumblr":    0.8,
}

_HOUR_MULTIPLIER: dict[int, float] = {
    7: 1.3, 8: 1.4, 9: 1.5, 10: 1.4, 11: 1.3,
    12: 1.5, 13: 1.4, 17: 1.3, 18: 1.5, 19: 1.6,
    20: 1.5, 21: 1.4,
}

_CATEGORY_MULTIPLIER: dict[str, float] = {
    "electronics": 1.4, "fashion": 1.3, "beauty": 1.3,
    "fitness": 1.2, "food": 1.1, "home": 1.1,
    "health": 1.2, "travel": 1.3, "toys": 1.1,
    "sports": 1.2, "pets": 1.2,
}


def _hour_factor(hour: int) -> float:
    return _HOUR_MULTIPLIER.get(hour, 1.0)


def _platform_base(platform: str) -> float:
    return _PLATFORM_BASE.get(platform.lower(), 1.0)


def _category_factor(category: str) -> float:
    return _CATEGORY_MULTIPLIER.get((category or "").lower(), 1.0)


def _word_count_factor(word_count: int) -> float:
    if word_count < 10:
        return 0.7
    if word_count <= 50:
        return 1.0
    if word_count <= 100:
        return 0.9
    return 0.8


def predict(
    platform: str,
    hour: int | None = None,
    category: str = "",
    word_count: int = 30,
    base_clicks: float = 10.0,
) -> dict:
    if hour is None:
        hour = datetime.now(timezone.utc).hour
    pf = _platform_base(platform)
    hf = _hour_factor(hour)
    cf = _category_factor(category)
    wf = _word_count_factor(word_count)
    predicted = round(base_clicks * pf * hf * cf * wf, 2)
    return {
        "platform": platform,
        "hour": hour,
        "category": category,
        "word_count": word_count,
        "predicted_clicks": predicted,
        "factors": {
            "platform": round(pf, 3),
            "hour": round(hf, 3),
            "category": round(cf, 3),
            "word_count": round(wf, 3),
        },
    }


def best_time_to_post(platform: str, category: str = "") -> dict:
    hours = range(0, 24)
    results = [predict(platform, h, category) for h in hours]
    best = max(results, key=lambda x: x["predicted_clicks"])
    return {"best_hour": best["hour"], "predicted_clicks": best["predicted_clicks"]}


def rank_platforms(
    platforms: list[str],
    hour: int | None = None,
    category: str = "",
    word_count: int = 30,
) -> list[dict]:
    results = [predict(p, hour, category, word_count) for p in platforms]
    return sorted(results, key=lambda x: x["predicted_clicks"], reverse=True)


def learn_from_history(runs: list[dict]) -> dict:
    platform_clicks: dict[str, list[int]] = defaultdict(list)
    hour_clicks: dict[int, list[int]] = defaultdict(list)
    for r in runs:
        if not r.get("success"):
            continue
        p = (r.get("platform") or "").lower()
        c = int(r.get("clicks", 0))
        if p:
            platform_clicks[p].append(c)
        try:
            h = datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00")).hour
            hour_clicks[h].append(c)
        except Exception:
            pass
    return {
        "platform_avg": {p: round(sum(v) / len(v), 2) for p, v in platform_clicks.items()},
        "hour_avg": {h: round(sum(v) / len(v), 2) for h, v in hour_clicks.items()},
        "best_platform": max(platform_clicks, key=lambda p: sum(platform_clicks[p]) / len(platform_clicks[p]), default=None),
        "best_hour": max(hour_clicks, key=lambda h: sum(hour_clicks[h]) / len(hour_clicks[h]), default=None),
    }
