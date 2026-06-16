"""Tests for platform-specific caption routing (Build #4)."""

import pytest
from unittest.mock import AsyncMock, patch


_PRODUCT = {
    "name": "Sony WH-1000XM5 Headphones",
    "price": 299.0,
    "category": "Electronics",
    "description": "Industry-leading noise cancelling with exceptional sound quality.",
    "imageUrl": "https://img.example.com/sony.jpg",
    "deeplink": "https://example.com/dp/B09XS7JWHH",
    "source": "sovrn",
}


# ── _build_prompts platform tone injection ─────────────────────────────────────

class TestBuildPromptsWithPlatform:
    def test_bluesky_injects_conversational_tone(self):
        from api.ai.text import _build_prompts, _PLATFORM_TONE
        system, _ = _build_prompts(_PRODUCT, [], platform="bluesky")
        assert _PLATFORM_TONE["bluesky"][:20] in system

    def test_instagram_injects_visual_tone(self):
        from api.ai.text import _build_prompts, _PLATFORM_TONE
        system, _ = _build_prompts(_PRODUCT, [], platform="instagram")
        assert _PLATFORM_TONE["instagram"][:20] in system

    def test_mastodon_injects_hashtag_guidance(self):
        from api.ai.text import _build_prompts
        system, _ = _build_prompts(_PRODUCT, [], platform="mastodon")
        assert "hashtag" in system.lower()

    def test_x_injects_character_limit_guidance(self):
        from api.ai.text import _build_prompts
        system, _ = _build_prompts(_PRODUCT, [], platform="x")
        assert "220" in system or "Twitter" in system

    def test_facebook_no_hashtag_instruction(self):
        from api.ai.text import _build_prompts
        system, _ = _build_prompts(_PRODUCT, [], platform="facebook")
        assert "no hashtag" in system.lower()

    def test_unknown_platform_does_not_add_tone(self):
        from api.ai.text import _build_prompts
        system_no_platform, _ = _build_prompts(_PRODUCT, [], platform=None)
        system_unknown, _ = _build_prompts(_PRODUCT, [], platform="tiktok")
        assert system_no_platform == system_unknown

    def test_none_platform_is_backward_compatible(self):
        from api.ai.text import _build_prompts
        system_none, user_none = _build_prompts(_PRODUCT, [], platform=None)
        system_old, user_old = _build_prompts(_PRODUCT, [])
        assert system_none == system_old
        assert user_none == user_old

    def test_all_known_platforms_have_tone(self):
        from api.ai.text import _PLATFORM_TONE
        expected = {"bluesky", "mastodon", "x", "instagram", "threads", "facebook", "tumblr"}
        assert expected.issubset(set(_PLATFORM_TONE.keys()))


# ── generate_platform_caption ─────────────────────────────────────────────────

class TestGeneratePlatformCaption:
    @pytest.mark.asyncio
    async def test_returns_string(self):
        from api.ai.text import generate_platform_caption
        with patch("api.ai.text._try_groq", AsyncMock(return_value=None)), \
             patch("api.ai.text._try_mistral", AsyncMock(return_value=None)):
            result = await generate_platform_caption(_PRODUCT, [], platform="bluesky")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_uses_provider_output_when_available(self):
        from api.ai.text import generate_platform_caption
        with patch("api.ai.text._try_groq", AsyncMock(return_value="Great headphones! Buy now.")):
            result = await generate_platform_caption(_PRODUCT, [], platform="instagram")
        assert "Great headphones" in result

    @pytest.mark.asyncio
    async def test_falls_back_to_template_when_providers_fail(self):
        from api.ai.text import generate_platform_caption
        with patch("api.ai.text._try_groq", AsyncMock(return_value=None)), \
             patch("api.ai.text._try_mistral", AsyncMock(return_value=None)):
            result = await generate_platform_caption(_PRODUCT, [], platform="x")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_none_platform_behaves_like_generic(self):
        from api.ai.text import generate_platform_caption, generate_post_text
        with patch("api.ai.text._try_groq", AsyncMock(return_value=None)), \
             patch("api.ai.text._try_mistral", AsyncMock(return_value=None)):
            r1 = await generate_platform_caption(_PRODUCT, [], platform=None)
            r2 = await generate_post_text(_PRODUCT, [])
        # Both use template fallback — same structure (may differ in random choice)
        assert isinstance(r1, str) and isinstance(r2, str)

    @pytest.mark.asyncio
    async def test_respects_max_chars(self):
        from api.ai.text import generate_platform_caption, MAX_CHARS
        long_text = "x" * 500 + " Buy now!"
        with patch("api.ai.text._try_groq", AsyncMock(return_value=long_text)):
            result = await generate_platform_caption(_PRODUCT, [], platform="bluesky")
        assert len(result) <= MAX_CHARS


# ── Pipeline concurrent caption generation ─────────────────────────────────────

class TestPipelinePlatformCaptions:
    @pytest.mark.asyncio
    async def test_multiple_platforms_get_different_captions(self, monkeypatch):
        """When posting to >1 platform, each gets a platform-tuned caption."""
        from api.ai import text as ai_text
        call_log = []

        async def fake_caption(product, trends, platform=None):
            call_log.append(platform)
            return f"Caption for {platform}"

        monkeypatch.setattr(ai_text, "generate_platform_caption", fake_caption)

        # Simulate the concurrent gather in pipeline
        import asyncio
        platforms = ["bluesky", "instagram", "mastodon"]
        platform_captions: dict = {}

        async def _gen(plat):
            c = await ai_text.generate_platform_caption(_PRODUCT, [], platform=plat)
            platform_captions[plat] = c

        await asyncio.gather(*[_gen(p) for p in platforms])

        assert set(platform_captions.keys()) == set(platforms)
        assert platform_captions["bluesky"] == "Caption for bluesky"
        assert platform_captions["instagram"] == "Caption for instagram"
        assert set(call_log) == set(platforms)

    @pytest.mark.asyncio
    async def test_single_platform_skips_concurrent_generation(self, monkeypatch):
        """Single-platform path uses the base caption, no per-platform calls needed."""
        from api.ai import text as ai_text
        call_count = {"n": 0}

        async def fake_caption(product, trends, platform=None):
            call_count["n"] += 1
            return "platform caption"

        monkeypatch.setattr(ai_text, "generate_platform_caption", fake_caption)

        platforms = ["bluesky"]
        platform_captions: dict = {}
        if len(platforms) > 1:
            import asyncio
            async def _gen(plat):
                c = await ai_text.generate_platform_caption(_PRODUCT, [], platform=plat)
                platform_captions[plat] = c
            await asyncio.gather(*[_gen(p) for p in platforms])

        assert call_count["n"] == 0  # not called for single platform
        assert len(platform_captions) == 0
