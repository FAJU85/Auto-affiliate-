from api.utils.tag_cleaner import normalize, clean, format_tags, limit_for_platform, clean_for_platform, tag_stats


def test_normalize_strips_hash():
    assert normalize("#deals") == "deals"


def test_normalize_lowercase():
    assert normalize("DEALS") == "deals"


def test_normalize_strips_spaces():
    assert normalize("  sale  ") == "sale"


def test_normalize_removes_special_chars():
    assert normalize("hello-world!") == "helloworld"


def test_normalize_empty():
    assert normalize("") == ""


def test_clean_deduplicates():
    result = clean(["deals", "#deals", "DEALS"])
    assert result == ["deals"]


def test_clean_preserves_order():
    result = clean(["b", "a", "c"])
    assert result == ["b", "a", "c"]


def test_clean_filters_empty():
    result = clean(["", "#", "valid"])
    assert result == ["valid"]


def test_clean_returns_normalized():
    result = clean(["#Hello", "WORLD"])
    assert "hello" in result
    assert "world" in result


def test_format_tags_adds_hash():
    assert format_tags(["deals", "sale"]) == ["#deals", "#sale"]


def test_format_tags_custom_prefix():
    assert format_tags(["deals"], prefix="") == ["deals"]


def test_limit_for_platform_twitter():
    tags = [str(i) for i in range(20)]
    assert len(limit_for_platform(tags, "twitter")) == 5


def test_limit_for_platform_instagram():
    tags = [str(i) for i in range(50)]
    assert len(limit_for_platform(tags, "instagram")) == 30


def test_limit_for_platform_unknown():
    tags = [str(i) for i in range(100)]
    assert len(limit_for_platform(tags, "unknown_platform")) == 100


def test_clean_for_platform_combines():
    tags = ["#A", "#a", "#B", "#C", "#D", "#E", "#F"]
    result = clean_for_platform(tags, "twitter")
    assert len(result) <= 5
    assert "a" in result


def test_tag_stats_structure():
    s = tag_stats(["#a", "#A", "b"])
    for key in ("input_count", "cleaned_count", "duplicates_removed", "tags"):
        assert key in s


def test_tag_stats_counts():
    s = tag_stats(["#a", "#A", "b"])
    assert s["input_count"] == 3
    assert s["cleaned_count"] == 2
    assert s["duplicates_removed"] == 1


def test_tag_stats_empty():
    s = tag_stats([])
    assert s["input_count"] == 0
    assert s["cleaned_count"] == 0
