"""Tests for api/utils/trend_injector.py."""

from api.utils.trend_injector import (
    CATEGORY_TRENDS,
    best_trend,
    get_trends_for,
    inject_trend,
)


def test_known_category_returns_nonempty():
    result = get_trends_for("Electronics")
    assert len(result) > 0


def test_unknown_category_falls_back_to_general():
    result = get_trends_for("Underwater Basket Weaving")
    general = get_trends_for("General")
    assert result == general


def test_get_trends_for_respects_n_limit():
    result = get_trends_for("Beauty", n=2)
    assert len(result) <= 2


def test_get_trends_for_n_zero_returns_empty():
    result = get_trends_for("Sports", n=0)
    assert result == []


def test_inject_trend_with_explicit_trends_returns_unchanged():
    explicit = ["trend A", "trend B"]
    result = inject_trend({"category": "Electronics"}, trends=explicit)
    assert result == explicit


def test_inject_trend_no_trends_uses_category_lookup():
    product = {"category": "Books"}
    result = inject_trend(product)
    expected = get_trends_for("Books")
    assert result == expected


def test_inject_trend_empty_trends_uses_category_lookup():
    product = {"category": "Home"}
    result = inject_trend(product, trends=[])
    expected = get_trends_for("Home")
    assert result == expected


def test_best_trend_returns_string():
    result = best_trend({"category": "Travel"})
    assert isinstance(result, str)
    assert len(result) > 0


def test_best_trend_with_empty_runs_returns_string():
    result = best_trend({"category": "Food"}, runs=[])
    assert isinstance(result, str)
    assert len(result) > 0


def test_case_insensitive_lookup():
    lower = get_trends_for("electronics")
    upper = get_trends_for("ELECTRONICS")
    mixed = get_trends_for("Electronics")
    assert lower == upper == mixed


def test_all_defined_categories_return_at_least_one_trend():
    for category in CATEGORY_TRENDS:
        result = get_trends_for(category, n=1)
        assert len(result) >= 1, f"Category {category!r} returned no trends"


def test_best_trend_prefers_high_click_caption_match():
    # The first trend for Electronics is "best budget smartphone 2026"
    first = get_trends_for("Electronics", n=1)[0]
    # A run with clicks containing the first phrase
    runs = [{"clicks": 5, "caption": f"Check out {first} now!"}]
    result = best_trend({"category": "Electronics"}, runs=runs)
    assert result == first


def test_inject_trend_missing_category_key_uses_general():
    product: dict = {}
    result = inject_trend(product)
    expected = get_trends_for("General")
    assert result == expected
