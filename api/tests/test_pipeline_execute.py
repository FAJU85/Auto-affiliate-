"""Unit tests for pipeline._execute code paths (PF-01, PF-04, PF-05)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


PRODUCT = {
    "name": "Widget Pro",
    "price": 29.99,
    "currency": "USD",
    "category": "electronics",
    "siteUrl": "https://example.com/widget",
    "deeplink": "https://example.com/widget",
    "source": "sovrn",
}


def _setup_env(monkeypatch):
    """Remove all external credentials so pipeline uses graceful-degradation paths."""
    monkeypatch.delenv("SOVRN_API_KEY", raising=False)
    monkeypatch.delenv("BSKY_HANDLE", raising=False)
    monkeypatch.delenv("BSKY_APP_PASSWORD", raising=False)


class TestDryRun:
    @pytest.mark.asyncio
    async def test_returns_ok_false_without_product(self, monkeypatch):
        _setup_env(monkeypatch)
        from api import pipeline
        with patch.object(pipeline, "_get_product", AsyncMock(return_value=None)):
            result = await pipeline.dry_run()
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_returns_ok_true_with_product(self, monkeypatch):
        _setup_env(monkeypatch)
        from api import pipeline
        with patch.object(pipeline, "_get_product", AsyncMock(return_value=PRODUCT)):
            with patch("api.ai.text.generate_post_text", AsyncMock(return_value="Great deal!")):
                result = await pipeline.dry_run()
        assert result["ok"] is True
        assert result["product"] == PRODUCT
        assert "caption" in result


class TestGetProduct:
    @pytest.mark.asyncio
    async def test_returns_none_without_sovrn_key(self, monkeypatch):
        monkeypatch.delenv("SOVRN_API_KEY", raising=False)
        from api import pipeline
        result = await pipeline._get_product()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_sovrn_product_when_available(self, monkeypatch):
        from api import pipeline
        with patch.object(pipeline, "_try_sovrn", AsyncMock(return_value=PRODUCT)):
            result = await pipeline._get_product()
        assert result == PRODUCT


class TestTrySovrn:
    @pytest.mark.asyncio
    async def test_returns_none_without_key(self, monkeypatch):
        monkeypatch.delenv("SOVRN_API_KEY", raising=False)
        from api import pipeline
        result = await pipeline._try_sovrn()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, monkeypatch):
        monkeypatch.setenv("SOVRN_API_KEY", "fake")
        from api import pipeline
        # Patch at the pipeline module boundary where _try_sovrn calls get_sovrn_product
        with patch("api.pipeline.get_sovrn_product", AsyncMock(side_effect=RuntimeError("network error"))):
            result = await pipeline._try_sovrn()
        assert result is None


class TestCalculateSlo:
    def test_slo_100_all_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as mmod
        importlib.reload(mmod)
        from datetime import datetime, timezone
        for _ in range(10):
            mmod.record_run({"success": True, "timestamp": datetime.now(timezone.utc).isoformat()})
        from api.pipeline import calculate_slo
        result = calculate_slo(window=10)
        assert result["slo_pct"] == 100.0
        assert result["error_budget_remaining_pct"] > 0
        importlib.reload(mmod)

    def test_error_budget_keys_present(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.pipeline import calculate_slo
        result = calculate_slo(window=10)
        assert "slo_pct" in result
        assert "error_budget_remaining_pct" in result
        assert "total" in result
        assert "slo_target" in result


class TestFindImage:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_url(self):
        from api import pipeline
        result = await pipeline._find_image({})
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_bytes_on_200_image_response(self):
        from api import pipeline
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "image/jpeg"}
        mock_resp.content = b"fakeimagebytes"
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            result = await pipeline._find_image({"imageUrl": "https://example.com/img.jpg"})
        assert result == b"fakeimagebytes"

    @pytest.mark.asyncio
    async def test_returns_none_on_non_image_content_type(self):
        from api import pipeline
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.content = b"<html>"
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            result = await pipeline._find_image({"imageUrl": "https://example.com/page"})
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        from api import pipeline
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("timeout"))
            result = await pipeline._find_image({"imageUrl": "https://example.com/img.jpg"})
        assert result is None


class TestRunPipelineExecution:
    def setup_method(self):
        from api import pipeline
        pipeline.STATE["running"] = False
        pipeline.STATE["paused"] = False
        pipeline.STATE["pausedUntil"] = None

    @pytest.mark.asyncio
    async def test_pipeline_times_out_gracefully(self, monkeypatch):
        import asyncio
        from api import pipeline
        async def slow_execute(started):
            await asyncio.sleep(999)
        monkeypatch.setattr(pipeline, "_execute", slow_execute)
        monkeypatch.setattr(pipeline, "PIPELINE_TIMEOUT", 0.01)
        result = await pipeline.run_pipeline()
        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_handles_uncaught_exception(self, monkeypatch):
        from api import pipeline
        async def boom(started):
            raise ValueError("unexpected error")
        monkeypatch.setattr(pipeline, "_execute", boom)
        result = await pipeline.run_pipeline()
        assert result["success"] is False
        assert "unexpected error" in result["error"]

    @pytest.mark.asyncio
    async def test_pipeline_clears_running_flag_on_error(self, monkeypatch):
        from api import pipeline
        async def boom(started):
            raise ValueError("crash")
        monkeypatch.setattr(pipeline, "_execute", boom)
        await pipeline.run_pipeline()
        assert pipeline.STATE["running"] is False
