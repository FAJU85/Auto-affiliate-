"""Extended tests for social_post.py — Threads, Tumblr, image upload, dispatchers."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture()
def sp(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import api.social_post as mod
    importlib.reload(mod)
    return mod, tmp_path


def _write_conn(tmp_path, data: dict):
    (tmp_path / "social-connections.json").write_text(json.dumps(data))


# ── Mastodon image upload ────────────────────────────────────────────────────

class TestUploadMastodonImage:
    @pytest.mark.asyncio
    async def test_returns_media_id_on_200(self, sp):
        mod, _ = sp
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "media-123"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await mod._upload_mastodon_image(
                "https://mastodon.social", {"Authorization": "Bearer t"}, b"fakejpeg"
            )
        assert result == "media-123"

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self, sp):
        mod, _ = sp
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("network error")
            )
            result = await mod._upload_mastodon_image(
                "https://mastodon.social", {"Authorization": "Bearer t"}, b"fakejpeg"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_non_2xx(self, sp):
        mod, _ = sp
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await mod._upload_mastodon_image(
                "https://mastodon.social", {"Authorization": "Bearer t"}, b"fakejpeg"
            )
        assert result is None


# ── X image upload ───────────────────────────────────────────────────────────

class TestUploadXImage:
    @pytest.mark.asyncio
    async def test_returns_media_id_on_201(self, sp):
        mod, _ = sp
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"media_id_string": "xmedia456"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await mod._upload_x_image("ck", "cs", "at", "as", b"imgdata")
        assert result == "xmedia456"

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, sp):
        mod, _ = sp
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("timeout")
            )
            result = await mod._upload_x_image("ck", "cs", "at", "as", b"imgdata")
        assert result is None


# ── Threads posting ──────────────────────────────────────────────────────────

class TestPostThreads:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, sp):
        mod, _ = sp
        with pytest.raises(RuntimeError, match="not connected"):
            await mod._post_threads("caption", "https://link.com")

    @pytest.mark.asyncio
    async def test_posts_successfully_text_mode(self, sp):
        mod, tmp_path = sp
        _write_conn(tmp_path, {"threads": {
            "connected": True, "access_token": "t", "user_id": "u123", "handle": "myhandle"
        }})
        import importlib
        importlib.reload(mod)
        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "container-1"}
        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "post-abc"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=[container_resp, publish_resp]
            )
            result = await mod._post_threads("Great deal!", "https://link.com")
        assert "threads.net" in result or "threads" in result

    @pytest.mark.asyncio
    async def test_raises_on_container_error(self, sp):
        mod, tmp_path = sp
        _write_conn(tmp_path, {"threads": {
            "connected": True, "access_token": "t", "user_id": "u123"
        }})
        import importlib
        importlib.reload(mod)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(RuntimeError, match="container"):
                await mod._post_threads("caption", "https://link.com")


# ── Tumblr posting ───────────────────────────────────────────────────────────

class TestPostTumblr:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, sp):
        mod, _ = sp
        with pytest.raises(RuntimeError, match="not connected"):
            await mod._post_tumblr("caption", "https://link.com")

    @pytest.mark.asyncio
    async def test_raises_when_no_blog_name(self, sp):
        mod, tmp_path = sp
        _write_conn(tmp_path, {"tumblr": {
            "connected": True, "access_token": "t", "handle": ""
        }})
        import importlib
        importlib.reload(mod)
        with pytest.raises(RuntimeError, match="handle"):
            await mod._post_tumblr("caption", "https://link.com")

    @pytest.mark.asyncio
    async def test_posts_successfully(self, sp):
        mod, tmp_path = sp
        _write_conn(tmp_path, {"tumblr": {
            "connected": True, "access_token": "t", "handle": "myblog"
        }})
        import importlib
        importlib.reload(mod)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"response": {"id": "12345"}}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await mod._post_tumblr("Great deal!", "https://link.com")
        assert "tumblr.com" in result

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, sp):
        mod, tmp_path = sp
        _write_conn(tmp_path, {"tumblr": {
            "connected": True, "access_token": "t", "handle": "myblog"
        }})
        import importlib
        importlib.reload(mod)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(RuntimeError, match="401"):
                await mod._post_tumblr("caption", "https://link.com")


# ── Circuit-breaker dispatchers ──────────────────────────────────────────────

class TestCircuitBreakerDispatchers:
    @pytest.mark.asyncio
    async def test_post_to_mastodon_calls_mastodon(self, sp):
        mod, _ = sp
        with patch.object(mod, "_post_mastodon", AsyncMock(return_value="uri")) as mocked:
            await mod.post_to_mastodon("cap", "link")
        mocked.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_to_x_calls_x(self, sp):
        mod, _ = sp
        with patch.object(mod, "_post_x", AsyncMock(return_value="uri")) as mocked:
            await mod.post_to_x("cap", "link")
        mocked.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_to_facebook_calls_facebook(self, sp):
        mod, _ = sp
        with patch.object(mod, "_post_facebook", AsyncMock(return_value="uri")) as mocked:
            await mod.post_to_facebook("cap", "link")
        mocked.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_to_instagram_calls_instagram(self, sp):
        mod, _ = sp
        with patch.object(mod, "_post_instagram", AsyncMock(return_value="uri")) as mocked:
            await mod.post_to_instagram("cap", "link")
        mocked.assert_called_once()
