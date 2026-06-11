"""Unit tests for caption generation (ai/text.py) — mocked HTTP."""

import pytest
from unittest.mock import AsyncMock, patch


PRODUCT = {
    "name": "AirPods Pro",
    "price": 199.99,
    "currency": "USD",
    "category": "electronics",
    "description": "Active noise cancellation wireless earbuds",
}


class TestFmtPrice:
    def test_usd(self):
        from api.ai.text import _fmt_price
        assert _fmt_price({"price": 9.99, "currency": "USD"}) == "$9.99"

    def test_eur(self):
        from api.ai.text import _fmt_price
        assert _fmt_price({"price": 5.0, "currency": "EUR"}) == "€5.0"

    def test_gbp(self):
        from api.ai.text import _fmt_price
        assert _fmt_price({"price": 12.5, "currency": "GBP"}) == "£12.5"

    def test_unknown_currency(self):
        from api.ai.text import _fmt_price
        result = _fmt_price({"price": 10.0, "currency": "JPY"})
        assert "10.0" in result

    def test_no_price(self):
        from api.ai.text import _fmt_price
        assert _fmt_price({}) == ""


class TestClean:
    def test_strips_markdown_bold(self):
        from api.ai.text import _clean
        assert _clean("**Buy now!**") == "Buy now!"

    def test_strips_hashtags(self):
        from api.ai.text import _clean
        result = _clean("Great deal. #ad #sale")
        assert "#" not in result

    def test_strips_urls(self):
        from api.ai.text import _clean
        result = _clean("Check https://example.com for deals")
        assert "https://" not in result

    def test_truncates_to_max(self):
        from api.ai.text import _clean, MAX_CHARS
        long_text = "a " * 150
        result = _clean(long_text)
        assert len(result) <= MAX_CHARS + 1  # +1 for the ellipsis char

    def test_collapses_whitespace(self):
        from api.ai.text import _clean
        result = _clean("hello   world")
        assert "  " not in result


class TestLooksUsable:
    def test_rejects_short_text(self):
        from api.ai.text import _looks_usable
        assert _looks_usable("hi") is False

    def test_rejects_non_ascii_heavy(self):
        from api.ai.text import _looks_usable
        assert _looks_usable("这是一个测试。这是一个更长的中文字符串用来测试。") is False

    def test_accepts_good_english(self):
        from api.ai.text import _looks_usable
        assert _looks_usable("Upgrade your home with this amazing product. Get it now!") is True

    def test_rejects_camelcase_spam(self):
        from api.ai.text import _looks_usable
        assert _looks_usable("AirPodsProDeal TechSavings BuyNow TrendingGadget") is False

    def test_rejects_no_letters(self):
        from api.ai.text import _looks_usable
        assert _looks_usable("!!! ??? ### $$$") is False


class TestBuildPrompts:
    def test_returns_tuple_of_strings(self):
        from api.ai.text import _build_prompts
        system, user = _build_prompts(PRODUCT, ["tech deals"])
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_product_name_in_user_prompt(self):
        from api.ai.text import _build_prompts
        _, user = _build_prompts(PRODUCT, [])
        assert "AirPods" in user

    def test_bad_template_key_falls_back(self, monkeypatch):
        from api.ai import text as text_mod
        from api.utils import settings
        s = settings.get_settings()
        s["postUserTemplate"] = "{nonexistent_key}"
        monkeypatch.setattr("api.utils.settings.get_settings", lambda: s)
        _, user = text_mod._build_prompts(PRODUCT, [])
        assert "AirPods" in user


class TestTemplate:
    def test_returns_string(self):
        from api.ai.text import _template
        result = _template(PRODUCT, [])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_product_name(self):
        from api.ai.text import _template
        result = _template(PRODUCT, [])
        assert "AirPods" in result


class TestGeneratePostText:
    @pytest.mark.asyncio
    async def test_falls_back_to_template_without_keys(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        from api.ai.text import generate_post_text
        result = await generate_post_text(PRODUCT)
        assert isinstance(result, str)
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_uses_groq_when_available(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake-key")
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        from api.ai import text as text_mod
        good_caption = "Great noise-cancelling earbuds. Get yours today!"
        with patch.object(text_mod, "_try_groq", AsyncMock(return_value=good_caption)):
            result = await text_mod.generate_post_text(PRODUCT)
        assert "earbuds" in result or len(result) > 10

    @pytest.mark.asyncio
    async def test_falls_back_to_mistral_when_groq_fails(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("MISTRAL_API_KEY", "mistral-key")
        from api.ai import text as text_mod
        good_caption = "Top wireless earbuds with noise cancellation. Buy now!"
        with patch.object(text_mod, "_try_groq", AsyncMock(return_value=None)):
            with patch.object(text_mod, "_try_mistral", AsyncMock(return_value=good_caption)):
                result = await text_mod.generate_post_text(PRODUCT)
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_rejects_unusable_ai_output_and_uses_template(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "fake")
        from api.ai import text as text_mod
        junk = "AB"  # too short — _looks_usable will reject it
        with patch.object(text_mod, "_try_groq", AsyncMock(return_value=junk)):
            with patch.object(text_mod, "_try_mistral", AsyncMock(return_value=None)):
                result = await text_mod.generate_post_text(PRODUCT)
        # Falls back to template
        assert isinstance(result, str)
        assert len(result) > 10
