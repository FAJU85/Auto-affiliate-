"""Per-platform post deduplication.

A product already posted to Bluesky can still be posted to Instagram,
but not to Bluesky again within the dedup window.
"""

import os
from datetime import datetime, timezone, timedelta

DEDUP_TTL_HOURS: int = int(os.environ.get("DEDUP_TTL_HOURS", "24"))


def _extract_product_name(product) -> str:
    """Return a normalised product name string from a run's 'product' field."""
    if isinstance(product, dict):
        return str(product.get("name", "")).lower()
    return str(product or "").lower()


def was_posted_to_platform(
    product_name: str,
    platform: str,
    runs: list[dict],
    ttl_hours: int = DEDUP_TTL_HOURS,
) -> bool:
    """Return True if a successful run with matching product_name AND platform
    exists within the last *ttl_hours*.

    - product_name matching: case-insensitive substring
    - platform matching: exact, case-insensitive
    """
    needle = product_name.lower()
    plat = platform.lower()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)

    for run in runs:
        if not run.get("success"):
            continue
        if run.get("platform", "").lower() != plat:
            continue
        run_name = _extract_product_name(run.get("product"))
        if needle not in run_name and run_name not in needle:
            continue
        try:
            ts = datetime.fromisoformat(run.get("timestamp", ""))
            if ts > cutoff:
                return True
        except Exception:
            continue  # malformed timestamp → skip

    return False


def filter_unposted(
    products: list[dict],
    platform: str,
    runs: list[dict],
    ttl_hours: int = DEDUP_TTL_HOURS,
) -> list[dict]:
    """Return products not yet posted to *platform* within the TTL window."""
    return [
        p
        for p in products
        if not was_posted_to_platform(
            p.get("name", ""), platform, runs, ttl_hours
        )
    ]
