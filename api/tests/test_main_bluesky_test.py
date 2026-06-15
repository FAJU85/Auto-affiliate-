"""Tests for /api/accounts/bluesky/test endpoint — live HTTP paths."""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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


def _reset_bsky_cooldown():
    import api.main as m
    import api.bluesky_client as bc
    m._last_bsky_test = 0.0
    bc._clear_ratelimit()
    bc._session.clear()


class TestBlueskytestEndpoint:
    def test_returns_false_when_creds_missing(self, client):
        _reset_bsky_cooldown()
        r = client.post("/api/accounts/bluesky/test")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert data["error"]  # any non-empty error about unconfigured credentials

    def test_returns_ok_when_200(self, client):
        _reset_bsky_cooldown()
        os.environ["BSKY_HANDLE"] = "user.bsky.social"
        os.environ["BSKY_APP_PASSWORD"] = "apppassword"  # pragma: allowlist secret
        try:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"did": "did:plc:abc123"}
            mock_resp.headers = {}
            with patch("httpx.AsyncClient") as mc:
                mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
                r = client.post("/api/accounts/bluesky/test")
            assert r.status_code == 200
            assert r.json()["ok"] is True
            assert r.json()["did"] == "did:plc:abc123"
        finally:
            os.environ.pop("BSKY_HANDLE", None)
            os.environ.pop("BSKY_APP_PASSWORD", None)

    def test_returns_rate_limited_on_429(self, client):
        _reset_bsky_cooldown()
        os.environ["BSKY_HANDLE"] = "user.bsky.social"
        os.environ["BSKY_APP_PASSWORD"] = "apppassword"  # pragma: allowlist secret
        try:
            mock_resp = MagicMock()
            mock_resp.status_code = 429
            mock_resp.headers = {"Retry-After": "60"}
            mock_resp.text = "Too Many Requests"
            with patch("httpx.AsyncClient") as mc:
                mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
                r = client.post("/api/accounts/bluesky/test")
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is False
            assert data.get("rateLimited") is True
        finally:
            os.environ.pop("BSKY_HANDLE", None)
            os.environ.pop("BSKY_APP_PASSWORD", None)

    def test_returns_error_on_401(self, client):
        _reset_bsky_cooldown()
        os.environ["BSKY_HANDLE"] = "user.bsky.social"
        os.environ["BSKY_APP_PASSWORD"] = "wrongpass"  # pragma: allowlist secret
        try:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_resp.headers = {}
            with patch("httpx.AsyncClient") as mc:
                mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
                r = client.post("/api/accounts/bluesky/test")
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is False
            assert "401" in data["error"]
        finally:
            os.environ.pop("BSKY_HANDLE", None)
            os.environ.pop("BSKY_APP_PASSWORD", None)

    def test_returns_error_on_exception(self, client):
        _reset_bsky_cooldown()
        os.environ["BSKY_HANDLE"] = "user.bsky.social"
        os.environ["BSKY_APP_PASSWORD"] = "apppassword"  # pragma: allowlist secret
        try:
            with patch("httpx.AsyncClient") as mc:
                mc.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("network failure"))
                r = client.post("/api/accounts/bluesky/test")
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is False
            assert "network failure" in data["error"]
        finally:
            os.environ.pop("BSKY_HANDLE", None)
            os.environ.pop("BSKY_APP_PASSWORD", None)


class TestMainAdditionalRoutes:
    def test_circuit_breakers_path_reset(self, client):
        r = client.post("/api/circuit-breakers/bluesky/reset")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_circuit_breakers_reset_all_path(self, client):
        r = client.post("/api/circuit-breakers/reset-all")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_stats_with_successful_runs(self, client):
        import api.utils.metrics as m
        from datetime import datetime, timezone
        m.record_run({
            "success": True,
            "productSource": "sovrn",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        r = client.get("/api/stats?days=7")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_home_page_fallback(self, client):
        r = client.get("/")
        assert r.status_code == 200
