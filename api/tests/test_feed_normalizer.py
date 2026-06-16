from api.utils.feed_normalizer import normalize, normalize_batch, drop_incomplete, normalization_report


def test_normalize_standard_fields():
    item = {"title": "Hat", "price": "19.99", "url": "https://a.com", "image": "https://img.com/x.jpg"}
    r = normalize(item)
    assert r["title"] == "Hat"
    assert r["price"] == 19.99
    assert r["url"] == "https://a.com"
    assert r["image"] == "https://img.com/x.jpg"


def test_normalize_alias_fields():
    item = {"name": "Shoes", "cost": "$49.00", "link": "https://b.com"}
    r = normalize(item)
    assert r["title"] == "Shoes"
    assert r["price"] == 49.0
    assert r["url"] == "https://b.com"


def test_normalize_missing_optional_is_none():
    r = normalize({"title": "T", "url": "https://a.com"})
    assert r["image"] is None
    assert r["description"] is None


def test_normalize_price_with_currency_symbol():
    r = normalize({"price": "$29.99"})
    assert r["price"] == 29.99


def test_normalize_price_comma_decimal():
    r = normalize({"price": "19,99"})
    assert r["price"] == 19.99


def test_normalize_price_none():
    r = normalize({"title": "T"})
    assert r["price"] is None


def test_normalize_preserves_raw():
    item = {"title": "Hat", "custom_field": "xyz"}
    r = normalize(item)
    assert r["_raw"]["custom_field"] == "xyz"


def test_normalize_empty_title_is_empty_string():
    r = normalize({})
    assert r["title"] == ""


def test_normalize_batch_length():
    items = [{"title": "A"}, {"title": "B"}]
    assert len(normalize_batch(items)) == 2


def test_drop_incomplete_filters_missing_url():
    items = [{"title": "A", "url": "https://a.com"}, {"title": "B"}]
    result = drop_incomplete(items)
    assert len(result) == 1
    assert result[0]["title"] == "A"


def test_drop_incomplete_custom_require():
    items = [{"title": "A", "url": "https://a.com", "price": "10"}]
    result = drop_incomplete(items, require=["title", "url", "price"])
    assert len(result) == 1


def test_drop_incomplete_empty():
    assert drop_incomplete([]) == []


def test_normalization_report_structure():
    items = [{"title": "A", "url": "https://a.com", "price": "10"}]
    r = normalization_report(items)
    assert "total" in r
    assert "coverage" in r


def test_normalization_report_pct():
    items = [
        {"title": "A", "url": "https://a.com"},
        {"title": "B"},
    ]
    r = normalization_report(items)
    assert r["coverage"]["url"]["count"] == 1
    assert r["coverage"]["url"]["pct"] == 50.0


def test_normalization_report_empty():
    r = normalization_report([])
    assert r["total"] == 0
