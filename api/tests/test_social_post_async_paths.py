"""Tests for async image upload paths and exception handler branches in social_post.py."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestUploadMastodonImageAsyncPath:
    @pytest.mark.asyncio
    async def test_202_polls_until_ready(self):
        from api.social_post import _upload_mastodon_image

        upload_resp = MagicMock()
        upload_resp.status_code = 202
        upload_resp.json.return_value = {"id": "media_async_123"}

        poll_not_ready = MagicMock()
        poll_not_ready.status_code = 206  # not ready yet

        poll_ready = MagicMock()
        poll_ready.status_code = 200

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=upload_resp)
            mock_client.get = AsyncMock(side_effect=[poll_not_ready, poll_ready])
            mc.return_value.__aenter__.return_value = mock_client
            with patch("asyncio.sleep", AsyncMock()):
                result = await _upload_mastodon_image(
                    "https://mastodon.social",
                    {"Authorization": "Bearer tok"},
                    b"imgdata"
                )
        assert result == "media_async_123"

    @pytest.mark.asyncio
    async def test_202_returns_none_when_no_id(self):
        from api.social_post import _upload_mastodon_image

        upload_resp = MagicMock()
        upload_resp.status_code = 202
        upload_resp.json.return_value = {}  # no id

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=upload_resp)
            result = await _upload_mastodon_image(
                "https://mastodon.social",
                {"Authorization": "Bearer tok"},
                b"imgdata"
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_202_returns_none_when_poll_times_out(self):
        from api.social_post import _upload_mastodon_image

        upload_resp = MagicMock()
        upload_resp.status_code = 202
        upload_resp.json.return_value = {"id": "async_timeout_id"}

        poll_not_ready = MagicMock()
        poll_not_ready.status_code = 206

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=upload_resp)
            mock_client.get = AsyncMock(return_value=poll_not_ready)
            mc.return_value.__aenter__.return_value = mock_client
            with patch("asyncio.sleep", AsyncMock()):
                result = await _upload_mastodon_image(
                    "https://mastodon.social",
                    {"Authorization": "Bearer tok"},
                    b"imgdata"
                )
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        from api.social_post import _upload_mastodon_image

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("upload failed"))
            result = await _upload_mastodon_image(
                "https://mastodon.social",
                {"Authorization": "Bearer tok"},
                b"imgdata"
            )
        assert result is None


class TestPostToPlatformEdgeCases:
    @pytest.mark.asyncio
    async def test_circuit_breaker_error_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        sp._mastodon_cb.reset()
        with patch.object(sp, "_post_mastodon", AsyncMock(side_effect=RuntimeError("Circuit breaker 'mastodon' is OPEN"))):
            result = await sp.post_to_platform("mastodon", "caption", "https://link.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_generic_exception_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        sp._mastodon_cb.reset()
        with patch.object(sp, "_post_mastodon", AsyncMock(side_effect=Exception("unexpected error"))):
            result = await sp.post_to_platform("mastodon", "caption", "https://link.com")
        assert result is None


class TestBlueskyclientExceptionBranches:
    @pytest.mark.asyncio
    async def test_generic_exception_with_rate_keyword_waits(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "testpass")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc.bluesky_cb.reset()

        sleep_calls = []

        async def fake_sleep(s):
            sleep_calls.append(s)

        expected_uri = "at://did:plc:abc/post/1"
        with patch.object(bc, "_post_async", AsyncMock(side_effect=[
            Exception("API rate limit exceeded"),
            expected_uri
        ])):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                result = await bc.post_to_bluesky("Caption", "https://link.com", None, {})
        assert result == expected_uri
        # Should have slept for rate-limit wait
        assert any(s >= 60 for s in sleep_calls)

    @pytest.mark.asyncio
    async def test_generic_exception_with_expired_clears_session(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "testpass")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc.bluesky_cb.reset()
        # Seed session
        bc._session.update({"accessJwt": "jwt_abc", "did": "did:plc:123", "expiry": 9999999999})

        cleared = []

        def mock_clear():
            cleared.append(True)

        with patch.object(bc, "_post_async", AsyncMock(side_effect=[
            Exception("Token expired"),
            "at://did:plc:abc/post/99"
        ])):
            with patch.object(bc, "_clear_session", side_effect=mock_clear):
                with patch("asyncio.sleep", AsyncMock()):
                    await bc.post_to_bluesky("Caption", "https://link.com", None, {})
        assert len(cleared) >= 1
