from api.utils.text_truncator import truncate, truncate_for_platform, fits, split_for_thread, char_count, platform_limit


def test_truncate_short_text_unchanged():
    assert truncate("hello", 100) == "hello"


def test_truncate_at_word_boundary():
    result = truncate("the quick brown fox", 12)
    assert result.endswith("…")
    assert len(result) <= 12


def test_truncate_no_space_found():
    result = truncate("abcdefghij", 5)
    assert len(result) <= 5


def test_truncate_custom_suffix():
    result = truncate("hello world test", 10, suffix="...")
    assert result.endswith("...")
    assert len(result) <= 10


def test_truncate_for_platform_x():
    long_text = "a" * 300
    result = truncate_for_platform(long_text, "x")
    assert len(result) <= 280


def test_truncate_for_platform_bluesky():
    long_text = "word " * 100
    result = truncate_for_platform(long_text, "bluesky")
    assert len(result) <= 300


def test_truncate_for_unknown_platform():
    text = "hello"
    assert truncate_for_platform(text, "unknown") == text


def test_fits_short_text():
    assert fits("hello", "x") is True


def test_fits_long_text():
    assert fits("a" * 300, "x") is False


def test_fits_unknown_platform():
    assert fits("a" * 99999, "unknown") is True


def test_platform_limit_x():
    assert platform_limit("x") == 280


def test_platform_limit_bluesky():
    assert platform_limit("bluesky") == 300


def test_platform_limit_unknown():
    assert platform_limit("myspace") is None


def test_split_short_text():
    parts = split_for_thread("short", "x")
    assert parts == ["short"]


def test_split_long_text():
    text = "word " * 100
    parts = split_for_thread(text, "x")
    assert len(parts) > 1
    assert all(len(p) <= 280 for p in parts)


def test_char_count_structure():
    r = char_count("hello world", "x")
    for key in ("used", "limit", "remaining", "fits"):
        assert key in r


def test_char_count_fits():
    r = char_count("hi", "x")
    assert r["fits"] is True
    assert r["remaining"] == 278


def test_char_count_unknown_platform():
    r = char_count("hi", "unknown")
    assert r["limit"] is None
    assert r["fits"] is True
