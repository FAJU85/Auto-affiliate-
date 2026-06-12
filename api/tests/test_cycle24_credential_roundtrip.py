"""Cycle 24: regression tests for credential save→reload round-trip.

Previously credentials (X tokens, Facebook/Instagram access tokens) were
silently dropped when reading back via GET /api/accounts, causing the dashboard
to appear empty after a page refresh even though data was saved correctly.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def cred_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("BSKY_HANDLE", raising=False)
    monkeypatch.delenv("BSKY_APP_PASSWORD", raising=False)

    # social_oauth.CONNECTIONS_FILE is a module-level constant set at import time;
    # patch it to the test's tmp_path so save and load use the same directory.
    import api.social_oauth as so
    monkeypatch.setattr(so, "CONNECTIONS_FILE", tmp_path / "social-connections.json")

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


class TestCredentialRoundTrip:
    """Save credentials then read them back — the page-refresh bug."""

    def test_x_credentials_visible_after_save(self, cred_client):
        """POST /api/social/x/credentials then GET /api/accounts — fields must be non-empty."""
        r = cred_client.post("/api/social/x/credentials", json={
            "handle":          "myuser",
            "consumer_key":    "ck_real",
            "consumer_secret": "cs_real",
            "access_token":    "at_real",
            "access_secret":   "as_real",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r2 = cred_client.get("/api/accounts")
        assert r2.status_code == 200
        x = r2.json()["social"]["x"]
        assert x["connected"] is True
        assert x["handle"] == "myuser"
        # Credentials must be present (masked) so the form can show "already saved"
        assert x["consumer_key"]    != ""
        assert x["consumer_secret"] != ""
        assert x["access_token"]    != ""
        assert x["access_secret"]   != ""

    def test_facebook_credentials_visible_after_save(self, cred_client):
        """POST /api/social/facebook/credentials then GET /api/accounts."""
        r = cred_client.post("/api/social/facebook/credentials", json={
            "handle":            "mypage",
            "page_id":           "pg_123",
            "page_access_token": "pat_real",
        })
        assert r.status_code == 200

        r2 = cred_client.get("/api/accounts")
        fb = r2.json()["social"]["facebook"]
        assert fb["connected"] is True
        assert fb["page_access_token"] != ""
        assert fb["page_id"] == "pg_123"

    def test_instagram_credentials_visible_after_save(self, cred_client):
        """POST /api/social/instagram/credentials then GET /api/accounts."""
        r = cred_client.post("/api/social/instagram/credentials", json={
            "handle":       "iguser",
            "ig_user_id":   "ig_456",
            "access_token": "ig_tok_real",
        })
        assert r.status_code == 200

        r2 = cred_client.get("/api/accounts")
        ig = r2.json()["social"]["instagram"]
        assert ig["connected"] is True
        assert ig["access_token"] != ""
        assert ig["ig_user_id"] == "ig_456"

    def test_x_partial_update_preserves_existing_keys(self, cred_client):
        """Partial save (only handle + one key) must not wipe the other saved keys."""
        # First save all four keys
        cred_client.post("/api/social/x/credentials", json={
            "handle":          "partialuser",
            "consumer_key":    "ck_v1",
            "consumer_secret": "cs_v1",
            "access_token":    "at_v1",
            "access_secret":   "as_v1",
        })

        # Then update only consumer_key (simulates user only changing one field)
        cred_client.post("/api/social/x/credentials", json={
            "handle":       "partialuser",
            "consumer_key": "ck_v2",
            # consumer_secret, access_token, access_secret omitted (mask not sent)
        })

        r = cred_client.get("/api/accounts")
        x = r.json()["social"]["x"]
        # consumer_key updated, others preserved
        assert x["consumer_secret"] != ""
        assert x["access_token"]    != ""
        assert x["access_secret"]   != ""

    def test_x_credentials_are_masked_not_plaintext(self, cred_client):
        """Credentials must be returned as mask ('••••'), not the actual secret value."""
        cred_client.post("/api/social/x/credentials", json={
            "handle":          "maskuser",
            "consumer_key":    "real_secret_key",
            "consumer_secret": "real_secret_secret",
            "access_token":    "real_access_token",
            "access_secret":   "real_access_secret",
        })

        r = cred_client.get("/api/accounts")
        x = r.json()["social"]["x"]
        assert x["consumer_key"]    != "real_secret_key"
        assert x["consumer_secret"] != "real_secret_secret"
        assert x["access_token"]    != "real_access_token"
        assert x["access_secret"]   != "real_access_secret"
        # Values should be the mask placeholder
        assert x["consumer_key"] == "••••"
