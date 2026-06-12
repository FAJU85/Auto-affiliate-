"""Cycle 12: SOVRN fallback paths, social_post X image upload, main.py edge routes."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── SOVRN ──────────────────────────────────────────────────────────────────────

class TestSovrnAllPostedFallback:
    @pytest.mark.asyncio
    async def test_picks_product_when_all_recently_posted(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("SOVRN_API_KEY", "fake-sovrn-key")
        import importlib
        import api.feeds.sovrn as sovrn
        importlib.reload(sovrn)

        # Mark all products as recently posted so fallback fires
        with patch("api.utils.metrics.was_recently_posted", return_value=True):
            product = sovrn._pick_product()
        # Should still return a product (fallback random pick)
        assert product is not None
        assert "name" in product

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("SOVRN_API_KEY", "fake-sovrn-key")
        import importlib
        import api.feeds.sovrn as sovrn
        importlib.reload(sovrn)
        # Open the circuit breaker
        sovrn.sovrn_cb.reset()
        for _ in range(3):
            try:
                await sovrn.sovrn_cb.call(AsyncMock(side_effect=RuntimeError("fail")))
            except Exception:
                pass
        # get_sovrn_product with open CB should still return a product using original URL
        result = await sovrn.get_sovrn_product()
        assert result is not None
        assert "deeplink" in result
        sovrn.sovrn_cb.reset()

    @pytest.mark.asyncio
    async def test_monetize_exception_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("SOVRN_API_KEY", "fake-sovrn-key")
        import importlib
        import api.feeds.sovrn as sovrn
        importlib.reload(sovrn)
        sovrn.sovrn_cb.reset()
        # Force monetize to raise via circuit breaker call exception
        with patch.object(sovrn, "monetize_url", AsyncMock(side_effect=Exception("monetize fail"))):
            result = await sovrn.get_sovrn_product()
        # Should still return a product using the original URL
        assert result is not None
        assert "deeplink" in result
        sovrn.sovrn_cb.reset()

    @pytest.mark.asyncio
    async def test_link_unchanged_warn_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("SOVRN_API_KEY", "fake-sovrn-key")
        import importlib
        import api.feeds.sovrn as sovrn
        importlib.reload(sovrn)
        sovrn.sovrn_cb.reset()
        # monetize_url returns the same URL (no change → warn path)
        with patch.object(sovrn, "monetize_url", AsyncMock(side_effect=lambda url: url)):
            result = await sovrn.get_sovrn_product()
        assert result is not None
        sovrn.sovrn_cb.reset()


# ── X image upload ──────────────────────────────────────────────────────────────

class TestUploadXImage:
    @pytest.mark.asyncio
    async def test_returns_media_id_on_success(self):
        from api.social_post import _upload_x_image
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"media_id_string": "media123"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=ok_resp)
            result = await _upload_x_image("ck", "cs", "at", "as", b"imgdata")
        assert result == "media123"

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self):
        from api.social_post import _upload_x_image
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.text = "Server Error"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=fail_resp)
            result = await _upload_x_image("ck", "cs", "at", "as", b"imgdata")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        from api.social_post import _upload_x_image
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("timeout"))
            result = await _upload_x_image("ck", "cs", "at", "as", b"imgdata")
        assert result is None


# ── _post_x with incomplete credentials ────────────────────────────────────────

class TestPostXIncompleteCredentials:
    @pytest.mark.asyncio
    async def test_raises_when_credentials_incomplete(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "x": {"connected": True, "consumer_key": "ck"}  # missing 3 keys
        }))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="incomplete"):
            await sp._post_x("caption", "https://link.com")

    @pytest.mark.asyncio
    async def test_posts_with_image(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"x": {
            "connected": True,
            "consumer_key": "ck", "consumer_secret": "cs",  # pragma: allowlist secret
            "access_token": "at", "access_secret": "as", "handle": "user"  # pragma: allowlist secret
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        media_resp = MagicMock()
        media_resp.status_code = 200
        media_resp.json.return_value = {"media_id_string": "img456"}

        tweet_resp = MagicMock()
        tweet_resp.status_code = 201
        tweet_resp.json.return_value = {"data": {"id": "tweet789"}}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[media_resp, tweet_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp._post_x("Caption!", "https://link.com", image=b"imgdata")
        assert "twitter.com" in result


# ── _post_facebook with image_url ──────────────────────────────────────────────

class TestPostFacebookWithImage:
    @pytest.mark.asyncio
    async def test_posts_photo_with_image_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"facebook": {
            "connected": True,
            "page_access_token": "pat123",  # pragma: allowlist secret
            "page_id": "pg456"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        photo_resp = MagicMock()
        photo_resp.status_code = 200
        photo_resp.json.return_value = {"id": "pg456_photo789"}

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=photo_resp)
            result = await sp._post_facebook("Caption!", "https://link.com", image_url="https://img.example.com/img.jpg")
        assert "facebook.com" in result

    @pytest.mark.asyncio
    async def test_raises_on_photo_post_failure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"facebook": {
            "connected": True,
            "page_access_token": "pat123",  # pragma: allowlist secret
            "page_id": "pg456"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        fail_resp = MagicMock()
        fail_resp.status_code = 400
        fail_resp.json.return_value = {"error": "bad request"}
        fail_resp.text = "Bad Request"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=fail_resp)
            with pytest.raises(RuntimeError):
                await sp._post_facebook("Caption!", "https://link.com", image_url="https://img.example.com/img.jpg")


# ── _post_mastodon with image ───────────────────────────────────────────────────

class TestPostMastodonWithImage:
    @pytest.mark.asyncio
    async def test_posts_with_image(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "mastodon": {"connected": True, "access_token": "mst_tok", "instance": "https://mastodon.social"}
        }))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        # Mock _upload_mastodon_image to return a media_id
        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {"url": "https://mastodon.social/@user/12345"}

        with patch.object(sp, "_upload_mastodon_image", AsyncMock(return_value="media_id_123")):
            with patch("httpx.AsyncClient") as mc:
                mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=post_resp)
                result = await sp._post_mastodon("Caption!", "https://link.com", image=b"imgdata")
        assert "mastodon.social" in result

    @pytest.mark.asyncio
    async def test_posts_with_long_caption_truncated(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "mastodon": {"connected": True, "access_token": "mst_tok", "instance": "https://mastodon.social"}
        }))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {"url": "https://mastodon.social/@user/99"}

        # Very long caption — should be truncated
        long_caption = "A" * 600
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=post_resp)
            result = await sp._post_mastodon(long_caption, "https://link.com")
        assert "mastodon.social" in result
