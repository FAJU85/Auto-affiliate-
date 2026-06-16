"""Tests for api/utils/price_monitor.py — Build #36."""

import math

import pytest

from api.utils.price_monitor import (
    best_value,
    best_value_per_category,
    group_by_category,
    rank_by_value,
)


# ---------------------------------------------------------------------------
# rank_by_value
# ---------------------------------------------------------------------------

def test_rank_by_value_empty():
    assert rank_by_value([]) == []


def test_rank_by_value_adds_score_key():
    products = [{"name": "A", "price": 10.0, "commission_rate": 2.0}]
    result = rank_by_value(products)
    assert "_value_score" in result[0]
    assert result[0]["_value_score"] == pytest.approx(5.0)


def test_rank_by_value_sorted_ascending():
    products = [
        {"name": "Expensive", "price": 100.0, "commission_rate": 1.0},  # score 100
        {"name": "Cheap", "price": 10.0, "commission_rate": 1.0},       # score 10
        {"name": "Mid", "price": 50.0, "commission_rate": 2.0},         # score 25
    ]
    result = rank_by_value(products)
    scores = [p["_value_score"] for p in result]
    assert scores == sorted(scores)
    assert result[0]["name"] == "Cheap"


def test_rank_by_value_missing_price_goes_to_end():
    products = [
        {"name": "NoPriceLast"},
        {"name": "HasPrice", "price": 5.0},
    ]
    result = rank_by_value(products)
    assert result[0]["name"] == "HasPrice"
    assert result[-1]["_value_score"] == math.inf


def test_rank_by_value_zero_price_treated_as_inf():
    products = [
        {"name": "ZeroPrice", "price": 0},
        {"name": "RealPrice", "price": 1.0},
    ]
    result = rank_by_value(products)
    assert result[0]["name"] == "RealPrice"
    assert result[-1]["_value_score"] == math.inf


def test_rank_by_value_string_price_parsed():
    products = [
        {"name": "A", "price": "$29.99"},
        {"name": "B", "price": "10.00"},
    ]
    result = rank_by_value(products)
    assert result[0]["name"] == "B"
    assert result[0]["_value_score"] == pytest.approx(10.0)


def test_rank_by_value_commission_zero_uses_fallback():
    """commission_rate=0 must not cause ZeroDivisionError; falls back to 1.0."""
    products = [{"name": "X", "price": 20.0, "commission_rate": 0}]
    result = rank_by_value(products)
    assert result[0]["_value_score"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# best_value
# ---------------------------------------------------------------------------

def test_best_value_empty_returns_none():
    assert best_value([]) is None


def test_best_value_returns_lowest_score():
    products = [
        {"name": "Good", "price": 5.0, "commission_rate": 1.0},
        {"name": "Bad",  "price": 50.0, "commission_rate": 1.0},
    ]
    result = best_value(products)
    assert result["name"] == "Good"


def test_best_value_includes_score_key():
    products = [{"name": "Only", "price": 8.0}]
    result = best_value(products)
    assert "_value_score" in result


# ---------------------------------------------------------------------------
# group_by_category
# ---------------------------------------------------------------------------

def test_group_by_category_groups_correctly():
    products = [
        {"name": "A", "category": "Electronics"},
        {"name": "B", "category": "Clothing"},
        {"name": "C", "category": "Electronics"},
    ]
    groups = group_by_category(products)
    assert set(groups.keys()) == {"Electronics", "Clothing"}
    assert len(groups["Electronics"]) == 2
    assert len(groups["Clothing"]) == 1


def test_group_by_category_missing_defaults_to_general():
    products = [{"name": "NoCategory"}]
    groups = group_by_category(products)
    assert "General" in groups
    assert groups["General"][0]["name"] == "NoCategory"


# ---------------------------------------------------------------------------
# best_value_per_category
# ---------------------------------------------------------------------------

def test_best_value_per_category_one_per_category():
    products = [
        {"name": "Laptop1", "category": "Electronics", "price": 500.0, "commission_rate": 5.0},
        {"name": "Laptop2", "category": "Electronics", "price": 400.0, "commission_rate": 2.0},
        {"name": "Shirt1",  "category": "Clothing",    "price": 20.0,  "commission_rate": 1.0},
        {"name": "Shirt2",  "category": "Clothing",    "price": 10.0,  "commission_rate": 1.0},
    ]
    result = best_value_per_category(products)
    assert set(result.keys()) == {"Electronics", "Clothing"}
    # Electronics: Laptop1 score=100, Laptop2 score=200 → Laptop1 wins
    assert result["Electronics"]["name"] == "Laptop1"
    # Clothing: Shirt1 score=20, Shirt2 score=10 → Shirt2 wins
    assert result["Clothing"]["name"] == "Shirt2"
