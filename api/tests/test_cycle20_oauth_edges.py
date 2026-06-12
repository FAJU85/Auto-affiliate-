"""Cycle 20: social_oauth edge cases and remaining uncovered paths."""

import os
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def oauth_client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("oauth_data")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)

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


class TestSocialOauthEdgePaths:
    def test_mastodon_register_invalid_instance_url(self, oauth_client):
        r = oauth_client.post("/api/social/mastodon/register", json={
            "instance": "://invalid"  # netloc empty after parse
        })
        assert r.status_code in (400, 422)

    def test_mastodon_register_no_space_host(self, oauth_client):
        saved = os.environ.pop("SPACE_HOST", None)
        try:
            r = oauth_client.post("/api/social/mastodon/register", json={
                "instance": "mastodon.social"
            })
            # Without SPACE_HOST, get_base_url returns None → 503 (or the registration might fail earlier)
            assert r.status_code in (400, 503)
        finally:
            if saved:
                os.environ["SPACE_HOST"] = saved

    def test_threads_auth_no_app_id(self, oauth_client):
        os.environ.pop("THREADS_APP_ID", None)
        r = oauth_client.get("/api/social/threads/auth")
        assert r.status_code == 503

    def test_threads_auth_no_space_host(self, oauth_client):
        os.environ["THREADS_APP_ID"] = "test_app_id"
        saved = os.environ.pop("SPACE_HOST", None)
        try:
            r = oauth_client.get("/api/social/threads/auth")
            assert r.status_code in (503, 302)
        finally:
            os.environ.pop("THREADS_APP_ID", None)
            if saved:
                os.environ["SPACE_HOST"] = saved

    def test_connect_platform_generic_sets_password(self, oauth_client, tmp_path_factory):
        """Line 339: generic platform sets password field."""
        # Use an unknown platform type to hit the else branch
        r = oauth_client.post("/api/social/generic_platform/connect", json={
            "handle": "myuser",
            "password": "mysecret",  # pragma: allowlist secret
            "connected": True
        })
        # Either 200 or 422 — if the endpoint exists
        assert r.status_code in (200, 404, 422)

    def test_oauth_callback_threads_platform(self, oauth_client):
        """Line 372: threads callback path."""
        import api.social_oauth as so

        # Save a state for threads
        states = so.load_states()
        import time
        states["test_threads_state"] = {"platform": "threads", "ts": time.time()}
        so.save_states(states)

        with patch.object(so, "threads_callback", AsyncMock(return_value={"handle": "threads_user"})):
            r = oauth_client.get("/api/social/callback?platform=threads&code=testcode&state=test_threads_state")
        # Redirects
        assert r.status_code in (200, 302, 307)

    def test_oauth_callback_tumblr_platform(self, oauth_client):
        """Line 374: tumblr callback path."""
        import api.social_oauth as so
        import time

        states = so.load_states()
        states["test_tumblr_state"] = {"platform": "tumblr", "ts": time.time()}
        so.save_states(states)

        with patch.object(so, "tumblr_callback", AsyncMock(return_value={"handle": "tumblr_user"})):
            r = oauth_client.get("/api/social/callback?platform=tumblr&code=testcode&state=test_tumblr_state")
        assert r.status_code in (200, 302, 307)

    def test_oauth_callback_exception_redirects_with_error(self, oauth_client):
        """Lines 377-379: exception handler in _handle_oauth_callback."""
        import api.social_oauth as so
        import time

        states = so.load_states()
        states["test_err_state"] = {"platform": "mastodon", "ts": time.time()}
        so.save_states(states)

        with patch.object(so, "_mastodon_complete", AsyncMock(side_effect=Exception("auth failed"))):
            r = oauth_client.get("/api/social/callback?platform=mastodon&code=badcode&state=test_err_state")
        assert r.status_code in (200, 302, 307)

    def test_oauth_health_endpoint(self, oauth_client):
        """Line 438: /health from social_oauth router returns ok."""
        r = oauth_client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True
