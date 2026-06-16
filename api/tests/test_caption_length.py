"""Tests for platform-aware caption length enforcement."""

from api.utils.caption_length import trim_caption, caption_fits, PLATFORM_LIMITS


def test_short_caption_unchanged():
    caption = "This is a short caption."
    assert trim_caption(caption, "x") == caption


def test_caption_at_exactly_limit_unchanged():
    limit = PLATFORM_LIMITS["x"]  # 280
    caption = "a" * limit
    assert trim_caption(caption, "x") == caption


def test_caption_one_char_over_limit_gets_trimmed():
    limit = PLATFORM_LIMITS["x"]  # 280
    caption = "word " * (limit // 5) + "x"
    result = trim_caption(caption, "x")
    assert len(result) <= limit


def test_trimmed_caption_ends_with_ellipsis():
    caption = "word " * 100  # much longer than limit
    result = trim_caption(caption, "x")
    assert result.endswith("…")


def test_trimmed_caption_length_within_limit():
    limit = PLATFORM_LIMITS["mastodon"]  # 500
    caption = "hello world " * 100
    result = trim_caption(caption, "mastodon")
    assert len(result) <= limit


def test_unknown_platform_uses_default():
    default_limit = PLATFORM_LIMITS["default"]  # 280
    caption = "word " * 100
    result = trim_caption(caption, "unknown_platform")
    assert len(result) <= default_limit


def test_caption_fits_returns_true_within_limit():
    assert caption_fits("short caption", "x") is True


def test_caption_fits_returns_false_over_limit():
    limit = PLATFORM_LIMITS["x"]  # 280
    caption = "a" * (limit + 1)
    assert caption_fits(caption, "x") is False


def test_bluesky_uses_correct_limit():
    limit = PLATFORM_LIMITS["bluesky"]  # 300
    assert limit == 300
    caption = "a" * 300
    assert caption_fits(caption, "bluesky") is True
    assert not caption_fits("a" * 301, "bluesky")


def test_x_uses_correct_limit():
    assert PLATFORM_LIMITS["x"] == 280
    assert caption_fits("a" * 280, "x") is True
    assert not caption_fits("a" * 281, "x")


def test_mastodon_uses_correct_limit():
    assert PLATFORM_LIMITS["mastodon"] == 500
    assert caption_fits("a" * 500, "mastodon") is True
    assert not caption_fits("a" * 501, "mastodon")


def test_empty_string_returns_empty_string():
    assert trim_caption("", "x") == ""
    assert trim_caption("", "bluesky") == ""


def test_single_long_word_no_spaces_truncates():
    limit = PLATFORM_LIMITS["x"]  # 280
    caption = "a" * (limit + 50)  # no spaces
    result = trim_caption(caption, "x")
    assert len(result) <= limit
    assert result.endswith("…")


def test_caption_fits_at_exact_limit():
    limit = PLATFORM_LIMITS["instagram"]  # 2200
    caption = "a" * limit
    assert caption_fits(caption, "instagram") is True
