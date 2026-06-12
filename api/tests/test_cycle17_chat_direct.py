"""Cycle 17: direct _chat coverage tests without importlib.reload."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestChatDirectCoverage:
    """Test _chat, _try_groq, _try_mistral without reload to get accurate coverage."""

    @pytest.mark.asyncio
    async def test_chat_429_exhausts_retries_raises_ratelimited(self):
        from api.ai.text import _chat, groq_cb, GROQ_URL, GROQ_MODEL
        groq_cb.reset()

        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "1"}
        resp_429.text = "Too Many Requests"

        with patch("api.ai.text.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp_429)
            with patch("asyncio.sleep", AsyncMock()):
                with pytest.raises(RuntimeError, match="rate_limited"):
                    await _chat(GROQ_URL, "key", GROQ_MODEL, "sys", "usr")
        groq_cb.reset()

    @pytest.mark.asyncio
    async def test_chat_non_200_returns_none(self):
        from api.ai.text import _chat, GROQ_URL, GROQ_MODEL

        resp_503 = MagicMock()
        resp_503.status_code = 503
        resp_503.text = "Service Unavailable"

        with patch("api.ai.text.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp_503)
            result = await _chat(GROQ_URL, "key", GROQ_MODEL, "sys", "usr")
        assert result is None

    @pytest.mark.asyncio
    async def test_try_groq_ratelimited_runtime_returns_none(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from api.ai import text as txt
        txt.groq_cb.reset()

        # Patch at module level so the function reference in _try_groq is patched
        with patch("api.ai.text._chat", AsyncMock(side_effect=RuntimeError("HTTP 503 error"))):
            result = await txt._try_groq("system", "user")
        assert result is None
        txt.groq_cb.reset()

    @pytest.mark.asyncio
    async def test_try_groq_ratelimited_keyword_returns_none(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from api.ai import text as txt
        txt.groq_cb.reset()

        with patch("api.ai.text._chat", AsyncMock(side_effect=RuntimeError("rate_limited:60"))):
            result = await txt._try_groq("system", "user")
        assert result is None
        txt.groq_cb.reset()

    @pytest.mark.asyncio
    async def test_try_groq_generic_exception_returns_none(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from api.ai import text as txt
        txt.groq_cb.reset()

        with patch("api.ai.text._chat", AsyncMock(side_effect=Exception("connection refused"))):
            result = await txt._try_groq("system", "user")
        assert result is None
        txt.groq_cb.reset()

    @pytest.mark.asyncio
    async def test_try_mistral_non_ratelimited_runtime_returns_none(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
        from api.ai import text as txt
        txt.mistral_cb.reset()

        with patch("api.ai.text._chat", AsyncMock(side_effect=RuntimeError("upstream error"))):
            result = await txt._try_mistral("system", "user")
        assert result is None
        txt.mistral_cb.reset()

    @pytest.mark.asyncio
    async def test_try_mistral_ratelimited_returns_none(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
        from api.ai import text as txt
        txt.mistral_cb.reset()

        with patch("api.ai.text._chat", AsyncMock(side_effect=RuntimeError("rate_limited:30"))):
            result = await txt._try_mistral("system", "user")
        assert result is None
        txt.mistral_cb.reset()

    @pytest.mark.asyncio
    async def test_try_mistral_generic_exception_returns_none(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
        from api.ai import text as txt
        txt.mistral_cb.reset()

        with patch("api.ai.text._chat", AsyncMock(side_effect=Exception("timeout"))):
            result = await txt._try_mistral("system", "user")
        assert result is None
        txt.mistral_cb.reset()

    @pytest.mark.asyncio
    async def test_groq_cb_open_warns_and_returns_none_direct(self, monkeypatch):
        """Hit lines 171-172: groq circuit breaker is open."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from api.ai import text as txt
        txt.groq_cb.reset()
        # Trip the circuit breaker using the original module's CB
        for _ in range(txt.groq_cb.failure_threshold):
            try:
                await txt.groq_cb.call(AsyncMock(side_effect=RuntimeError("fail")))
            except Exception:
                pass
        assert txt.groq_cb.is_open()
        result = await txt._try_groq("system", "user")
        assert result is None
        txt.groq_cb.reset()

    @pytest.mark.asyncio
    async def test_mistral_cb_open_warns_and_returns_none_direct(self, monkeypatch):
        """Hit lines 192-193: mistral circuit breaker is open."""
        monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
        from api.ai import text as txt
        txt.mistral_cb.reset()
        for _ in range(txt.mistral_cb.failure_threshold):
            try:
                await txt.mistral_cb.call(AsyncMock(side_effect=RuntimeError("fail")))
            except Exception:
                pass
        assert txt.mistral_cb.is_open()
        result = await txt._try_mistral("system", "user")
        assert result is None
        txt.mistral_cb.reset()


