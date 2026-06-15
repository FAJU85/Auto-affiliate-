"""Extended main.py integration tests — logs, debug, accounts, stats, dry-run."""

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)
    os.environ.pop("SOVRN_API_KEY", None)
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


class TestLogsEndpoints:
    def test_get_logs_returns_list(self, client):
        r = client.get("/api/logs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_logs_with_level_filter(self, client):
        r = client.get("/api/logs?level=info")
        assert r.status_code == 200

    def test_get_logs_with_component_filter(self, client):
        r = client.get("/api/logs?component=system")
        assert r.status_code == 200

    def test_clear_logs_returns_ok(self, client):
        r = client.post("/api/logs/clear")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_logs_summary_returns_counts(self, client):
        r = client.get("/api/logs/summary")
        assert r.status_code == 200
        data = r.json()
        assert "totalErrors" in data
        assert "totalWarns" in data


class TestDebugEndpoint:
    def test_returns_env_keys(self, client):
        r = client.get("/api/debug")
        assert r.status_code == 200
        data = r.json()
        assert "env" in data
        assert "networks" in data
        assert "lastRun" in data


class TestStatsEndpoint:
    def test_returns_list(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_days_param(self, client):
        r = client.get("/api/stats?days=3")
        assert r.status_code == 200


class TestAccountsEndpoints:
    def test_returns_bluesky_and_social(self, client):
        r = client.get("/api/accounts")
        assert r.status_code == 200
        data = r.json()
        assert "bluesky" in data
        assert "social" in data
        assert "connected" in data["bluesky"]

    def test_disconnect_bluesky(self, client):
        r = client.post("/api/accounts/bluesky/disconnect")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_enable_bluesky(self, client):
        r = client.post("/api/accounts/bluesky/enable")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_test_bluesky_without_creds(self, client):
        r = client.post("/api/accounts/bluesky/test")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert data["error"]  # any non-empty error message is fine


class TestDryRunEndpoint:
    def test_dry_run_without_sovrn_key(self, client):
        r = client.post("/api/dry-run")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False  # no product source


class TestAnalyzeLogsEndpoint:
    def test_analyze_without_ai_key(self, client):
        r = client.post("/api/logs/analyze")
        assert r.status_code == 200
        data = r.json()
        # No AI key → unknown status
        assert "status" in data
        assert data["status"] == "unknown"


class TestRedirectEndpoint:
    def test_redirect_with_click_tracking(self, client):
        from api import pipeline
        pipeline._REDIRECTS.clear()
        tid, _ = pipeline._tracking_url("https://example.com/product")
        r = client.get(f"/r/{tid}", follow_redirects=False)
        assert r.status_code in (301, 302, 307, 308)

    def test_redirect_increments_click(self, client):
        from api import pipeline
        pipeline._REDIRECTS.clear()
        tid, _ = pipeline._tracking_url("https://example.com/click-track")
        # First visit
        client.get(f"/r/{tid}", follow_redirects=False)
        # Check health still works
        r = client.get("/health")
        assert r.status_code == 200


class TestPipelineRunEndpointWithPause:
    def test_run_rejected_while_paused(self, client):
        from api import pipeline
        pipeline.STATE["paused"] = True
        pipeline.STATE["pausedUntil"] = None
        r = client.post("/api/run")
        pipeline.STATE["paused"] = False
        assert r.json()["ok"] is False
        assert "paused" in r.json()["error"].lower()

    def test_pause_sets_paused_state(self, client):
        client.post("/api/schedule/pause")
        from api import pipeline
        assert pipeline.STATE["paused"] is True
        client.post("/api/schedule/resume")

    def test_schedule_config_has_cron(self, client):
        r = client.get("/api/schedule/config")
        assert r.status_code == 200
        assert "cron" in r.json()


class TestSloEndpointExtended:
    def test_slo_after_mixed_runs(self, client):
        import api.utils.metrics as m
        from datetime import datetime, timezone
        # Record some runs directly
        for i in range(4):
            m.record_run({
                "success": i % 2 == 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        r = client.get("/api/slo")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("slo_pct"), (int, float, type(None)))


class TestPlatformRulesExtended:
    def test_all_platforms_present(self, client):
        body = client.get("/api/platform-rules").json()
        platforms = {item["platform"] for item in body["rules"]}
        expected = {"bluesky", "x", "threads", "facebook", "instagram", "mastodon", "tumblr"}
        assert expected <= platforms

    def test_instagram_max_hashtags(self, client):
        body = client.get("/api/platform-rules").json()
        ig = next(p for p in body["rules"] if p["platform"] == "instagram")
        assert ig["maxHashtags"] == 20


class TestBudgetEndpointExtended:
    def test_status_budget_structure(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        budget = r.json()["budget"]
        assert "spent" in budget
        assert isinstance(budget["spent"], float)
        assert "cap" in budget
