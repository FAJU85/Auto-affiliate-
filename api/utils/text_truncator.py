import re

_PLATFORM_LIMITS: dict[str, int] = {
    "bluesky": 300,
    "mastodon": 500,
    "x": 280,
    "twitter": 280,
    "instagram": 2200,
    "facebook": 63206,
    "threads": 500,
    "tumblr": 4096,
}

_URL_RE = re.compile(r"https?://[^\s]+")


def platform_limit(platform: str) -> int | None:
    return _PLATFORM_LIMITS.get(platform.lower())


def truncate(text: str, max_chars: int, suffix: str = "…") -> str:
    if len(text) <= max_chars:
        return text
    cut = max_chars - len(suffix)
    if cut <= 0:
        return suffix[:max_chars]
    truncated = text[:cut]
    last_space = truncated.rfind(" ")
    if last_space > cut // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip() + suffix


def truncate_for_platform(text: str, platform: str, suffix: str = "…") -> str:
    limit = platform_limit(platform)
    if limit is None:
        return text
    return truncate(text, limit, suffix)


def fits(text: str, platform: str) -> bool:
    limit = platform_limit(platform)
    if limit is None:
        return True
    return len(text) <= limit


def split_for_thread(text: str, platform: str, overlap: str = "") -> list[str]:
    limit = platform_limit(platform)
    if limit is None:
        return [text]
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break
        cut = limit - len(overlap)
        chunk = remaining[:cut]
        last_space = chunk.rfind(" ")
        if last_space > cut // 2:
            chunk = chunk[:last_space]
        parts.append(chunk.rstrip() + overlap)
        remaining = remaining[len(chunk):].lstrip()
    return parts


def char_count(text: str, platform: str) -> dict:
    limit = platform_limit(platform)
    used = len(text)
    return {
        "used": used,
        "limit": limit,
        "remaining": (limit - used) if limit else None,
        "fits": (used <= limit) if limit else True,
    }
