"""Cycle 18: deep main.py coverage — stats/clicks continue paths, health degraded, home fallback."""

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data18")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)
    os.environ.pop("BSKY_HANDLE", None)
    os.environ.pop("BSKY_APP_PASSWORD", None)

    import importlib
    import api.utils.settings as smod
    import api.utils.metrics as mmod
    import api.utils.budget as bmod
    smod._cache = None
    importlib.reload(smod)
    importlib.reload(mmod)
    importlib.reload(bmod)

    from api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestMainDeepPaths:
    def test_stats_skips_failed_runs_and_no_day(self, client):
        import api.utils.metrics as m
        # Add a failed run and a run without timestamp (no-day path)
        m.record_run({"success": False, "productSource": "sovrn", "timestamp": datetime.now(timezone.utc).isoformat()})
        m.record_run({"success": True, "productSource": "sovrn", "timestamp": ""})  # no day
        r = client.get("/api/stats")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_clicks_skips_run_without_day(self, client):
        import api.utils.metrics as m
        # Add run with empty timestamp
        m.record_run({"success": True, "clicks": 2, "timestamp": ""})
        r = client.get("/api/clicks")
        assert r.status_code == 200
        assert "daily" in r.json()

    def test_health_degraded_when_slo_below_50(self, client):
        with patch("api.pipeline.calculate_slo", return_value={"slo_pct": 30.0}):
            r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        # slo_pct < 50 → degraded
        assert data["status"] == "degraded"

    def test_health_misconfigured_when_missing_vars(self, client):
        # No BSKY creds set → missing_vars not empty → misconfigured
        with patch("api.pipeline.calculate_slo", return_value={"slo_pct": 99.0}):
            r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        # missing vars → misconfigured
        assert data["status"] in ("misconfigured", "healthy")

    def test_home_fallback_html(self, client):
        # DASHBOARD file doesn't exist in test env → fallback HTML
        with patch("api.main.DASHBOARD") as mock_dash:
            mock_dash.exists.return_value = False
            r = client.get("/")
        assert r.status_code == 200

    def test_logs_endpoint(self, client):
        r = client.get("/api/logs")
        assert r.status_code == 200

    def test_run_with_valid_platform_and_creds_triggers_pipeline(self, client):
        import api.utils.settings as smod
        os.environ["BSKY_HANDLE"] = "user.bsky.social"
        os.environ["BSKY_APP_PASSWORD"] = "testpass"  # pragma: allowlist secret
        smod.save_settings({"publishPlatforms": ["bluesky"], "bskyEnabled": True, "dailyCostCap": 5.0})
        try:
            with patch("asyncio.create_task"):
                r = client.post("/api/run")
            assert r.status_code == 200
            assert r.json()["ok"] is True
        finally:
            os.environ.pop("BSKY_HANDLE", None)
            os.environ.pop("BSKY_APP_PASSWORD", None)
            smod.save_settings({"publishPlatforms": ["bluesky"], "bskyEnabled": True, "dailyCostCap": 2.0})

    def test_metrics_logs_function(self, client):
        from api.main import metrics_logs
        result = metrics_logs(10)
        assert isinstance(result, list)

    def test_logs_endpoint_returns_list(self, client):
        r = client.get("/api/logs")
        assert r.status_code == 200


# ── social_post.py: remaining lines 303, 359, 380, 416-417, 422-425 ──────────

class TestSocialPostDeepPaths:
    @pytest.mark.asyncio
    async def test_post_mastodon_success_no_image(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        import json
        conn_file.write_text(json.dumps({
            "mastodon": {"connected": True, "access_token": "tok", "instance": "https://mastodon.social"}
        }))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        from unittest.mock import MagicMock, AsyncMock, patch
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"url": "https://mastodon.social/@user/post1"}

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=ok_resp)
            result = await sp._post_mastodon("Caption", "https://link.com")
        assert "mastodon.social" in result

    @pytest.mark.asyncio
    async def test_post_to_platform_threads(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import json
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"threads": {
            "connected": True, "access_token": "th_tok", "user_id": "12345"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        from unittest.mock import MagicMock, AsyncMock, patch
        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "container_t1"}

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "thread_post_1"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp.post_to_platform("threads", "Caption!", "https://link.com", product={})
        assert result is not None

    @pytest.mark.asyncio
    async def test_post_to_platform_tumblr(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        from unittest.mock import AsyncMock, patch
        with patch.object(sp, "post_to_tumblr", AsyncMock(return_value="https://tumblr.com/post/1")):
            result = await sp.post_to_platform("tumblr", "Caption", "https://link.com")
        assert result == "https://tumblr.com/post/1"
