"""Unit tests for AI log analyzer (ai/log_analyzer.py) — mocked HTTP."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestBuildPrompt:
    def test_includes_log_entries(self):
        from api.ai.log_analyzer import _build_prompt
        logs = [
            {"level": "error", "component": "pipeline", "msg": "something failed"},
            {"level": "info",  "component": "sovrn",   "msg": "fetched product"},
        ]
        prompt = _build_prompt(logs, None)
        assert "something failed" in prompt
        assert "fetched product" in prompt

    def test_includes_last_run(self):
        from api.ai.log_analyzer import _build_prompt
        run = {"success": False, "platforms": ["bluesky"], "error": "rate limited"}
        prompt = _build_prompt([], run)
        assert "rate limited" in prompt
        assert "False" in prompt

    def test_no_errors_message(self):
        from api.ai.log_analyzer import _build_prompt
        logs = [{"level": "info", "component": "system", "msg": "ok"}]
        prompt = _build_prompt(logs, None)
        assert "No errors or warnings" in prompt

    def test_empty_logs(self):
        from api.ai.log_analyzer import _build_prompt
        prompt = _build_prompt([], None)
        assert "RECENT LOGS" in prompt


class TestCallApi:
    @pytest.mark.asyncio
    async def test_returns_parsed_json_on_200(self):
        from api.ai.log_analyzer import _call_api
        payload = {"status": "healthy", "summary": "all good", "issues": [], "insights": []}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": json.dumps(payload)}}]
        }
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _call_api("http://fake", "key", "model", "prompt")
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_returns_none_on_non_200(self):
        from api.ai.log_analyzer import _call_api
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "error"
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _call_api("http://fake", "key", "model", "prompt")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        from api.ai.log_analyzer import _call_api
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("timeout"))
            result = await _call_api("http://fake", "key", "model", "prompt")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_content(self):
        from api.ai.log_analyzer import _call_api
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": ""}}]}
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await _call_api("http://fake", "key", "model", "prompt")
        assert result is None


class TestAnalyzeLogs:
    @pytest.mark.asyncio
    async def test_returns_fallback_when_no_keys(self, monkeypatch):
        from api.ai import log_analyzer
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        result = await log_analyzer.analyze_logs([])
        assert result["status"] == "unknown"
        assert result["provider"] is None

    @pytest.mark.asyncio
    async def test_uses_hf_when_key_set(self, monkeypatch):
        from api.ai import log_analyzer
        monkeypatch.setenv("HF_TOKEN", "fake-token")
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        fake_result = {"status": "healthy", "summary": "ok", "issues": [], "insights": [], "recommendation": "none"}
        with patch.object(log_analyzer, "_call_api", AsyncMock(return_value=fake_result)):
            result = await log_analyzer.analyze_logs([])
        assert result["provider"] == "huggingface"

    @pytest.mark.asyncio
    async def test_falls_back_to_mistral(self, monkeypatch):
        from api.ai import log_analyzer
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.setenv("MISTRAL_API_KEY", "mistral-key")
        fake_result = {"status": "warning", "summary": "warn", "issues": [], "insights": [], "recommendation": "fix"}
        with patch.object(log_analyzer, "_call_api", AsyncMock(return_value=fake_result)):
            result = await log_analyzer.analyze_logs([])
        assert result["provider"] == "mistral"

    @pytest.mark.asyncio
    async def test_falls_back_to_groq(self, monkeypatch):
        from api.ai import log_analyzer
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        fake_result = {"status": "critical", "summary": "bad", "issues": [], "insights": [], "recommendation": "fix now"}
        with patch.object(log_analyzer, "_call_api", AsyncMock(return_value=fake_result)):
            result = await log_analyzer.analyze_logs([])
        assert result["provider"] == "groq"
