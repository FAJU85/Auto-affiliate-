"""Extended social_oauth.py tests — OAuth flow endpoints, credentials store, mastodon/threads/tumblr."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def oauth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("SPACE_HOST", raising=False)
    monkeypatch.setenv("SPACE_HOST", "test.hf.space")
    import importlib
    import api.social_oauth as omod
    importlib.reload(omod)
    app = FastAPI()
    app.include_router(omod.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, omod


@pytest.fixture()
def oauth_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import api.social_oauth as mod
    importlib.reload(mod)
    yield mod


class TestMastodonRegisterEndpoint:
    def test_returns_url_and_state(self, oauth_client, tmp_path):
        c, _ = oauth_client
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "client_id": "cid123",
            "client_secret": "csec456"  # pragma: allowlist secret
        }
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            r = c.post("/social/mastodon/register", json={"instance": "mastodon.social"})
        assert r.status_code == 200
        data = r.json()
        assert "url" in data
        assert "state" in data
        assert "mastodon.social" in data["url"]

    def test_missing_instance_returns_400(self, oauth_client):
        c, _ = oauth_client
        r = c.post("/social/mastodon/register", json={"instance": ""})
        assert r.status_code == 400

    def test_mastodon_registration_failure_returns_502(self, oauth_client):
        c, _ = oauth_client
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server Error"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            r = c.post("/social/mastodon/register", json={"instance": "mastodon.social"})
        assert r.status_code == 502

    def test_strips_username_from_instance_url(self, oauth_client):
        c, _ = oauth_client
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"client_id": "c", "client_secret": "s"}  # pragma: allowlist secret
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            r = c.post("/social/mastodon/register", json={"instance": "https://mastodon.social/@user"})
        assert r.status_code == 200
        data = r.json()
        assert "@user" not in data.get("url", "")


class TestThreadsAuthEndpoint:
    def test_no_threads_app_id_returns_503(self, oauth_client, monkeypatch):
        c, _ = oauth_client
        monkeypatch.delenv("THREADS_APP_ID", raising=False)
        r = c.get("/social/threads/auth")
        assert r.status_code == 503

    def test_with_threads_app_id_returns_url(self, oauth_client, monkeypatch):
        c, _ = oauth_client
        monkeypatch.setenv("THREADS_APP_ID", "my_threads_app")
        r = c.get("/social/threads/auth")
        assert r.status_code == 200
        data = r.json()
        assert "url" in data
        assert "threads.net" in data["url"]


class TestTumblrAuthEndpoint:
    def test_no_tumblr_client_id_returns_503(self, oauth_client, monkeypatch):
        c, _ = oauth_client
        monkeypatch.delenv("TUMBLR_CLIENT_ID", raising=False)
        r = c.get("/social/tumblr/auth")
        assert r.status_code == 503

    def test_with_tumblr_client_id_returns_url(self, oauth_client, monkeypatch):
        c, _ = oauth_client
        monkeypatch.setenv("TUMBLR_CLIENT_ID", "my_tumblr_app")
        r = c.get("/social/tumblr/auth")
        assert r.status_code == 200
        data = r.json()
        assert "url" in data
        assert "tumblr.com" in data["url"]


class TestStoreCredentialsEndpoint:
    def test_saves_x_credentials(self, oauth_client, tmp_path):
        c, mod = oauth_client
        payload = {
            "platform": "x",
            "consumer_key": "ck",
            "consumer_secret": "cs",  # pragma: allowlist secret
            "access_token": "at",  # pragma: allowlist secret
            "access_secret": "asec",  # pragma: allowlist secret
            "handle": "testuser"
        }
        r = c.post("/social/x/credentials", json=payload)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["handle"] == "testuser"
        conns = mod.load_connections()
        assert conns["x"]["consumer_key"] == "ck"

    def test_saves_facebook_credentials(self, oauth_client):
        c, mod = oauth_client
        payload = {
            "platform": "facebook",
            "page_access_token": "pat123",  # pragma: allowlist secret
            "page_id": "pg456",
            "handle": "MyPage"
        }
        r = c.post("/social/facebook/credentials", json=payload)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_saves_instagram_credentials(self, oauth_client):
        c, mod = oauth_client
        payload = {
            "platform": "instagram",
            "access_token": "igtoken",  # pragma: allowlist secret
            "ig_user_id": "ig123",
            "handle": "ighandle"
        }
        r = c.post("/social/instagram/credentials", json=payload)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_missing_handle_returns_400(self, oauth_client):
        c, _ = oauth_client
        r = c.post("/social/x/credentials", json={"platform": "x", "consumer_key": "ck"})
        assert r.status_code == 400

    def test_unknown_platform_returns_404(self, oauth_client):
        c, _ = oauth_client
        r = c.post("/social/fakebook/credentials", json={"handle": "h"})
        assert r.status_code == 404

    def test_oauth_platform_returns_400_for_credentials_endpoint(self, oauth_client):
        c, _ = oauth_client
        r = c.post("/social/mastodon/credentials", json={"handle": "user@mastodon.social"})
        assert r.status_code == 400


class TestOauthCallbackEndpoint:
    def test_missing_code_redirects(self, oauth_client):
        c, _ = oauth_client
        r = c.get("/social/callback?platform=mastodon", follow_redirects=False)
        assert r.status_code in (301, 302, 307)

    def test_error_param_redirects_with_error(self, oauth_client):
        c, _ = oauth_client
        r = c.get("/social/callback?platform=mastodon&error=access_denied", follow_redirects=False)
        assert r.status_code in (301, 302, 307)
        location = r.headers.get("location", "")
        assert "oauth_error" in location

    def test_expired_state_redirects(self, oauth_client):
        c, _ = oauth_client
        r = c.get("/social/callback?platform=mastodon&code=abc&state=no-such-state", follow_redirects=False)
        assert r.status_code in (301, 302, 307)
        location = r.headers.get("location", "")
        assert "expired_state" in location

    def test_unknown_platform_with_valid_state_redirects(self, oauth_client, tmp_path):
        c, mod = oauth_client
        import time
        mod.save_states({"validstate": {"platform": "unknownplatform", "ts": time.time()}})
        r = c.get("/social/callback?platform=unknownplatform&code=abc&state=validstate", follow_redirects=False)
        assert r.status_code in (301, 302, 307)
        location = r.headers.get("location", "")
        assert "oauth_error" in location or "unknown_platform" in location

    def test_mastodon_callback_completes_oauth(self, oauth_client, tmp_path):
        c, mod = oauth_client
        import time
        state_id = "mststate123"
        mod.save_states({state_id: {
            "platform": "mastodon",
            "instance": "https://mastodon.social",
            "client_id": "cid",
            "client_secret": "csec",  # pragma: allowlist secret
            "callback": "https://test.hf.space/oauth/social/callback?platform=mastodon",
            "ts": time.time()
        }})

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "mst_token"}  # pragma: allowlist secret

        me_resp = MagicMock()
        me_resp.json.return_value = {"acct": "testuser@mastodon.social"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=token_resp)
            mock_client.get = AsyncMock(return_value=me_resp)
            mc.return_value.__aenter__.return_value = mock_client
            r = c.get(f"/social/callback?platform=mastodon&code=authcode&state={state_id}", follow_redirects=False)

        assert r.status_code in (301, 302, 307)
        location = r.headers.get("location", "")
        assert "oauth_ok=mastodon" in location or "testuser" in location
