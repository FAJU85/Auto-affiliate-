"""Image quality scorer — ranks product image URLs by heuristic signals."""

from __future__ import annotations

import re
from urllib.parse import urlparse


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_LARGE_HINTS = re.compile(r"large|big|high|1200|800|original", re.IGNORECASE)
_SMALL_HINTS = re.compile(r"thumb|small|50x|75x|100x", re.IGNORECASE)
_CDN_PREFIXES = {"images.", "img.", "cdn.", "media.", "static."}
_PLACEHOLDER_HINTS = re.compile(
    r"placeholder|noimage|default|blank|missing", re.IGNORECASE
)


def score_image_url(url: str | None) -> float:
    """Return a 0.0–1.0 quality score for an image URL using heuristics only."""
    if not url:
        return 0.0

    score = 0.5  # neutral baseline

    # Extension bonus
    path = urlparse(url).path.lower()
    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    if ext in _IMAGE_EXTENSIONS:
        score += 0.3

    # Large size hint bonus
    if _LARGE_HINTS.search(url):
        score += 0.2

    # Small size hint penalty
    if _SMALL_HINTS.search(url):
        score -= 0.3

    # CDN domain bonus
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    if any(host.startswith(prefix) for prefix in _CDN_PREFIXES):
        score += 0.1

    # Placeholder/blank penalty
    if _PLACEHOLDER_HINTS.search(url):
        score -= 0.5

    return max(0.0, min(1.0, score))


def best_image_url(urls: list[str]) -> str | None:
    """Return the URL with the highest quality score, or None if the list is empty."""
    if not urls:
        return None
    scored = [(u, score_image_url(u)) for u in urls]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[0][0]


def rank_image_urls(urls: list[str]) -> list[tuple[str, float]]:
    """Return (url, score) pairs sorted descending by score."""
    scored = [(u, score_image_url(u)) for u in urls]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored
