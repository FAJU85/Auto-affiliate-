from api.utils.name_normalizer import normalize_name, names_match, normalize_product


def test_empty_string_returns_empty():
    assert normalize_name("") == ""


def test_basic_lowercase():
    assert normalize_name("Sony Headphones") == "sony headphones"


def test_strips_german_umlaut():
    assert normalize_name("Bücher") == "buecher"


def test_strips_accent_e():
    assert normalize_name("Crème Brûlée") == "creme brulee"


def test_strips_spanish_n():
    assert normalize_name("Niño") == "nino"


def test_removes_punctuation():
    result = normalize_name("Product! #1 (Best)")
    assert "!" not in result
    assert "#" not in result
    assert "(" not in result and ")" not in result


def test_collapses_spaces():
    result = normalize_name("too   many   spaces")
    assert "  " not in result


def test_names_match_identical():
    assert names_match("Sony WH-1000XM5", "Sony WH-1000XM5")


def test_names_match_accent_vs_ascii():
    assert names_match("Résumé", "Resume")


def test_names_match_different_products():
    assert not names_match("Sony Headphones", "Apple AirPods Pro")


def test_normalize_product_preserves_other_fields():
    p = {"name": "Ücool Product", "price": 9.99}
    result = normalize_product(p)
    assert result["price"] == 9.99


def test_normalize_product_sets_original_name():
    p = {"name": "Ücool Product"}
    result = normalize_product(p)
    assert result["_original_name"] == "Ücool Product"


def test_normalize_product_no_name_field():
    p = {"price": 5.0}
    result = normalize_product(p)
    assert "name" not in result
