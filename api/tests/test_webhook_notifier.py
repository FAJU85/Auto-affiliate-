"""Tests for api.utils.webhook_notifier — outbound run-complete webhook."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.utils.webhook_notifier import fire_webhook, notify_run_complete


# ── fire_webhook ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fire_webhook_empty_url_returns_false():
    result = await fire_webhook("", {"test": 1})
    assert result is False


@pytest.mark.asyncio
async def test_fire_webhook_success_200():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    with patch("api.utils.webhook_notifier.httpx.AsyncClient", return_value=mock_client):
        result = await fire_webhook("https://example.com/hook", {"test": 1})
    assert result is True


@pytest.mark.asyncio
async def test_fire_webhook_success_201():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    with patch("api.utils.webhook_notifier.httpx.AsyncClient", return_value=mock_client):
        result = await fire_webhook("https://example.com/hook", {"data": "x"})
    assert result is True


@pytest.mark.asyncio
async def test_fire_webhook_500_returns_false():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    with patch("api.utils.webhook_notifier.httpx.AsyncClient", return_value=mock_client):
        result = await fire_webhook("https://example.com/hook", {})
    assert result is False


@pytest.mark.asyncio
async def test_fire_webhook_network_exception_returns_false():
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
    with patch("api.utils.webhook_notifier.httpx.AsyncClient", return_value=mock_client):
        result = await fire_webhook("https://example.com/hook", {})
    assert result is False


@pytest.mark.asyncio
async def test_fire_webhook_timeout_returns_false():
    import httpx as _httpx
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(
        side_effect=_httpx.TimeoutException("timed out", request=MagicMock())
    )
    with patch("api.utils.webhook_notifier.httpx.AsyncClient", return_value=mock_client):
        result = await fire_webhook("https://example.com/hook", {})
    assert result is False


# ── notify_run_complete ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_run_complete_no_env_var_returns_false(monkeypatch):
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    result = await notify_run_complete({"success": True})
    assert result is False


@pytest.mark.asyncio
async def test_notify_run_complete_empty_env_var_returns_false(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "")
    result = await notify_run_complete({"success": True})
    assert result is False


@pytest.mark.asyncio
async def test_notify_run_complete_calls_fire_webhook(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/run")
    with patch("api.utils.webhook_notifier.fire_webhook", new=AsyncMock(return_value=True)) as mock_fw:
        result = await notify_run_complete({"success": True})
    mock_fw.assert_called_once()
    assert result is True


@pytest.mark.asyncio
async def test_notify_run_complete_payload_has_event_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/run")
    captured = {}

    async def _capture(url, payload, **kwargs):
        captured.update(payload)
        return True

    with patch("api.utils.webhook_notifier.fire_webhook", side_effect=_capture):
        await notify_run_complete({"success": True})

    assert captured.get("event") == "run_complete"


@pytest.mark.asyncio
async def test_notify_run_complete_payload_has_timestamp_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/run")
    captured = {}

    async def _capture(url, payload, **kwargs):
        captured.update(payload)
        return True

    with patch("api.utils.webhook_notifier.fire_webhook", side_effect=_capture):
        await notify_run_complete({"success": False, "error": "test"})

    assert "timestamp" in captured


@pytest.mark.asyncio
async def test_notify_run_complete_payload_has_result_key(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://hooks.example.com/run")
    run_result = {"success": True, "product": "Widget", "durationMs": 1234}
    captured = {}

    async def _capture(url, payload, **kwargs):
        captured.update(payload)
        return True

    with patch("api.utils.webhook_notifier.fire_webhook", side_effect=_capture):
        await notify_run_complete(run_result)

    assert captured.get("result") == run_result
