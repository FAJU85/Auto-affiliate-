from api.utils.image_caption import generate_alt_text, generate_caption, caption_variants, list_templates


def test_alt_text_title_only():
    assert "Wireless Headphones" in generate_alt_text("Wireless Headphones")


def test_alt_text_with_brand():
    result = generate_alt_text("Headphones", brand="Sony")
    assert "Sony" in result
    assert "Headphones" in result


def test_alt_text_with_price():
    result = generate_alt_text("Headphones", price="$49.99")
    assert "$49.99" in result


def test_alt_text_with_category():
    result = generate_alt_text("Headphones", category="electronics")
    assert "electronics" in result


def test_generate_caption_standard():
    result = generate_caption("Wireless Headphones")
    assert "Wireless Headphones" in result


def test_generate_caption_price_template():
    result = generate_caption("Hat", template="price", price="$20")
    assert "Hat" in result
    assert "$20" in result


def test_generate_caption_brand_template():
    result = generate_caption("Shoes", template="brand", brand="Nike")
    assert "Nike" in result
    assert "Shoes" in result


def test_generate_caption_truncated():
    long_title = "A" * 200
    result = generate_caption(long_title, max_length=50)
    assert len(result) <= 50
    assert result.endswith("…")


def test_generate_caption_deal_template():
    result = generate_caption("Jacket", template="deal", price="$30")
    assert "Jacket" in result
    assert "$30" in result


def test_generate_caption_unknown_template_fallback():
    result = generate_caption("Hat", template="nonexistent")
    assert "Hat" in result


def test_caption_variants_returns_all_templates():
    variants = caption_variants("Sneakers", brand="Nike", category="fashion", price="$80")
    for name in list_templates():
        assert name in variants


def test_caption_variants_all_strings():
    variants = caption_variants("Product")
    assert all(isinstance(v, str) for v in variants.values())


def test_list_templates_sorted():
    t = list_templates()
    assert t == sorted(t)


def test_list_templates_includes_standard():
    assert "standard" in list_templates()


def test_generate_caption_title_case():
    result = generate_caption("wireless headphones", template="standard")
    assert result[0].isupper()
