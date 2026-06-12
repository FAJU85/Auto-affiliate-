"""Tests for /api/run pre-flight guards and history/clicks with actual run data."""

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone


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


class TestRunEndpointGuards:
    def test_rejects_when_cost_cap_exceeded(self, client):
        import api.utils.settings as smod
        smod.save_settings({"dailyCostCap": 0.001, "publishPlatforms": ["mastodon"]})
        try:
            with patch("api.utils.budget.get_daily_spend", return_value=1.0):
                r = client.post("/api/run")
            assert r.status_code == 200
            assert r.json()["ok"] is False
            assert "cap" in r.json()["error"].lower()
        finally:
            smod.save_settings({"dailyCostCap": 2.0, "publishPlatforms": ["bluesky"]})

    def test_rejects_when_no_platforms_selected(self, client):
        import api.utils.settings as smod
        smod.save_settings({"publishPlatforms": [], "dailyCostCap": 2.0})
        try:
            r = client.post("/api/run")
            assert r.status_code == 200
            assert r.json()["ok"] is False
            assert "platform" in r.json()["error"].lower()
        finally:
            smod.save_settings({"publishPlatforms": ["bluesky"], "dailyCostCap": 2.0})

    def test_rejects_when_bluesky_disabled(self, client):
        import api.utils.settings as smod
        smod.save_settings({"publishPlatforms": ["bluesky"], "bskyEnabled": False, "dailyCostCap": 2.0})
        try:
            r = client.post("/api/run")
            assert r.status_code == 200
            assert r.json()["ok"] is False
            assert "disabled" in r.json()["error"].lower()
        finally:
            smod.save_settings({"publishPlatforms": ["bluesky"], "bskyEnabled": True, "dailyCostCap": 2.0})

    def test_rejects_when_bsky_creds_missing(self, client):
        import api.utils.settings as smod
        smod.save_settings({"publishPlatforms": ["bluesky"], "bskyEnabled": True, "dailyCostCap": 2.0})
        os.environ.pop("BSKY_HANDLE", None)
        os.environ.pop("BSKY_APP_PASSWORD", None)
        r = client.post("/api/run")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "missing" in data["error"].lower() or "credentials" in data["error"].lower()


class TestHistoryWithData:
    def test_csv_includes_run_data(self, client):
        import api.utils.metrics as m
        m.record_run({
            "success": True,
            "product": "Widget Pro",
            "productSource": "sovrn",
            "captionChars": 120,
            "clicks": 3,
            "postUri": "at://did:plc:abc/post/1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        r = client.get("/api/history.csv")
        assert r.status_code == 200
        assert "Widget Pro" in r.text or "sovrn" in r.text

    def test_clicks_endpoint_with_runs(self, client):
        import api.utils.metrics as m
        m.record_run({
            "success": True,
            "clicks": 5,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        r = client.get("/api/clicks?days=30")
        assert r.status_code == 200
        data = r.json()
        assert "daily" in data
        # At least one day's data
        assert len(data["daily"]) >= 1

    def test_clicks_ctr_calculation(self, client):
        r = client.get("/api/clicks")
        data = r.json()
        for day in data.get("daily", []):
            if day["posts"] > 0:
                assert isinstance(day["ctr"], float)


class TestRateLimitGuardInBlueskyTest:
    def test_rate_limit_active_blocks_test(self, client):
        import time
        import api.bluesky_client as bc
        bc._save_ratelimit(time.time() + 3600)  # 1 hour in the future
        os.environ["BSKY_HANDLE"] = "user.bsky.social"
        os.environ["BSKY_APP_PASSWORD"] = "testpass"  # pragma: allowlist secret
        import api.main as m
        m._last_bsky_test = 0.0
        try:
            r = client.post("/api/accounts/bluesky/test")
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is False
            assert data.get("rateLimited") is True
        finally:
            bc._clear_ratelimit()
            os.environ.pop("BSKY_HANDLE", None)
            os.environ.pop("BSKY_APP_PASSWORD", None)
