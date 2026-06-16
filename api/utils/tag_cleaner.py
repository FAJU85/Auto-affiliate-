import re

_PLATFORM_LIMITS = {
    "twitter": 5,
    "instagram": 30,
    "facebook": 10,
    "mastodon": 10,
    "bluesky": 8,
    "threads": 30,
    "tumblr": 20,
}


def normalize(tag: str) -> str:
    tag = tag.lstrip("#").strip()
    tag = re.sub(r"[^\w]", "", tag, flags=re.UNICODE)
    return tag.lower()


def clean(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for t in tags:
        n = normalize(t)
        if n and n not in seen:
            seen.add(n)
            result.append(n)
    return result


def format_tags(tags: list[str], prefix: str = "#") -> list[str]:
    return [f"{prefix}{t}" for t in tags]


def limit_for_platform(tags: list[str], platform: str) -> list[str]:
    limit = _PLATFORM_LIMITS.get(platform.lower())
    return tags[:limit] if limit is not None else tags


def clean_for_platform(tags: list[str], platform: str) -> list[str]:
    return limit_for_platform(clean(tags), platform)


def tag_stats(tags: list[str]) -> dict:
    cleaned = clean(tags)
    return {
        "input_count": len(tags),
        "cleaned_count": len(cleaned),
        "duplicates_removed": len(tags) - len(cleaned),
        "tags": cleaned,
    }
