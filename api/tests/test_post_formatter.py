import pytest
from api.utils.post_formatter import format_post, format_batch, fits_platform, format_stats

_PRODUCT = {
    "title": "Premium Leather Wallet",
    "price": 19.99,
    "original_price": 39.99,
    "description": "Slim design, genuine leather, RFID blocking.",
    "url": "https://rzekl.com/g/abc/?aff_short_key=test",
    "currency": "USD",
}


def test_format_post_contains_title():
    text = format_post(_PRODUCT, platform="twitter")
    assert "Premium Leather Wallet" in text


def test_format_post_contains_url():
    text = format_post(_PRODUCT, platform="twitter")
    assert "rzekl.com" in text


def test_format_post_contains_price():
    text = format_post(_PRODUCT, platform="twitter")
    assert "19.99" in text


def test_format_post_shows_discount():
    text = format_post(_PRODUCT, platform="twitter")
    assert "50%" in text or "off" in text


def test_format_post_twitter_limit():
    text = format_post(_PRODUCT, platform="twitter", template="compact")
    assert len(text) <= 280


def test_format_post_compact_template():
    text = format_post(_PRODUCT, platform="twitter", template="compact")
    assert "Premium Leather Wallet" in text


def test_format_post_minimal_template():
    text = format_post(_PRODUCT, platform="bluesky", template="minimal")
    assert "Premium Leather Wallet" in text
    assert "rzekl.com" in text


def test_format_post_invalid_template():
    with pytest.raises(ValueError):
        format_post(_PRODUCT, template="nonexistent")


def test_format_post_with_hashtags():
    text = format_post(_PRODUCT, platform="instagram", hashtags=["deals", "leather"])
    assert "#deals" in text
    assert "#leather" in text


def test_format_post_custom_emoji():
    text = format_post(_PRODUCT, platform="twitter", template="standard", emoji="🎁")
    assert "🎁" in text


def test_format_post_no_price():
    product = {"title": "Widget", "url": "https://example.com"}
    text = format_post(product, platform="twitter", template="minimal")
    assert "Widget" in text


def test_format_batch_empty():
    assert format_batch([]) == []


def test_format_batch_length():
    results = format_batch([_PRODUCT, _PRODUCT], platform="twitter", template="compact")
    assert len(results) == 2
    assert all(isinstance(t, str) for t in results)


def test_fits_platform_true():
    assert fits_platform("short text", "twitter") is True


def test_fits_platform_false():
    long_text = "x" * 300
    assert fits_platform(long_text, "twitter") is False


def test_format_stats_structure():
    s = format_stats("Hello world\nLine 2")
    for key in ("length", "lines", "fits"):
        assert key in s


def test_format_stats_fits_all_short():
    s = format_stats("Hi")
    assert all(s["fits"].values())
