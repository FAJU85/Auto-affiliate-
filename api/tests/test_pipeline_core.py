"""Unit tests for pipeline core logic (PF-01, PF-02, PF-06)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from api import pipeline


class TestTrackingUrl:
    def test_generates_unique_ids(self):
        t1, _ = pipeline._tracking_url("https://example.com/a")
        t2, _ = pipeline._tracking_url("https://example.com/a")
        assert t1 != t2

    def test_stores_in_redirects(self):
        pipeline._REDIRECTS.clear()
        tid, _ = pipeline._tracking_url("https://example.com/product")
        assert pipeline._REDIRECTS[tid] == "https://example.com/product"

    def test_redirect_uses_host_when_available(self, monkeypatch):
        monkeypatch.setattr("api.pipeline.settings.get_space_host",
                            lambda: "https://test.hf.space")
        tid, redirect = pipeline._tracking_url("https://example.com/p")
        assert redirect == f"https://test.hf.space/r/{tid}"

    def test_redirect_falls_back_to_deeplink_when_no_host(self, monkeypatch):
        monkeypatch.setattr("api.pipeline.settings.get_space_host", lambda: "")
        _, redirect = pipeline._tracking_url("https://example.com/fallback")
        assert redirect == "https://example.com/fallback"


class TestResolveRedirect:
    def test_resolves_from_memory(self):
        pipeline._REDIRECTS.clear()
        tid, _ = pipeline._tracking_url("https://example.com/mem")
        assert pipeline.resolve_redirect(tid) == "https://example.com/mem"

    def test_returns_none_for_unknown_id(self):
        result = pipeline.resolve_redirect("doesnotexist_abc")
        assert result is None


class TestRecordRun:
    def test_increments_run_count(self):
        pipeline.STATE["runCount"] = 0
        pipeline._record({"success": False, "error": "test"})
        assert pipeline.STATE["runCount"] == 1

    def test_increments_success_count_on_success(self):
        pipeline.STATE["successCount"] = 0
        pipeline._record({"success": True})
        assert pipeline.STATE["successCount"] == 1

    def test_does_not_increment_success_on_failure(self):
        pipeline.STATE["successCount"] = 0
        pipeline._record({"success": False, "error": "oops"})
        assert pipeline.STATE["successCount"] == 0

    def test_sets_last_error_on_failure(self):
        pipeline._record({"success": False, "error": "something broke"})
        assert pipeline.STATE["lastError"] == "something broke"

    def test_clears_last_error_on_success(self):
        pipeline.STATE["lastError"] = "previous error"
        pipeline._record({"success": True})
        assert pipeline.STATE["lastError"] is None


class TestRunPipelineGuards:
    def setup_method(self):
        pipeline.STATE["running"] = False
        pipeline.STATE["paused"] = False
        pipeline.STATE["pausedUntil"] = None

    @pytest.mark.asyncio
    async def test_rejects_when_already_running(self):
        pipeline.STATE["running"] = True
        result = await pipeline.run_pipeline()
        assert result["ok"] is False
        assert "already running" in result["error"]
        pipeline.STATE["running"] = False

    @pytest.mark.asyncio
    async def test_rejects_when_paused_manually(self):
        pipeline.STATE["paused"] = True
        pipeline.STATE["pausedUntil"] = None
        result = await pipeline.run_pipeline()
        assert result["ok"] is False
        assert "paused" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_auto_resumes_when_cooldown_expired(self, monkeypatch):
        import time
        pipeline.STATE["paused"] = True
        pipeline.STATE["pausedUntil"] = time.time() - 1  # expired 1 second ago

        # Mock _execute so the pipeline doesn't actually run
        monkeypatch.setattr(
            "api.pipeline._execute",
            AsyncMock(return_value={"success": True})
        )
        result = await pipeline.run_pipeline()
        assert pipeline.STATE["paused"] is False
        assert pipeline.STATE["pausedUntil"] is None


class TestGetTrends:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        trends = await pipeline.get_trends()
        assert isinstance(trends, list)
        assert len(trends) > 0

    @pytest.mark.asyncio
    async def test_returns_strings(self):
        trends = await pipeline.get_trends()
        assert all(isinstance(t, str) for t in trends)
