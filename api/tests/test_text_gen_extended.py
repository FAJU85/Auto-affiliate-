"""Extended ai/text.py tests — _chat rate-limit, retry, _try_groq/_try_mistral paths."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestChatFunction:
    @pytest.mark.asyncio
    async def test_returns_content_on_200(self):
        from api.ai.text import _chat
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Great deal on this product!"}}]
        }
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _chat("https://api.groq.com", "key", "model", "system", "user")
        assert result == "Great deal on this product!"

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self):
        from api.ai.text import _chat
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server Error"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _chat("https://api.groq.com", "key", "model", "system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_empty_content(self):
        from api.ai.text import _chat
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": ""}}]}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _chat("https://api.groq.com", "key", "model", "system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_raises_rate_limited_after_3_429s(self):
        from api.ai.text import _chat
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "5"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with patch("asyncio.sleep", AsyncMock()):
                with pytest.raises(RuntimeError, match="rate_limited"):
                    await _chat("https://api.groq.com", "key", "model", "system", "user")

    @pytest.mark.asyncio
    async def test_retries_once_on_429_then_succeeds(self):
        from api.ai.text import _chat
        rate_resp = MagicMock()
        rate_resp.status_code = 429
        rate_resp.headers = {"Retry-After": "1"}
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"choices": [{"message": {"content": "Success after retry!"}}]}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(side_effect=[rate_resp, ok_resp])
            with patch("asyncio.sleep", AsyncMock()):
                result = await _chat("https://api.groq.com", "key", "model", "system", "user")
        assert result == "Success after retry!"


class TestTryGroq:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        result = await txt._try_groq("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_circuit_breaker_open(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        # Trip the circuit breaker
        txt.groq_cb.reset()
        for _ in range(3):
            try:
                await txt.groq_cb.call(AsyncMock(side_effect=RuntimeError("fail")))
            except Exception:
                pass
        # Now it should be open
        result = await txt._try_groq("system", "user")
        assert result is None
        txt.groq_cb.reset()

    @pytest.mark.asyncio
    async def test_returns_text_on_success(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        with patch.object(txt, "_chat", AsyncMock(return_value="AI generated text")):
            result = await txt._try_groq("system", "user")
        assert result == "AI generated text"

    @pytest.mark.asyncio
    async def test_returns_none_on_rate_limit_error(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        with patch.object(txt, "_chat", AsyncMock(side_effect=RuntimeError("rate_limited:30"))):
            result = await txt._try_groq("system", "user")
        assert result is None
        txt.groq_cb.reset()

    @pytest.mark.asyncio
    async def test_returns_none_on_generic_exception(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        with patch.object(txt, "_chat", AsyncMock(side_effect=Exception("network error"))):
            result = await txt._try_groq("system", "user")
        assert result is None
        txt.groq_cb.reset()


class TestTryMistral:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        result = await txt._try_mistral("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_circuit_breaker_open(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.mistral_cb.reset()
        for _ in range(3):
            try:
                await txt.mistral_cb.call(AsyncMock(side_effect=RuntimeError("fail")))
            except Exception:
                pass
        result = await txt._try_mistral("system", "user")
        assert result is None
        txt.mistral_cb.reset()

    @pytest.mark.asyncio
    async def test_returns_text_on_success(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.mistral_cb.reset()
        with patch.object(txt, "_chat", AsyncMock(return_value="Mistral generated text")):
            result = await txt._try_mistral("system", "user")
        assert result == "Mistral generated text"

    @pytest.mark.asyncio
    async def test_returns_none_on_rate_limit(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.mistral_cb.reset()
        with patch.object(txt, "_chat", AsyncMock(side_effect=RuntimeError("rate_limited:60"))):
            result = await txt._try_mistral("system", "user")
        assert result is None
        txt.mistral_cb.reset()

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.mistral_cb.reset()
        with patch.object(txt, "_chat", AsyncMock(side_effect=Exception("timeout"))):
            result = await txt._try_mistral("system", "user")
        assert result is None
        txt.mistral_cb.reset()
