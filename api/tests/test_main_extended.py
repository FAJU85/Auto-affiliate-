"""Extended main.py tests — auth middleware, networks, history, dedup, circuit breakers, diagnose, finops."""

import os
import pytest
from unittest.mock import AsyncMock, patch
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


class TestAuthMiddleware:
    def test_api_without_password_allows_all(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200

    def test_api_with_password_rejects_unauthorized(self, client):
        os.environ["DASHBOARD_PASSWORD"] = "testpass123"
        try:
            r = client.get("/api/status")
            assert r.status_code == 401
            assert r.json()["ok"] is False
        finally:
            os.environ.pop("DASHBOARD_PASSWORD", None)

    def test_api_with_correct_bearer_token_allowed(self, client):
        os.environ["DASHBOARD_PASSWORD"] = "testpass123"
        try:
            r = client.get("/api/status", headers={"Authorization": "Bearer testpass123"})
            assert r.status_code == 200
        finally:
            os.environ.pop("DASHBOARD_PASSWORD", None)

    def test_health_always_public(self, client):
        os.environ["DASHBOARD_PASSWORD"] = "testpass123"
        try:
            r = client.get("/health")
            assert r.status_code == 200
        finally:
            os.environ.pop("DASHBOARD_PASSWORD", None)

    def test_redirect_route_is_public(self, client):
        os.environ["DASHBOARD_PASSWORD"] = "testpass123"
        try:
            r = client.get("/r/nonexistent", follow_redirects=False)
            assert r.status_code in (301, 302, 307, 308, 404)
        finally:
            os.environ.pop("DASHBOARD_PASSWORD", None)


class TestNetworksEndpoints:
    def test_networks_returns_list(self, client):
        r = client.get("/api/networks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_network_test_unknown(self, client):
        r = client.get("/api/network/test?network=fakenet")
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_network_test_known(self, client):
        r = client.get("/api/network/test?network=sovrn")
        assert r.status_code == 200
        data = r.json()
        assert "ok" in data
        assert "network" in data


class TestHistoryEndpoints:
    def test_history_returns_list(self, client):
        r = client.get("/api/history")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_history_csv_returns_text(self, client):
        r = client.get("/api/history.csv")
        assert r.status_code == 200
        assert "timestamp" in r.text

    def test_clicks_returns_daily_and_total(self, client):
        r = client.get("/api/clicks")
        assert r.status_code == 200
        data = r.json()
        assert "daily" in data
        assert "total" in data


class TestDedupEndpoints:
    def test_dedup_stats_returns_structure(self, client):
        r = client.get("/api/dedup/stats")
        assert r.status_code == 200
        data = r.json()
        assert "bySource" in data

    def test_dedup_reset_clears_store(self, client):
        r = client.post("/api/dedup/reset")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert "cleared" in r.json()

    def test_slo_reset_returns_ok(self, client):
        r = client.post("/api/slo/reset")
        assert r.status_code == 200
        assert r.json()["ok"] is True


class TestFinOpsEndpoint:
    def test_finops_structure(self, client):
        r = client.get("/api/finops")
        assert r.status_code == 200
        data = r.json()
        assert "today_usd" in data
        assert "cap_usd" in data
        assert "forecast" in data

    def test_finops_today_usd_is_float(self, client):
        r = client.get("/api/finops")
        assert isinstance(r.json()["today_usd"], float)


class TestInsightsEndpoint:
    def test_insights_structure(self, client):
        r = client.get("/api/insights")
        assert r.status_code == 200
        data = r.json()
        assert "networkHealth" in data
        assert "dedup" in data
        assert "totalClicks" in data


class TestCircuitBreakerEndpoint:
    def test_reset_all(self, client):
        r = client.post("/api/circuit-breaker/reset", json={"name": "all"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_reset_known_breaker(self, client):
        r = client.post("/api/circuit-breaker/reset", json={"name": "bluesky"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_reset_unknown_breaker_reports_error(self, client):
        r = client.post("/api/circuit-breaker/reset", json={"name": "fakecb"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "error" in data

    def test_reset_empty_name_resets_all(self, client):
        r = client.post("/api/circuit-breaker/reset", json={"name": ""})
        assert r.status_code == 200
        assert r.json()["ok"] is True


class TestDiagnoseEndpoint:
    def test_returns_checks_list(self, client):
        r = client.get("/api/diagnose")
        assert r.status_code == 200
        data = r.json()
        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_returns_ready_field(self, client):
        r = client.get("/api/diagnose")
        data = r.json()
        assert "ready" in data
        assert isinstance(data["ready"], bool)

    def test_circuit_breakers_in_response(self, client):
        r = client.get("/api/diagnose")
        data = r.json()
        assert "circuitBreakers" in data

    def test_pipeline_running_field(self, client):
        r = client.get("/api/diagnose")
        data = r.json()
        assert "pipelineRunning" in data


class TestAiGenerateEndpoint:
    def test_ai_generate_returns_text(self, client):
        with patch("api.ai.text.generate_post_text", new=AsyncMock(return_value="Great deal on Laptop!")):
            r = client.post("/api/ai/generate", json={
                "productName": "Laptop Pro",
                "category": "electronics",
                "description": "Fast laptop"
            })
        assert r.status_code == 200
        assert "text" in r.json()


class TestOAuthCallbackEndpoint:
    def test_oauth_callback_missing_code_redirects(self, client):
        r = client.get("/oauth/social/callback?platform=mastodon", follow_redirects=False)
        assert r.status_code in (302, 303, 307)

    def test_oauth_callback_with_error_redirects(self, client):
        r = client.get("/oauth/social/callback?platform=mastodon&error=access_denied", follow_redirects=False)
        assert r.status_code in (302, 303, 307)

    def test_oauth_callback_expired_state_redirects(self, client):
        r = client.get(
            "/oauth/social/callback?platform=mastodon&code=abc&state=nonexistent",
            follow_redirects=False
        )
        assert r.status_code in (302, 303, 307)
