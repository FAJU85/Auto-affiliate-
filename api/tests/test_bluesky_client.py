"""Unit tests for Bluesky client — pure logic + mocked HTTP."""

import json
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestRateLimitGuard:
    def test_returns_zero_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        assert bc._ratelimit_until() == 0.0

    def test_returns_future_epoch_when_active(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        future = time.time() + 3600
        bc._save_ratelimit(future)
        result = bc._ratelimit_until()
        assert result > time.time()

    def test_returns_zero_for_expired_ratelimit(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        past = time.time() - 10
        bc._save_ratelimit(past)
        assert bc._ratelimit_until() == 0.0

    def test_clear_ratelimit_removes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc._save_ratelimit(time.time() + 3600)
        bc._clear_ratelimit()
        assert bc._ratelimit_until() == 0.0


class TestSessionManagement:
    def test_no_cached_session_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        assert bc._load_cached_session() is None

    def test_save_and_load_session(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc._save_session("jwt-token-123", "did:plc:abc123")
        result = bc._load_cached_session()
        assert result is not None
        assert result["accessJwt"] == "jwt-token-123"
        assert result["did"] == "did:plc:abc123"

    def test_clear_session_removes_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc._save_session("jwt", "did")
        bc._clear_session()
        assert bc._load_cached_session() is None

    def test_expired_session_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        # Write a session with past expiry
        bc.SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        bc.SESSION_FILE.write_text(json.dumps({
            "accessJwt": "old-jwt", "did": "did:plc:old", "expiry": time.time() - 1
        }))
        bc._session.clear()
        assert bc._load_cached_session() is None


class TestGraphemeHelpers:
    def test_grapheme_len_ascii(self):
        from api.bluesky_client import _grapheme_len
        assert _grapheme_len("hello") == 5

    def test_grapheme_len_emoji(self):
        from api.bluesky_client import _grapheme_len
        # Emoji = 1 grapheme
        count = _grapheme_len("hi 🎉")
        assert count == 4

    def test_truncate_within_limit(self):
        from api.bluesky_client import _truncate_graphemes
        assert _truncate_graphemes("hello", 10) == "hello"

    def test_truncate_at_limit(self):
        from api.bluesky_client import _truncate_graphemes
        result = _truncate_graphemes("hello world", 5)
        assert len(result) == 5

    def test_build_post_text_fits_in_limit(self):
        from api.bluesky_client import _build_post_text, GRAPHEME_LIMIT
        from api.bluesky_client import _grapheme_len
        text = _build_post_text("Short caption", "https://example.com/product")
        assert _grapheme_len(text) <= GRAPHEME_LIMIT

    def test_build_post_text_truncates_long_caption(self):
        from api.bluesky_client import _build_post_text, _grapheme_len, GRAPHEME_LIMIT
        long_caption = "A" * 400
        text = _build_post_text(long_caption, "https://example.com/p")
        assert _grapheme_len(text) <= GRAPHEME_LIMIT

    def test_build_post_text_preserves_link(self):
        from api.bluesky_client import _build_post_text
        link = "https://example.com/product-link"
        text = _build_post_text("Caption text", link)
        assert link in text


class TestLinkFacets:
    def test_returns_empty_when_no_deeplink(self):
        from api.bluesky_client import _link_facets
        assert _link_facets("some text", "") == []

    def test_returns_facet_when_link_in_text(self):
        from api.bluesky_client import _link_facets
        link = "https://example.com/p"
        text = f"Great deal\n{link}"
        facets = _link_facets(text, link)
        assert len(facets) == 1
        assert facets[0]["features"][0]["uri"] == link

    def test_returns_empty_when_link_not_in_text(self):
        from api.bluesky_client import _link_facets
        facets = _link_facets("No link here at all", "https://example.com")
        assert facets == []

    def test_facet_byte_offsets_correct(self):
        from api.bluesky_client import _link_facets
        link = "https://test.com"
        text = f"Buy now\n{link}"
        facets = _link_facets(text, link)
        raw = text.encode("utf-8")
        start = facets[0]["index"]["byteStart"]
        end = facets[0]["index"]["byteEnd"]
        assert raw[start:end].decode() == link


class TestBuildPostWithCtaLink:
    def test_appends_url_when_no_cta_phrases(self, monkeypatch):
        from api.bluesky_client import _build_post_with_cta_link
        monkeypatch.setattr("api.utils.settings.get_settings",
                            lambda: {"ctaPhrases": []})
        text, facets = _build_post_with_cta_link("Great deal!", "https://example.com/p")
        assert "https://example.com/p" in text

    def test_creates_cta_facet_when_phrase_in_caption(self, monkeypatch):
        from api.bluesky_client import _build_post_with_cta_link
        monkeypatch.setattr("api.utils.settings.get_settings",
                            lambda: {"ctaPhrases": ["Get it now"]})
        caption = "Amazing product. Get it now"
        text, facets = _build_post_with_cta_link(caption, "https://example.com/p")
        # CTA phrase found — facet should point to the link
        assert len(facets) == 1
        assert facets[0]["features"][0]["uri"] == "https://example.com/p"


class TestGetSession:
    @pytest.mark.asyncio
    async def test_raises_when_ratelimited(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc._save_ratelimit(time.time() + 3600)
        with pytest.raises(RuntimeError, match="rate limit active"):
            await bc._get_session("handle.bsky.social", "password")

    @pytest.mark.asyncio
    async def test_raises_on_login_failure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(RuntimeError, match="login failed"):
                await bc._get_session("bad.bsky.social", "wrong-password")

    @pytest.mark.asyncio
    async def test_raises_on_429(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "300"}
        mock_resp.text = "Too Many Requests"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(RuntimeError, match="rate-limited"):
                await bc._get_session("handle.bsky.social", "password")

    @pytest.mark.asyncio
    async def test_returns_jwt_and_did_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"accessJwt": "jwt-abc", "did": "did:plc:xyz"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            jwt, did = await bc._get_session("user.bsky.social", "apppassword")
        assert jwt == "jwt-abc"
        assert did == "did:plc:xyz"


class TestUploadImage:
    @pytest.mark.asyncio
    async def test_returns_none_for_empty_bytes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.bluesky_client import _upload_image
        result = await _upload_image("jwt", b"")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_oversized_image(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.bluesky_client import _upload_image
        big = b"x" * (1_000_001)
        result = await _upload_image("jwt", big)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_blob_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.bluesky_client import _upload_image
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"blob": {"$type": "blob", "ref": {"$link": "abc"}, "mimeType": "image/jpeg", "size": 1024}}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _upload_image("jwt-token", b"fakejpeg" * 100)
        assert result is not None
        assert "$type" in result
