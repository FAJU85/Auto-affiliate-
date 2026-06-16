"""Tests for api/utils/category_detector.py — Build #17."""

from api.utils.category_detector import detect_category, ensure_category


# ── detect_category ───────────────────────────────────────────────────────────

def test_electronics_keyword_in_name():
    product = {"name": "Wireless Bluetooth Headphones", "description": ""}
    assert detect_category(product) == "Electronics"


def test_beauty_keyword_in_name():
    product = {"name": "Hydrating Moisturizer with Vitamin C Serum", "description": ""}
    assert detect_category(product) == "Beauty"


def test_fashion_keyword_in_name():
    product = {"name": "Men's Running Sneakers", "description": ""}
    assert detect_category(product) == "Fashion"


def test_home_keyword_in_name():
    product = {"name": "Non-stick Cookware Pan Set", "description": ""}
    assert detect_category(product) == "Home"


def test_sports_keyword_in_name():
    product = {"name": "Adjustable Dumbbell Set for Home Gym", "description": ""}
    assert detect_category(product) == "Sports"


def test_books_keyword_in_name():
    product = {"name": "Self-Help Book: Atomic Habits", "description": ""}
    assert detect_category(product) == "Books"


def test_toys_keyword_in_name():
    product = {"name": "LEGO City Building Set", "description": ""}
    assert detect_category(product) == "Toys"


def test_health_keyword_in_name():
    product = {"name": "Daily Probiotic Supplement", "description": ""}
    assert detect_category(product) == "Health"


def test_travel_keyword_in_name():
    product = {"name": "Lightweight Carry-On Suitcase", "description": ""}
    assert detect_category(product) == "Travel"


def test_food_keyword_in_name():
    product = {"name": "Organic Dark Chocolate Snack Bars", "description": ""}
    assert detect_category(product) == "Food"


def test_unknown_product_returns_general():
    product = {"name": "Xyz Widget Thingamajig 3000", "description": ""}
    assert detect_category(product) == "General"


def test_case_insensitive_matching():
    product = {"name": "BLUETOOTH SPEAKER", "description": ""}
    assert detect_category(product) == "Electronics"


def test_description_contributes_to_detection():
    product = {"name": "Daily Capsule", "description": "Contains vitamin D, zinc and probiotic for immune support."}
    assert detect_category(product) == "Health"


# ── ensure_category ───────────────────────────────────────────────────────────

def test_ensure_category_fills_missing_category():
    product = {"name": "Noise Cancelling Headphones", "description": ""}
    result = ensure_category(product)
    assert result["category"] == "Electronics"


def test_ensure_category_preserves_existing_category():
    product = {"name": "Noise Cancelling Headphones", "description": "", "category": "Gadgets"}
    result = ensure_category(product)
    assert result["category"] == "Gadgets"


def test_ensure_category_returns_copy_not_mutation():
    product = {"name": "Wireless Earbuds", "description": ""}
    result = ensure_category(product)
    # Input should not be mutated
    assert "category" not in product
    assert result["category"] == "Electronics"


def test_ensure_category_handles_none_category():
    product = {"name": "Yoga Mat", "description": "For fitness and workout sessions.", "category": None}
    result = ensure_category(product)
    assert result["category"] == "Sports"


def test_ensure_category_handles_empty_string_category():
    product = {"name": "Camping Backpack", "description": "Great for hiking and travel.", "category": ""}
    result = ensure_category(product)
    # empty string is falsy → should be filled
    assert result["category"] != ""
