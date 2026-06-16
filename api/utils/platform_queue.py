"""Platform queue utilities: detect enabled platforms and summarize post results."""

from dataclasses import dataclass, field


PLATFORM_CREDENTIALS: dict[str, list[str]] = {
    "bluesky":   ["bskyHandle", "bskyAppPassword"],
    "mastodon":  ["mastodonInstance", "mastodonToken"],
    "x":         ["twitterApiKey", "twitterApiSecret", "twitterAccessToken", "twitterAccessSecret"],
    "instagram": ["instagramToken"],
    "facebook":  ["facebookToken"],
    "threads":   ["threadsToken"],
    "tumblr":    ["tumblrApiKey", "tumblrApiSecret", "tumblrBlogName"],
}


def get_enabled_platforms(settings: dict) -> list[str]:
    enabled = []
    for platform, keys in PLATFORM_CREDENTIALS.items():
        if all(settings.get(k) for k in keys):
            enabled.append(platform)
    return enabled


@dataclass
class PlatformResult:
    platform: str
    success: bool
    post_url: str | None = field(default=None)
    error: str | None = field(default=None)


def summarize_results(results: list[PlatformResult]) -> dict:
    succeeded = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    return {
        "total": len(results),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "platforms": [
            {
                "platform": r.platform,
                "success": r.success,
                "post_url": r.post_url,
                "error": r.error,
            }
            for r in results
        ],
    }