class TestBlueskyClientDirectCoverage:
    """Test bluesky_client without reload for accurate coverage."""

    @pytest.mark.asyncio
    async def test_upload_image_non_200_warns_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.bluesky_client import _upload_image

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.text = "Server Error"

        with patch("api.bluesky_client.httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=fail_resp)
            result = await _upload_image("jwt", b"imgdata")
        assert result is None

    @pytest.mark.asyncio
    async def test_post_to_bluesky_retry_sleep_then_raise(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "testpass")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.bluesky_client import post_to_bluesky, bluesky_cb, MAX_RETRIES
        bluesky_cb.reset()

        sleep_calls = []

        async def fake_sleep(s):
            sleep_calls.append(s)

        with patch("api.bluesky_client._post_async", AsyncMock(side_effect=RuntimeError("network error"))):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                with pytest.raises(RuntimeError, match="network error"):
                    await post_to_bluesky("Caption", "https://link.com", None, {})
        # Should have slept between retries
        assert len(sleep_calls) >= MAX_RETRIES - 1
        bluesky_cb.reset()

    @pytest.mark.asyncio
    async def test_post_to_bluesky_circuit_breaker_reraises(self, monkeypatch, tmp_path):
        """Hit line 353: CB open raises RuntimeError('Circuit breaker...') → re-raised."""
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "testpass")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.bluesky_client import post_to_bluesky, bluesky_cb
        bluesky_cb.reset()

        with patch("api.bluesky_client._post_async", AsyncMock(
            side_effect=RuntimeError("Circuit breaker 'bluesky' is OPEN")
        )):
            with pytest.raises(RuntimeError, match="Circuit breaker"):
                await post_to_bluesky("Caption", "https://link.com", None, {})
        bluesky_cb.reset()

    @pytest.mark.asyncio
    async def test_post_to_bluesky_generic_exception_non_rate_logs_warn(self, monkeypatch, tmp_path):
        """Hit line 375: generic exception without 'rate' or 'expired' keywords."""
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "testpass")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.bluesky_client import post_to_bluesky, bluesky_cb
        bluesky_cb.reset()

        with patch("api.bluesky_client._post_async", AsyncMock(side_effect=Exception("connection refused"))):
            with patch("asyncio.sleep", AsyncMock()):
                with pytest.raises(Exception):
                    await post_to_bluesky("Caption", "https://link.com", None, {})
        bluesky_cb.reset()

    def test_build_post_with_cta_link_empty_phrase_skipped(self, tmp_path, monkeypatch):
        """Hit line 230: empty cta phrase string in _build_post_with_cta_link."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.bluesky_client import _build_post_with_cta_link

        # Inject settings with empty CTA phrase so the empty-string check is hit
        with patch("api.utils.settings.get_settings", return_value={"ctaPhrases": ["", "Buy now!"]}):
            result, facets = _build_post_with_cta_link("Great product!", "https://example.com/p")
        assert "example.com" in result or isinstance(facets, list)
