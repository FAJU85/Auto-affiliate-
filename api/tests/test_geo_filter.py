from api.utils.geo_filter import is_allowed, expand_regions, filter_products, geo_summary


def test_is_allowed_no_rules():
    assert is_allowed("DE") is True


def test_is_allowed_allowlist():
    assert is_allowed("US", allow=["US", "CA"]) is True
    assert is_allowed("DE", allow=["US", "CA"]) is False


def test_is_allowed_blocklist():
    assert is_allowed("US", block=["US"]) is False
    assert is_allowed("DE", block=["US"]) is True


def test_block_takes_precedence():
    assert is_allowed("US", allow=["US"], block=["US"]) is False


def test_case_insensitive():
    assert is_allowed("de", allow=["DE"]) is True


def test_expand_region_eu():
    codes = expand_regions(["eu"])
    assert "DE" in codes
    assert "FR" in codes
    assert len(codes) > 10


def test_expand_region_mixed():
    codes = expand_regions(["US", "nordics"])
    assert "US" in codes
    assert "SE" in codes


def test_expand_deduplicates():
    codes = expand_regions(["eu", "DE"])
    assert codes.count("DE") == 1


def test_is_allowed_region_block():
    assert is_allowed("DE", block=["eu"]) is False
    assert is_allowed("US", block=["eu"]) is True


def test_filter_products_no_rules():
    products = [{"name": "A", "country": "US"}, {"name": "B", "country": "DE"}]
    assert len(filter_products(products)) == 2


def test_filter_products_allowlist():
    products = [{"name": "A", "country": "US"}, {"name": "B", "country": "DE"}]
    result = filter_products(products, allow=["US"])
    assert len(result) == 1
    assert result[0]["name"] == "A"


def test_filter_products_no_country_passes():
    products = [{"name": "A"}]
    result = filter_products(products, allow=["US"])
    assert len(result) == 1


def test_geo_summary_structure():
    s = geo_summary(["US", "DE", "US", "FR"])
    assert "unique_countries" in s
    assert "top_countries" in s
    assert "counts" in s


def test_geo_summary_counts():
    s = geo_summary(["US", "US", "DE"])
    assert s["unique_countries"] == 2
    assert s["counts"]["US"] == 2


def test_geo_summary_top_sorted():
    s = geo_summary(["US", "US", "US", "DE", "DE", "FR"])
    assert s["top_countries"][0]["country"] == "US"
