"""Platform-aware caption length enforcement."""

PLATFORM_LIMITS: dict[str, int] = {
    "bluesky": 300,
    "x": 280,
    "mastodon": 500,
    "instagram": 2200,
    "facebook": 63206,
    "threads": 500,
    "tumblr": 4096,
    "default": 280,
}


def trim_caption(caption: str, platform: str) -> str:
    """Trim caption to platform limit, truncating at word boundary with ellipsis."""
    if not caption:
        return caption
    limit = PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS["default"])
    if len(caption) <= limit:
        return caption
    # Truncate at last word boundary before limit-3, append ellipsis
    truncated = caption[: limit - 3]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "…"


def caption_fits(caption: str, platform: str) -> bool:
    """Return True if caption is within the platform's character limit."""
    limit = PLATFORM_LIMITS.get(platform, PLATFORM_LIMITS["default"])
    return len(caption) <= limit
