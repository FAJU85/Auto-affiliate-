"""Auto-hashtag optimizer — generate and rank hashtags by category and CTR performance.

For each product category and platform, maintains a ranked list of hashtags.
When click data is available, hashtags that appear in high-CTR posts are boosted.

Usage:
    from api.utils.hashtag_optimizer import hashtags_for

    tags = hashtags_for("Electronics", platform="instagram", runs=runs, n=5)
    # ["#tech", "#gadgets", "#electronics", "#deals", "#techdeals"]
"""

from __future__ import annotations

import re
from collections import defaultdict

# Base hashtag pools per product category
_CATEGORY_TAGS: dict[str, list[str]] = {
    "Electronics": [
        "#tech", "#gadgets", "#electronics", "#techdeals", "#deals",
        "#innovation", "#geeky", "#techlife", "#digitallife", "#mustbuy",
    ],
    "Beauty": [
        "#beauty", "#skincare", "#selfcare", "#glowup", "#beautytips",
        "#skincareroutine", "#beautydeals", "#makeup", "#wellness", "#glow",
    ],
    "Home": [
        "#homedecor", "#homegoods", "#interiordesign", "#homestyle",
        "#livingroom", "#homefinds", "#cozy", "#householdessentials", "#deals",
    ],
    "Kitchen": [
        "#kitchen", "#cooking", "#foodie", "#kitchentools", "#homecooking",
        "#kitchenlife", "#cheflife", "#cookingathome", "#foodprep", "#deals",
    ],
    "Fashion": [
        "#fashion", "#style", "#ootd", "#outfitoftheday", "#trending",
        "#fashiondeals", "#styleinspo", "#wardrobe", "#lookoftheday", "#deals",
    ],
    "Books": [
        "#books", "#reading", "#bookrecommendation", "#bookstagram",
        "#mustread", "#booklovers", "#selfimprovement", "#learning", "#deals",
    ],
    "Sports": [
        "#fitness", "#workout", "#sports", "#health", "#activewear",
        "#fitlife", "#gym", "#exercise", "#wellbeing", "#dealsoftheday",
    ],
    "Fitness": [
        "#fitness", "#health", "#wellness", "#workout", "#gym",
        "#fitnessmotivation", "#healthylifestyle", "#activelife", "#deals",
    ],
    "Smart Home": [
        "#smarthome", "#homeautomation", "#iot", "#tech", "#smartliving",
        "#gadgets", "#connected", "#innovation", "#futuretech", "#deals",
    ],
    "Travel": [
        "#travel", "#wanderlust", "#traveltips", "#explore", "#adventure",
        "#traveldeals", "#vacation", "#trip", "#destination", "#deals",
    ],
    "General": [
        "#deals", "#shopping", "#sale", "#musthave", "#find",
        "#recommended", "#buy", "#savings", "#lifestyle", "#trending",
    ],
}

# Platform-specific hashtag count limits and styles
_PLATFORM_TAG_LIMITS: dict[str, int] = {
    "bluesky":   0,   # no hashtags per platform tone
    "mastodon":  3,
    "x":         2,
    "instagram": 8,
    "threads":   5,
    "facebook":  0,
    "tumblr":    0,
}

# Universal deal/affiliate tags always appended when space permits
_DEAL_TAGS = ["#affiliate", "#ad", "#dealsoftheday"]


def _extract_hashtags(text: str) -> list[str]:
    """Extract hashtags from caption text."""
    return re.findall(r"#\w+", text.lower())


def compute_hashtag_ctr(runs: list[dict]) -> dict[str, float]:
    """Return a mapping of hashtag → average CTR across posts containing that tag."""
    tag_clicks: dict[str, list[float]] = defaultdict(list)

    for r in runs:
        if not r.get("success"):
            continue
        caption = r.get("caption", "") or ""
        clicks = int(r.get("clicks", 0))
        impressions = 1  # each post = 1 impression
        ctr = clicks / impressions

        for tag in _extract_hashtags(caption):
            tag_clicks[tag].append(ctr)

    return {tag: sum(ctrs) / len(ctrs) for tag, ctrs in tag_clicks.items() if ctrs}


def hashtags_for(
    category: str,
    platform: str = "instagram",
    runs: list[dict] | None = None,
    n: int | None = None,
) -> list[str]:
    """Return ranked hashtags for a product category and platform.

    When run history is provided, hashtags that appear in high-CTR posts
    are boosted. Falls back to category defaults when history is insufficient.

    Args:
        category: product category (e.g. "Electronics", "Beauty")
        platform: social platform name
        runs: run history for CTR-based reranking
        n: max number of hashtags; defaults to platform limit
    """
    limit = n if n is not None else _PLATFORM_TAG_LIMITS.get(platform.lower(), 3)
    if limit == 0:
        return []

    base_tags = list(_CATEGORY_TAGS.get(category, _CATEGORY_TAGS["General"]))

    # CTR-based reranking when history available
    if runs:
        ctr_map = compute_hashtag_ctr(runs)
        if ctr_map:
            base_tags.sort(key=lambda t: ctr_map.get(t, 0.0), reverse=True)

    return base_tags[:limit]


def inject_hashtags(caption: str, tags: list[str]) -> str:
    """Append hashtags to a caption, avoiding duplicates already in the text."""
    existing = set(_extract_hashtags(caption))
    new_tags = [t for t in tags if t.lower() not in existing]
    if not new_tags:
        return caption
    return caption.rstrip() + " " + " ".join(new_tags)


def optimized_hashtags(
    product: dict,
    platform: str,
    runs: list[dict] | None = None,
) -> list[str]:
    """Convenience: return optimized hashtags for a product on a given platform."""
    category = product.get("category", "General")
    return hashtags_for(category, platform=platform, runs=runs)
