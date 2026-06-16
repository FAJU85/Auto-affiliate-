from api.utils.affiliate_link_builder import (
    add_utm, detect_network, validate_admitad, build_admitad,
    build_utm_url, strip_utm, is_affiliate_url, link_summary,
)


def test_add_utm_no_existing_params():
    url = add_utm("https://example.com/product", source="twitter")
    assert "utm_source=twitter" in url
    assert "utm_medium=social" in url
    assert "utm_campaign=affiliate" in url


def test_add_utm_with_existing_params():
    url = add_utm("https://example.com/product?id=1", source="twitter")
    assert url.startswith("https://example.com/product?id=1&")
    assert "utm_source=twitter" in url


def test_add_utm_custom_campaign():
    url = add_utm("https://example.com", source="bluesky", campaign="summer_sale")
    assert "utm_campaign=summer_sale" in url


def test_detect_network_admitad():
    url = "https://rzekl.com/g/1e8d114494b4b6a5bf/?aff_short_key=abc"
    assert detect_network(url) == "admitad"


def test_detect_network_sovrn():
    url = "https://redirect.viglink.com/?key=abc&u=https://shop.com"
    assert detect_network(url) == "sovrn"


def test_detect_network_unknown():
    assert detect_network("https://example.com/product") is None


def test_validate_admitad_valid():
    url = "https://rzekl.com/g/1e8d114494b4b6a5bf/?aff_short_key=abc123"
    result = validate_admitad(url)
    assert result["valid"] is True
    assert result["issues"] == []


def test_validate_admitad_missing_wrapper():
    result = validate_admitad("https://example.com/?aff_short_key=abc")
    assert result["valid"] is False
    assert any("rzekl.com" in i for i in result["issues"])


def test_validate_admitad_missing_key():
    result = validate_admitad("https://rzekl.com/g/1e8d114494b4b6a5bf/")
    assert result["valid"] is False
    assert any("aff_short_key" in i for i in result["issues"])


def test_build_admitad_contains_wrapper():
    url = build_admitad("https://shop.com/item", aff_short_key="testkey")
    assert "rzekl.com" in url
    assert "aff_short_key=testkey" in url


def test_build_utm_url():
    url = build_utm_url("https://example.com", platform="instagram")
    assert "utm_source=instagram" in url


def test_strip_utm_removes_params():
    url = "https://example.com/product?id=1&utm_source=twitter&utm_medium=social"
    cleaned = strip_utm(url)
    assert "utm_source" not in cleaned
    assert "id=1" in cleaned


def test_strip_utm_clean_url_unchanged():
    url = "https://example.com/product?id=1"
    assert strip_utm(url) == url


def test_is_affiliate_url_true():
    assert is_affiliate_url("https://rzekl.com/g/abc/?aff_short_key=x") is True


def test_is_affiliate_url_false():
    assert is_affiliate_url("https://example.com/product") is False


def test_link_summary_structure():
    url = "https://rzekl.com/g/abc/?aff_short_key=x&utm_source=twitter"
    s = link_summary(url)
    for key in ("url", "network", "domain", "has_utm", "utm_params", "is_affiliate"):
        assert key in s


def test_link_summary_identifies_network():
    url = "https://rzekl.com/g/abc/?aff_short_key=x"
    s = link_summary(url)
    assert s["network"] == "admitad"
    assert s["is_affiliate"] is True
