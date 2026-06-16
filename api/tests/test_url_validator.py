from api.utils.url_validator import (
    is_valid_url, parse_url, check_admitad_link,
    validate_batch, extract_urls, has_tracking_params, url_summary,
)


def test_valid_http():
    assert is_valid_url("http://example.com") is True


def test_valid_https():
    assert is_valid_url("https://example.com/path?q=1") is True


def test_invalid_no_scheme():
    assert is_valid_url("example.com") is False


def test_invalid_empty():
    assert is_valid_url("") is False


def test_invalid_none():
    assert is_valid_url(None) is False


def test_invalid_spaces():
    assert is_valid_url("https://exam ple.com") is False


def test_parse_url_host():
    r = parse_url("https://example.com/path?a=1")
    assert r["host"] == "example.com"


def test_parse_url_params():
    r = parse_url("https://example.com/?foo=bar")
    assert "foo" in r["params"]


def test_check_admitad_valid():
    url = "https://rzekl.com/g/abc/?aff_short_key=xyz"
    r = check_admitad_link(url)
    assert r["valid"] is True
    assert r["issues"] == []


def test_check_admitad_missing_wrapper():
    url = "https://example.com/?aff_short_key=xyz"
    r = check_admitad_link(url)
    assert "missing_rzekl_wrapper" in r["issues"]


def test_check_admitad_missing_key():
    url = "https://rzekl.com/g/abc/"
    r = check_admitad_link(url)
    assert "missing_aff_short_key" in r["issues"]


def test_validate_batch():
    urls = ["https://a.com", "not-a-url"]
    result = validate_batch(urls)
    assert result[0]["valid"] is True
    assert result[1]["valid"] is False


def test_extract_urls():
    text = "Check https://example.com and http://other.org/path?q=1 for deals"
    urls = extract_urls(text)
    assert "https://example.com" in urls
    assert "http://other.org/path?q=1" in urls


def test_extract_urls_empty():
    assert extract_urls("no urls here") == []


def test_has_tracking_params_true():
    assert has_tracking_params("https://example.com/?utm_source=social") is True


def test_has_tracking_params_false():
    assert has_tracking_params("https://example.com/product") is False


def test_url_summary():
    urls = ["https://a.com", "https://b.com/?ref=x", "bad"]
    s = url_summary(urls)
    assert s["total"] == 3
    assert s["valid"] == 2
    assert s["invalid"] == 1
    assert s["with_tracking"] == 1
