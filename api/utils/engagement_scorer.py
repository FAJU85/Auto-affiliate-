from datetime import datetime, timezone

_PLATFORM_WEIGHTS = {
    "twitter": 1.0,
    "instagram": 1.2,
    "bluesky": 0.8,
    "mastodon": 0.7,
    "facebook": 0.9,
    "threads": 1.1,
    "tumblr": 0.6,
}

_PEAK_HOURS = {9, 12, 13, 17, 18, 19, 20}  # UTC approximate peaks
_PEAK_DAYS = {0, 1, 2, 3, 4}  # Mon–Fri

_POSITIVE_SIGNALS = {"free", "deal", "sale", "discount", "off", "limited", "exclusive", "save", "win", "gift"}
_NEGATIVE_SIGNALS = {"spam", "ad", "promo", "buy now"}


def _content_score(text: str) -> float:
    lower = text.lower()
    words = set(lower.split())
    pos = sum(1 for w in _POSITIVE_SIGNALS if w in words)
    neg = sum(1 for w in _NEGATIVE_SIGNALS if w in lower)
    has_hashtag = "#" in text
    has_emoji = any(ord(c) > 127 for c in text)
    has_url = "http" in lower
    score = 0.5
    score += pos * 0.05
    score -= neg * 0.1
    score += 0.1 if has_hashtag else 0
    score += 0.05 if has_emoji else 0
    score += 0.05 if has_url else 0
    return min(1.0, max(0.0, round(score, 3)))


def _time_score(dt: datetime) -> float:
    score = 0.5
    if dt.hour in _PEAK_HOURS:
        score += 0.3
    if dt.weekday() in _PEAK_DAYS:
        score += 0.2
    return min(1.0, score)


def score(
    platform: str,
    content: str,
    post_time: datetime | None = None,
) -> dict:
    if post_time is None:
        post_time = datetime.now(timezone.utc)
    platform_weight = _PLATFORM_WEIGHTS.get(platform.lower(), 1.0)
    content_s = _content_score(content)
    time_s = _time_score(post_time)
    raw = (content_s * 0.5 + time_s * 0.5) * platform_weight
    normalized = min(1.0, round(raw, 3))
    return {
        "platform": platform,
        "content_score": content_s,
        "time_score": time_s,
        "platform_weight": platform_weight,
        "engagement_score": normalized,
        "grade": _grade(normalized),
    }


def _grade(s: float) -> str:
    if s >= 0.8:
        return "A"
    if s >= 0.6:
        return "B"
    if s >= 0.4:
        return "C"
    return "D"


def score_batch(posts: list[dict]) -> list[dict]:
    results = []
    for p in posts:
        s = score(
            platform=p.get("platform", "twitter"),
            content=p.get("content", ""),
            post_time=p.get("post_time"),
        )
        results.append({**p, **s})
    return results


def best_platform(content: str, post_time: datetime | None = None) -> str:
    scores = {p: score(p, content, post_time)["engagement_score"] for p in _PLATFORM_WEIGHTS}
    return max(scores, key=lambda p: scores[p])
