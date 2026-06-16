import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.blacklist as m
    importlib.reload(m)
    return m


def test_add_domain(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.add("domains", "spam.com") is True


def test_add_duplicate_returns_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("domains", "spam.com")
    assert m.add("domains", "spam.com") is False


def test_remove_domain(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("domains", "spam.com")
    assert m.remove("domains", "spam.com") is True
    assert m.is_blocked_domain("https://spam.com/product") is False


def test_remove_nonexistent_returns_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.remove("domains", "nothere.com") is False


def test_invalid_category_raises(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        m.add("invalid", "foo")


def test_is_blocked_domain(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("domains", "spam.com")
    assert m.is_blocked_domain("https://spam.com/item") is True
    assert m.is_blocked_domain("https://legit.com/item") is False


def test_is_blocked_keyword(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("keywords", "scam")
    assert m.is_blocked_keyword("This is a scam product") is True
    assert m.is_blocked_keyword("This is a great product") is False


def test_is_blocked_keyword_whole_word(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("keywords", "cam")
    assert m.is_blocked_keyword("camera deal") is False


def test_is_blocked_product(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("product_ids", "P123")
    assert m.is_blocked_product("P123") is True
    assert m.is_blocked_product("P999") is False


def test_is_blocked_product_case_insensitive(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("product_ids", "p123")
    assert m.is_blocked_product("P123") is True


def test_is_blocked_by_domain(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("domains", "spam.com")
    product = {"id": "p1", "url": "https://spam.com/item", "title": "Nice product"}
    assert m.is_blocked(product) is True


def test_is_blocked_by_keyword(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("keywords", "scam")
    product = {"id": "p1", "url": "https://legit.com/item", "title": "Total scam deal"}
    assert m.is_blocked(product) is True


def test_filter_products(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("domains", "spam.com")
    products = [
        {"id": "p1", "url": "https://legit.com/item", "title": "Good deal"},
        {"id": "p2", "url": "https://spam.com/item", "title": "Bad deal"},
    ]
    result = m.filter_products(products)
    assert len(result) == 1
    assert result[0]["id"] == "p1"


def test_list_blocked_all(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("domains", "spam.com")
    m.add("keywords", "scam")
    bl = m.list_blocked()
    assert "domains" in bl
    assert "keywords" in bl
    assert "product_ids" in bl


def test_list_blocked_category(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("domains", "spam.com")
    bl = m.list_blocked("domains")
    assert "spam.com" in bl["domains"]


def test_blacklist_stats(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add("domains", "spam.com")
    m.add("keywords", "scam")
    s = m.blacklist_stats()
    assert s["domains"] == 1
    assert s["keywords"] == 1
    assert s["total"] == 2
