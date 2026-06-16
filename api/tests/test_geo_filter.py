"""Tests for api.utils.geo_filter."""

from api.utils.geo_filter import (
    detect_product_region,
    filter_by_region,
    is_allowed_region,
)


def test_empty_allowed_allows_all():
    products = [{"url": "https://example.co.uk/item"}, {"url": "https://example.de/item"}]
    assert filter_by_region(products, []) == products


def test_detect_uk():
    product = {"url": "https://www.shop.co.uk/product"}
    assert detect_product_region(product) == "UK"


def test_detect_de():
    product = {"url": "https://www.shop.de/product"}
    assert detect_product_region(product) == "DE"


def test_detect_us():
    product = {"url": "https://www.shop.com/product"}
    assert detect_product_region(product) == "US"


def test_detect_au():
    product = {"url": "https://www.shop.com.au/product"}
    assert detect_product_region(product) == "AU"


def test_detect_unknown_returns_none():
    product = {"url": "https://example.xyz/product"}
    assert detect_product_region(product) is None


def test_is_allowed_region_true_when_in_allowed():
    product = {"url": "https://www.shop.co.uk/product"}
    assert is_allowed_region(product, ["UK", "DE"]) is True


def test_is_allowed_region_false_when_not_in_allowed():
    product = {"url": "https://www.shop.de/product"}
    assert is_allowed_region(product, ["UK"]) is False


def test_is_allowed_region_true_when_unknown():
    product = {"url": "https://example.xyz/product"}
    assert is_allowed_region(product, ["UK"]) is True


def test_filter_by_region_returns_subset():
    products = [
        {"url": "https://www.shop.co.uk/item"},
        {"url": "https://www.shop.de/item"},
        {"url": "https://www.shop.fr/item"},
    ]
    result = filter_by_region(products, ["UK", "FR"])
    assert len(result) == 2
    assert products[0] in result
    assert products[2] in result


def test_case_insensitive_allowed():
    product = {"url": "https://www.shop.co.uk/item"}
    assert is_allowed_region(product, ["uk"]) is True


def test_region_field_takes_precedence():
    product = {"url": "https://www.shop.de/item", "region": "FR"}
    assert detect_product_region(product) == "FR"


def test_region_field_overrides_url_for_filter():
    product = {"url": "https://www.shop.de/item", "region": "FR"}
    assert is_allowed_region(product, ["FR"]) is True
    assert is_allowed_region(product, ["DE"]) is False


def test_no_url_returns_none():
    product = {}
    assert detect_product_region(product) is None
