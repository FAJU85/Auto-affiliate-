"""Tests for the content variation engine (Build #34)."""

from api.utils.content_variations import (
    ANGLES,
    generate_all_variations,
    generate_variation,
    best_variation,
)

PRODUCT = {"name": "Wireless Earbuds", "category": "audio", "price": "$29.99"}
PRODUCT_NO_PRICE = {"name": "Running Shoes", "category": "footwear"}


def test_generate_all_variations_returns_all_angles():
    result = generate_all_variations(PRODUCT)
    assert set(result.keys()) == set(ANGLES)


def test_generate_all_variations_all_non_empty():
    result = generate_all_variations(PRODUCT)
    for angle, caption in result.items():
        assert isinstance(caption, str) and len(caption) > 0, f"Empty caption for {angle}"


def test_price_variation_contains_price():
    caption = generate_variation(PRODUCT, "price")
    assert "$29.99" in caption


def test_price_variation_without_price():
    caption = generate_variation(PRODUCT_NO_PRICE, "price")
    assert isinstance(caption, str) and len(caption) > 0
    assert "$" not in caption or "deal" in caption.lower()


def test_benefit_variation_contains_category_or_name():
    caption = generate_variation(PRODUCT, "benefit")
    assert "audio" in caption or "Wireless Earbuds" in caption


def test_curiosity_variation_ends_with_cta():
    ctas = ["Get it now!", "Shop today!", "Don't miss out!", "Grab yours!", "Check it out!"]
    caption = generate_variation(PRODUCT, "curiosity")
    assert any(caption.endswith(cta) for cta in ctas)


def test_best_variation_returns_tuple():
    result = best_variation(PRODUCT)
    assert isinstance(result, tuple) and len(result) == 2
    assert isinstance(result[0], str) and isinstance(result[1], str)


def test_best_variation_no_runs_returns_benefit():
    angle, _ = best_variation(PRODUCT)
    assert angle == "benefit"


def test_best_variation_empty_runs_returns_benefit():
    angle, _ = best_variation(PRODUCT, runs=[])
    assert angle == "benefit"


def test_deterministic_same_product_same_output():
    r1 = generate_all_variations(PRODUCT)
    r2 = generate_all_variations(PRODUCT)
    assert r1 == r2


def test_all_variations_under_300_chars():
    result = generate_all_variations(PRODUCT)
    for angle, caption in result.items():
        assert len(caption) < 300, f"{angle} caption too long: {len(caption)} chars"


def test_best_variation_picks_highest_avg_clicks():
    runs = [
        {"angle": "price", "clicks": 10},
        {"angle": "price", "clicks": 20},
        {"angle": "benefit", "clicks": 1},
        {"angle": "curiosity", "clicks": 2},
    ]
    angle, _ = best_variation(PRODUCT, runs=runs)
    assert angle == "price"


def test_best_variation_caption_is_non_empty():
    _, caption = best_variation(PRODUCT)
    assert len(caption) > 0


def test_curiosity_variation_contains_category():
    caption = generate_variation(PRODUCT, "curiosity")
    assert "audio" in caption
