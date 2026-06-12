"""Tests for bluesky_client.py post flow — _post_async and post_to_bluesky."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestPostAsync:
    @pytest.mark.asyncio
    async def test_raises_when_creds_missing(self, monkeypatch):
        monkeypatch.delenv("BSKY_HANDLE", raising=False)
        monkeypatch.delenv("BSKY_APP_PASSWORD", raising=False)
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        with pytest.raises(RuntimeError, match="missing"):
            await bc._post_async("caption", "https://example.com", None, {})

    @pytest.mark.asyncio
    async def test_posts_successfully_without_image(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {"accessJwt": "jwt123", "did": "did:plc:abc"}

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {"uri": "at://did:plc:abc/app.bsky.feed.post/1234"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[session_resp, post_resp])
            mc.return_value.__aenter__.return_value = mock_client
            uri = await bc._post_async("Great deal!", "https://example.com/product", None, {"name": "Widget"})
        assert "at://" in uri

    @pytest.mark.asyncio
    async def test_posts_with_image(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {"accessJwt": "jwt123", "did": "did:plc:abc"}

        blob_resp = MagicMock()
        blob_resp.status_code = 200
        blob_resp.json.return_value = {"blob": {"$type": "blob", "ref": {"$link": "bafyexample"}}}

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {"uri": "at://did:plc:abc/app.bsky.feed.post/9999"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[session_resp, blob_resp, post_resp])
            mc.return_value.__aenter__.return_value = mock_client
            uri = await bc._post_async("Caption!", "https://example.com", b"imgdata", {"name": "Widget"})
        assert "at://" in uri

    @pytest.mark.asyncio
    async def test_raises_on_createrecord_429(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {"accessJwt": "jwt123", "did": "did:plc:abc"}

        post_resp = MagicMock()
        post_resp.status_code = 429
        post_resp.headers = {"Retry-After": "60"}
        post_resp.text = "Rate Limited"

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[session_resp, post_resp])
            mc.return_value.__aenter__.return_value = mock_client
            with pytest.raises(RuntimeError, match="rate-limited"):
                await bc._post_async("caption", "https://example.com", None, {})

    @pytest.mark.asyncio
    async def test_raises_on_createrecord_401(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {"accessJwt": "jwt123", "did": "did:plc:abc"}

        post_resp = MagicMock()
        post_resp.status_code = 401
        post_resp.text = "Unauthorized"

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[session_resp, post_resp])
            mc.return_value.__aenter__.return_value = mock_client
            with pytest.raises(RuntimeError, match="401"):
                await bc._post_async("caption", "https://example.com", None, {})


class TestPostToBluesky:
    @pytest.mark.asyncio
    async def test_success_returns_uri(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)

        expected_uri = "at://did:plc:abc/app.bsky.feed.post/1234"
        with patch.object(bc, "_post_async", AsyncMock(return_value=expected_uri)):
            result = await bc.post_to_bluesky("Caption", "https://example.com", None, {"name": "Widget"})
        assert result == expected_uri

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)

        expected_uri = "at://did:plc:abc/app.bsky.feed.post/9999"
        # First attempt fails, second succeeds
        with patch.object(bc, "_post_async", AsyncMock(side_effect=[
            RuntimeError("HTTP 500: server error"),
            expected_uri
        ])):
            with patch("asyncio.sleep", AsyncMock()):
                result = await bc.post_to_bluesky("Caption", "https://example.com", None, {})
        assert result == expected_uri

    @pytest.mark.asyncio
    async def test_raises_on_rate_limit(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)

        with patch.object(bc, "_post_async", AsyncMock(side_effect=RuntimeError("rate-limited (429)"))):
            with pytest.raises(RuntimeError, match="rate-limited"):
                await bc.post_to_bluesky("Caption", "https://example.com", None, {})

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        # Reset circuit breaker so tests don't bleed state
        bc.bluesky_cb.reset()

        with patch.object(bc, "_post_async", AsyncMock(side_effect=RuntimeError("persistent error"))):
            with patch("asyncio.sleep", AsyncMock()):
                with pytest.raises(RuntimeError):
                    await bc.post_to_bluesky("Caption", "https://example.com", None, {})

    @pytest.mark.asyncio
    async def test_clears_session_on_401_error(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "test-app-password")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc.bluesky_cb.reset()

        # Verify that RuntimeError with "401" causes _clear_session to be called
        cleared = []
        original_clear = bc._clear_session

        def mock_clear():
            cleared.append(True)
            original_clear()

        with patch.object(bc, "_post_async", AsyncMock(side_effect=RuntimeError("401 Unauthorized"))):
            with patch.object(bc, "_clear_session", side_effect=mock_clear):
                with patch("asyncio.sleep", AsyncMock()):
                    with pytest.raises(RuntimeError):
                        await bc.post_to_bluesky("Caption", "https://example.com", None, {})
        # _clear_session should have been called at least once
        assert len(cleared) >= 1
