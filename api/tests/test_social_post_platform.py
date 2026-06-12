"""Tests for Instagram, Threads, Tumblr posting paths and circuit-breaker dispatchers."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
def reset_cbs(monkeypatch, tmp_path):
    """Reload social_post with a clean DATA_DIR and reset all circuit breakers."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import api.social_post as sp
    importlib.reload(sp)
    # Reset all CBs so prior test failures don't bleed
    for cb in (sp._mastodon_cb, sp._x_cb, sp._facebook_cb, sp._instagram_cb, sp._threads_cb, sp._tumblr_cb):
        cb.reset()
    yield


class TestPostInstagramFullFlow:
    @pytest.mark.asyncio
    async def test_posts_successfully(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "instagram": {"connected": True, "access_token": "igt", "ig_user_id": "12345"}  # pragma: allowlist secret
        }))
        importlib.reload(sp)

        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "container_abc"}
        container_resp.text = ""

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "media_xyz"}
        publish_resp.text = ""

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp._post_instagram("Caption", "https://link.com", image_url="https://img.example.com/img.jpg")
        assert "instagram.com" in result

    @pytest.mark.asyncio
    async def test_raises_on_container_failure(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "instagram": {"connected": True, "access_token": "igt", "ig_user_id": "12345"}  # pragma: allowlist secret
        }))
        importlib.reload(sp)

        fail_resp = MagicMock()
        fail_resp.status_code = 400
        fail_resp.text = "Bad Request"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=fail_resp)
            with pytest.raises(RuntimeError, match="container"):
                await sp._post_instagram("Caption", "https://link.com", image_url="https://img.example.com/img.jpg")

    @pytest.mark.asyncio
    async def test_raises_when_no_container_id(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "instagram": {"connected": True, "access_token": "igt", "ig_user_id": "12345"}  # pragma: allowlist secret
        }))
        importlib.reload(sp)

        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {}  # no "id"
        container_resp.text = "{}"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=container_resp)
            with pytest.raises(RuntimeError, match="no container id"):
                await sp._post_instagram("Caption", "https://link.com", image_url="https://img.example.com/img.jpg")


class TestPostThreads:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, tmp_path):
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="not connected"):
            await sp._post_threads("caption", "https://link.com")

    @pytest.mark.asyncio
    async def test_posts_text_successfully(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "threads": {"connected": True, "access_token": "tht", "user_id": "u123", "handle": "testuser"}  # pragma: allowlist secret
        }))
        importlib.reload(sp)

        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "c123"}
        container_resp.text = ""

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "p456"}
        publish_resp.text = ""

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp._post_threads("Caption", "https://link.com")
        assert "threads.net" in result

    @pytest.mark.asyncio
    async def test_falls_back_to_text_on_image_failure(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "threads": {"connected": True, "access_token": "tht", "user_id": "u123", "handle": "user"}  # pragma: allowlist secret
        }))
        importlib.reload(sp)

        image_fail = MagicMock()
        image_fail.status_code = 400
        image_fail.text = "Image error"
        image_fail.json.return_value = {}

        text_ok = MagicMock()
        text_ok.status_code = 200
        text_ok.json.return_value = {"id": "ctxt123"}
        text_ok.text = ""

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "ptxt456"}
        publish_resp.text = ""

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[image_fail, text_ok, publish_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp._post_threads("Caption", "https://link.com", image_url="https://img.example.com/img.jpg")
        assert "threads.net" in result

    @pytest.mark.asyncio
    async def test_raises_on_publish_failure(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "threads": {"connected": True, "access_token": "tht", "user_id": "u123", "handle": "user"}  # pragma: allowlist secret
        }))
        importlib.reload(sp)

        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "c789"}
        container_resp.text = ""

        fail_publish = MagicMock()
        fail_publish.status_code = 500
        fail_publish.text = "Server Error"

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, fail_publish])
            mc.return_value.__aenter__.return_value = mock_client
            with pytest.raises(RuntimeError, match="publish"):
                await sp._post_threads("Caption", "https://link.com")


class TestPostTumblr:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, tmp_path):
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="not connected"):
            await sp._post_tumblr("caption", "https://link.com")

    @pytest.mark.asyncio
    async def test_raises_when_no_handle(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "tumblr": {"connected": True, "access_token": "tbt"}  # no handle
        }))
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="handle"):
            await sp._post_tumblr("caption", "https://link.com")

    @pytest.mark.asyncio
    async def test_posts_successfully(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "tumblr": {"connected": True, "access_token": "tbt", "handle": "myblog"}  # pragma: allowlist secret
        }))
        importlib.reload(sp)

        ok_resp = MagicMock()
        ok_resp.status_code = 201
        ok_resp.json.return_value = {"response": {"id": "post789"}}

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=ok_resp)
            result = await sp._post_tumblr("Caption", "https://link.com")
        assert "tumblr.com" in result

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, tmp_path):
        import importlib
        import api.social_post as sp
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "tumblr": {"connected": True, "access_token": "tbt", "handle": "myblog"}  # pragma: allowlist secret
        }))
        importlib.reload(sp)

        fail_resp = MagicMock()
        fail_resp.status_code = 403
        fail_resp.text = "Forbidden"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=fail_resp)
            with pytest.raises(RuntimeError, match="403"):
                await sp._post_tumblr("Caption", "https://link.com")


class TestCircuitBreakerDispatchers:
    @pytest.mark.asyncio
    async def test_post_to_threads_dispatches(self, tmp_path):
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        sp._threads_cb.reset()
        with patch.object(sp, "_post_threads", AsyncMock(return_value="https://threads.net/p/123")):
            result = await sp.post_to_threads("caption", "https://link.com")
        assert result == "https://threads.net/p/123"

    @pytest.mark.asyncio
    async def test_post_to_tumblr_dispatches(self, tmp_path):
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        sp._tumblr_cb.reset()
        with patch.object(sp, "_post_tumblr", AsyncMock(return_value="https://myblog.tumblr.com/post/1")):
            result = await sp.post_to_tumblr("caption", "https://link.com")
        assert result == "https://myblog.tumblr.com/post/1"

    @pytest.mark.asyncio
    async def test_post_to_instagram_dispatches(self, tmp_path):
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        sp._instagram_cb.reset()
        with patch.object(sp, "_post_instagram", AsyncMock(return_value="https://instagram.com/p/abc")):
            result = await sp.post_to_instagram("caption", "https://link.com", image_url="https://img.example.com/img.jpg")
        assert result == "https://instagram.com/p/abc"

    @pytest.mark.asyncio
    async def test_post_to_platform_threads(self, tmp_path):
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        sp._threads_cb.reset()
        with patch.object(sp, "_post_threads", AsyncMock(return_value="https://threads.net/@u/post/1")):
            result = await sp.post_to_platform("threads", "caption", "https://link.com")
        assert result == "https://threads.net/@u/post/1"

    @pytest.mark.asyncio
    async def test_post_to_platform_tumblr(self, tmp_path):
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        sp._tumblr_cb.reset()
        with patch.object(sp, "_post_tumblr", AsyncMock(return_value="https://blog.tumblr.com/post/2")):
            result = await sp.post_to_platform("tumblr", "caption", "https://link.com")
        assert result == "https://blog.tumblr.com/post/2"

    @pytest.mark.asyncio
    async def test_post_to_platform_facebook(self, tmp_path):
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        sp._facebook_cb.reset()
        with patch.object(sp, "_post_facebook", AsyncMock(return_value="https://facebook.com/p/1")):
            result = await sp.post_to_platform("facebook", "caption", "https://link.com")
        assert result == "https://facebook.com/p/1"
