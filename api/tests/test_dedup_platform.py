"""Tests for api/utils/dedup_platform.py — per-platform deduplication."""

from datetime import datetime, timezone, timedelta

from api.utils.dedup_platform import was_posted_to_platform, filter_unposted

TTL = 24  # hours used across all tests


def _ts(hours_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _run(product, platform: str, success: bool = True, hours_ago: float = 1) -> dict:
    return {
        "success": success,
        "platform": platform,
        "product": product,
        "timestamp": _ts(hours_ago),
    }


# ── was_posted_to_platform ────────────────────────────────────────────────────

def test_no_runs_returns_false():
    assert was_posted_to_platform("Widget", "bluesky", [], TTL) is False


def test_different_platform_returns_false():
    runs = [_run("Widget", "bluesky")]
    assert was_posted_to_platform("Widget", "instagram", runs, TTL) is False


def test_matching_platform_and_product_returns_true():
    runs = [_run("Widget", "bluesky")]
    assert was_posted_to_platform("Widget", "bluesky", runs, TTL) is True


def test_case_insensitive_platform_match():
    runs = [_run("Widget", "Bluesky")]
    assert was_posted_to_platform("Widget", "BLUESKY", runs, TTL) is True


def test_case_insensitive_product_name_match():
    runs = [_run("SUPER WIDGET PRO", "bluesky")]
    assert was_posted_to_platform("super widget pro", "bluesky", runs, TTL) is True


def test_product_as_dict_with_name_key():
    runs = [_run({"name": "Fancy Gadget", "price": 9.99}, "mastodon")]
    assert was_posted_to_platform("Fancy Gadget", "mastodon", runs, TTL) is True


def test_old_run_beyond_ttl_not_counted():
    runs = [_run("Widget", "bluesky", hours_ago=TTL + 1)]
    assert was_posted_to_platform("Widget", "bluesky", runs, TTL) is False


def test_run_exactly_at_ttl_boundary_not_counted():
    # Slightly over TTL should not count
    runs = [_run("Widget", "bluesky", hours_ago=TTL + 0.01)]
    assert was_posted_to_platform("Widget", "bluesky", runs, TTL) is False


def test_failed_run_not_counted():
    runs = [_run("Widget", "bluesky", success=False)]
    assert was_posted_to_platform("Widget", "bluesky", runs, TTL) is False


def test_malformed_timestamp_skipped():
    bad_run = {"success": True, "platform": "bluesky", "product": "Widget", "timestamp": "not-a-date"}
    assert was_posted_to_platform("Widget", "bluesky", [bad_run], TTL) is False


def test_substring_product_match():
    # Product name in run is longer; needle is substring
    runs = [_run("Super Widget Pro", "bluesky")]
    assert was_posted_to_platform("Widget", "bluesky", runs, TTL) is True


# ── filter_unposted ───────────────────────────────────────────────────────────

def test_filter_returns_all_when_no_runs():
    products = [{"name": "A"}, {"name": "B"}]
    result = filter_unposted(products, "bluesky", [], TTL)
    assert result == products


def test_filter_excludes_already_posted_product():
    products = [{"name": "Widget"}, {"name": "Gadget"}]
    runs = [_run("Widget", "bluesky")]
    result = filter_unposted(products, "bluesky", runs, TTL)
    assert len(result) == 1
    assert result[0]["name"] == "Gadget"


def test_filter_keeps_product_posted_to_different_platform():
    products = [{"name": "Widget"}, {"name": "Gadget"}]
    runs = [_run("Widget", "instagram")]
    result = filter_unposted(products, "bluesky", runs, TTL)
    # Widget was only posted to instagram, so both should pass for bluesky
    assert len(result) == 2


def test_filter_empty_products_returns_empty():
    runs = [_run("Widget", "bluesky")]
    assert filter_unposted([], "bluesky", runs, TTL) == []
