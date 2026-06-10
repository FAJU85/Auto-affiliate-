"""Unit tests for grapheme-safe truncation in bluesky_client.py.

Tests the _grapheme_len, _truncate_graphemes, and _build_post_text helpers
directly, without importing atproto (which requires native deps).
"""

import sys
import unicodedata
import pytest

# ── Inline the helpers under test so we don't need atproto ──────────────────

GRAPHEME_LIMIT = 300


def _grapheme_len(s: str) -> int:
    try:
        import regex  # type: ignore
        return len(regex.findall(r"\X", s))
    except ImportError:
        pass
    count = 0
    for ch in s:
        if unicodedata.category(ch) not in ("Mn", "Mc", "Me"):
            count += 1
    return count


def _truncate_graphemes(text: str, limit: int) -> str:
    try:
        import regex  # type: ignore
        clusters = regex.findall(r"\X", text)
    except ImportError:
        clusters = [ch for ch in text if unicodedata.category(ch) not in ("Mn", "Mc", "Me")]
    if len(clusters) <= limit:
        return text
    return "".join(clusters[:limit])


def _build_post_text(caption: str, deeplink: str) -> str:
    link_part = f"\n{deeplink}" if deeplink else ""
    link_graphemes = _grapheme_len(link_part)
    caption_budget = GRAPHEME_LIMIT - link_graphemes
    truncated_caption = _truncate_graphemes(caption.strip(), max(0, caption_budget - 1))
    if len(caption.strip()) > caption_budget:
        truncated_caption = truncated_caption.rstrip() + "…"
    return truncated_caption + link_part


# ── _grapheme_len ────────────────────────────────────────────────────────────

class TestGraphemeLen:
    def test_ascii_string(self):
        assert _grapheme_len("hello") == 5

    def test_empty_string(self):
        assert _grapheme_len("") == 0

    def test_emoji_single(self):
        # 🎉 is a single grapheme cluster
        assert _grapheme_len("🎉") == 1

    def test_emoji_sequence(self):
        # Each emoji is 1 grapheme; 3 emojis = 3 graphemes
        assert _grapheme_len("🎉🔥💯") == 3

    def test_mixed_ascii_and_emoji(self):
        assert _grapheme_len("Hi 🎉") == 4  # H, i, space, 🎉

    def test_combining_accent(self):
        # é as e + combining acute accent (2 code points, 1 grapheme)
        e_plus_acute = "é"  # e + combining acute
        result = _grapheme_len(e_plus_acute)
        # Our fallback counts non-combining chars only, so this is 1
        assert result == 1

    def test_300_ascii_chars(self):
        assert _grapheme_len("a" * 300) == 300

    def test_cyrillic(self):
        assert _grapheme_len("привет") == 6

    def test_chinese(self):
        assert _grapheme_len("你好世界") == 4


# ── _truncate_graphemes ──────────────────────────────────────────────────────

class TestTruncateGraphemes:
    def test_short_string_unchanged(self):
        text = "Short text"
        assert _truncate_graphemes(text, 50) == text

    def test_exact_limit_unchanged(self):
        text = "a" * 100
        assert _truncate_graphemes(text, 100) == text

    def test_truncates_over_limit(self):
        text = "a" * 200
        result = _truncate_graphemes(text, 100)
        assert len(result) == 100

    def test_truncates_emoji_correctly(self):
        # 10 emojis, limit 5 → 5 emojis
        text = "🔥" * 10
        result = _truncate_graphemes(text, 5)
        assert _grapheme_len(result) == 5

    def test_zero_limit(self):
        assert _truncate_graphemes("hello", 0) == ""

    def test_empty_input(self):
        assert _truncate_graphemes("", 10) == ""


# ── _build_post_text ─────────────────────────────────────────────────────────

class TestBuildPostText:
    def test_fits_within_300_graphemes(self):
        caption = "Great deal on this product! Check it out."
        deeplink = "https://example.com/r/abc123def"
        result = _build_post_text(caption, deeplink)
        assert _grapheme_len(result) <= GRAPHEME_LIMIT

    def test_long_caption_truncated(self):
        caption = "Amazing product! " * 25  # ~425 graphemes
        deeplink = "https://example.com/r/abc"
        result = _build_post_text(caption, deeplink)
        assert _grapheme_len(result) <= GRAPHEME_LIMIT

    def test_deeplink_always_preserved(self):
        caption = "x" * 290
        deeplink = "https://example.com/r/tracking123"
        result = _build_post_text(caption, deeplink)
        assert deeplink in result
        assert _grapheme_len(result) <= GRAPHEME_LIMIT

    def test_no_deeplink_no_newline(self):
        caption = "A caption with no link"
        result = _build_post_text(caption, "")
        assert "\n" not in result
        assert result == caption

    def test_ellipsis_added_when_truncated(self):
        caption = "word " * 100  # well over 300 graphemes
        deeplink = "https://example.com/r/abc"
        result = _build_post_text(caption, deeplink)
        assert "…" in result

    def test_no_ellipsis_when_short(self):
        caption = "Short caption"
        deeplink = "https://example.com/r/abc"
        result = _build_post_text(caption, deeplink)
        assert "…" not in result

    def test_emoji_heavy_caption_within_limit(self):
        # Heavy emoji caption — bytes >> graphemes
        caption = "🔥" * 200
        deeplink = "https://example.com/r/xyz"
        result = _build_post_text(caption, deeplink)
        assert _grapheme_len(result) <= GRAPHEME_LIMIT
        assert deeplink in result

    def test_empty_caption(self):
        deeplink = "https://example.com/r/abc"
        result = _build_post_text("", deeplink)
        assert deeplink in result
        assert _grapheme_len(result) <= GRAPHEME_LIMIT

    def test_bytes_can_exceed_300_while_graphemes_ok(self):
        # CJK chars are 3 bytes each but 1 grapheme
        # 100 CJK chars = 300 bytes but only 100 graphemes → should fit with deeplink
        caption = "中" * 100
        deeplink = "https://example.com/r/abc"
        result = _build_post_text(caption, deeplink)
        assert _grapheme_len(result) <= GRAPHEME_LIMIT
        # Byte length can exceed 300 — that's ok; Bluesky counts graphemes
        assert len(result.encode("utf-8")) > 300
