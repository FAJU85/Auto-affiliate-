"""Tests for api/utils/blacklist.py — persistent product blacklist."""

import importlib
import json


def _reload(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.blacklist as bl
    importlib.reload(bl)
    return bl


# ── Initial state ─────────────────────────────────────────────────────────────

def test_initial_empty(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    result = bl.get_blacklist()
    assert result == {"products": [], "domains": []}


# ── add_product ───────────────────────────────────────────────────────────────

def test_add_product_persists(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("SpamBrand")
    result = bl.get_blacklist()
    assert "spambrand" in result["products"]


def test_add_product_lowercase(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("MixedCase")
    assert "mixedcase" in bl.get_blacklist()["products"]


def test_add_product_no_duplicates(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("foo")
    bl.add_product("foo")
    bl.add_product("FOO")
    assert bl.get_blacklist()["products"].count("foo") == 1


def test_add_product_written_to_file(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("testitem")
    raw = json.loads((tmp_path / "blacklist.json").read_text())
    assert "testitem" in raw["products"]


# ── add_domain ────────────────────────────────────────────────────────────────

def test_add_domain_persists(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_domain("spam.com")
    assert "spam.com" in bl.get_blacklist()["domains"]


def test_add_domain_no_duplicates(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_domain("evil.com")
    bl.add_domain("EVIL.COM")
    assert bl.get_blacklist()["domains"].count("evil.com") == 1


# ── is_blacklisted ────────────────────────────────────────────────────────────

def test_is_blacklisted_false_for_clean_product(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    product = {"name": "Great Widget", "siteUrl": "https://example.com/widget"}
    assert bl.is_blacklisted(product) is False


def test_is_blacklisted_true_for_name_substring(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("spam")
    product = {"name": "Super Spam Gadget", "siteUrl": "https://legit.com/item"}
    assert bl.is_blacklisted(product) is True


def test_is_blacklisted_case_insensitive_name(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("casino")
    product = {"name": "CASINO Royale Deal", "siteUrl": "https://legit.com/item"}
    assert bl.is_blacklisted(product) is True


def test_is_blacklisted_true_for_domain_in_url(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_domain("spam.com")
    product = {"name": "Nice Product", "siteUrl": "https://www.spam.com/product/123"}
    assert bl.is_blacklisted(product) is True


def test_is_blacklisted_domain_substring_match(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_domain("bad.net")
    product = {"name": "Something", "deeplink": "https://shop.bad.net/deals/1"}
    assert bl.is_blacklisted(product) is True


def test_is_blacklisted_does_not_mutate_product(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("test")
    product = {"name": "Test Product", "siteUrl": "https://ok.com"}
    original = dict(product)
    bl.is_blacklisted(product)
    assert product == original


# ── remove_product / remove_domain ────────────────────────────────────────────

def test_remove_product_returns_true_when_found(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("removeme")
    assert bl.remove_product("removeme") is True
    assert "removeme" not in bl.get_blacklist()["products"]


def test_remove_product_returns_false_when_not_found(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    assert bl.remove_product("ghost") is False


def test_remove_domain_returns_true_when_found(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_domain("bye.com")
    assert bl.remove_domain("bye.com") is True
    assert "bye.com" not in bl.get_blacklist()["domains"]


def test_remove_domain_returns_false_when_not_found(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    assert bl.remove_domain("nothere.io") is False


# ── get_blacklist structure ───────────────────────────────────────────────────

def test_get_blacklist_structure(monkeypatch, tmp_path):
    bl = _reload(monkeypatch, tmp_path)
    bl.add_product("alpha")
    bl.add_domain("beta.com")
    result = bl.get_blacklist()
    assert set(result.keys()) == {"products", "domains"}
    assert isinstance(result["products"], list)
    assert isinstance(result["domains"], list)
