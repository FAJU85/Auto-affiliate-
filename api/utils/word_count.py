import re
import statistics

_PLATFORM_OPTIMAL: dict[str, tuple[int, int]] = {
    "bluesky":   (20, 60),
    "mastodon":  (30, 80),
    "x":         (15, 50),
    "twitter":   (15, 50),
    "instagram": (50, 150),
    "facebook":  (40, 100),
    "threads":   (20, 70),
    "tumblr":    (50, 300),
}


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def word_stats(text: str) -> dict:
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return {"count": 0, "unique": 0, "avg_length": 0.0, "longest": ""}
    lengths = [len(w) for w in words]
    return {
        "count": len(words),
        "unique": len(set(w.lower() for w in words)),
        "avg_length": round(sum(lengths) / len(lengths), 2),
        "longest": max(words, key=len),
    }


def check_length(text: str, platform: str) -> dict:
    wc = count_words(text)
    limits = _PLATFORM_OPTIMAL.get(platform.lower())
    if limits is None:
        return {"word_count": wc, "platform": platform, "status": "unknown", "optimal_range": None}
    lo, hi = limits
    if wc < lo:
        status = "too_short"
    elif wc > hi:
        status = "too_long"
    else:
        status = "optimal"
    return {
        "word_count": wc,
        "platform": platform,
        "status": status,
        "optimal_range": [lo, hi],
    }


def analyze_posts(posts: list[dict], text_field: str = "content", platform_field: str = "platform") -> list[dict]:
    results = []
    for p in posts:
        text = p.get(text_field, "") or ""
        platform = p.get(platform_field, "") or ""
        wc = count_words(text)
        check = check_length(text, platform) if platform else {"word_count": wc, "status": "unknown"}
        results.append({**p, "word_count": wc, "length_status": check["status"]})
    return results


def posts_stats(posts: list[dict], text_field: str = "content") -> dict:
    counts = [count_words(p.get(text_field, "") or "") for p in posts]
    if not counts:
        return {"count": 0, "avg": 0.0, "min": 0, "max": 0, "median": 0.0}
    return {
        "count": len(counts),
        "avg": round(sum(counts) / len(counts), 2),
        "min": min(counts),
        "max": max(counts),
        "median": round(statistics.median(counts), 2),
    }
