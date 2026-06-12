"""Tests for social_oauth.py Threads and Tumblr OAuth callback endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def oauth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.setenv("SPACE_HOST", "test.hf.space")
    import importlib
    import api.social_oauth as omod
    importlib.reload(omod)
    app = FastAPI()
    app.include_router(omod.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, omod


class TestThreadsCallback:
    @pytest.mark.asyncio
    async def test_posts_and_saves_connection(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("THREADS_APP_ID", "app123")
        monkeypatch.setenv("THREADS_APP_SECRET", "appsecret")  # pragma: allowlist secret
        monkeypatch.setenv("SPACE_HOST", "test.hf.space")
        import importlib
        import api.social_oauth as omod
        importlib.reload(omod)

        short_token_resp = MagicMock()
        short_token_resp.json.return_value = {"access_token": "short_tok"}  # pragma: allowlist secret

        long_token_resp = MagicMock()
        long_token_resp.status_code = 200
        long_token_resp.json.return_value = {"access_token": "long_tok"}  # pragma: allowlist secret

        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "u123", "username": "threaduser"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=short_token_resp)
            mock_client.get = AsyncMock(side_effect=[long_token_resp, me_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await omod.threads_callback(code="authcode", state="somestate")

        assert result["ok"] is True
        assert result["handle"] == "threaduser"
        conns = omod.load_connections()
        assert conns["threads"]["connected"] is True

    @pytest.mark.asyncio
    async def test_raises_when_no_access_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("SPACE_HOST", "test.hf.space")
        import importlib
        import api.social_oauth as omod
        importlib.reload(omod)

        empty_resp = MagicMock()
        empty_resp.json.return_value = {"error": "Invalid code"}

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=empty_resp)
            with pytest.raises(Exception):
                await omod.threads_callback(code="badcode", state="state")

    @pytest.mark.asyncio
    async def test_falls_back_to_short_lived_when_exchange_fails(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("SPACE_HOST", "test.hf.space")
        import importlib
        import api.social_oauth as omod
        importlib.reload(omod)

        short_token_resp = MagicMock()
        short_token_resp.json.return_value = {"access_token": "short_tok_only"}  # pragma: allowlist secret

        long_fail_resp = MagicMock()
        long_fail_resp.status_code = 400
        long_fail_resp.json.return_value = {}

        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "u999", "username": "shortuser"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=short_token_resp)
            mock_client.get = AsyncMock(side_effect=[long_fail_resp, me_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await omod.threads_callback(code="authcode", state="state")

        assert result["ok"] is True
        assert result["handle"] == "shortuser"


class TestTumblrCallback:
    @pytest.mark.asyncio
    async def test_saves_connection_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("TUMBLR_CLIENT_ID", "tc_id")
        monkeypatch.setenv("TUMBLR_CLIENT_SECRET", "tc_secret")  # pragma: allowlist secret
        monkeypatch.setenv("SPACE_HOST", "test.hf.space")
        import importlib
        import api.social_oauth as omod
        importlib.reload(omod)

        token_resp = MagicMock()
        token_resp.json.return_value = {
            "access_token": "tb_token",  # pragma: allowlist secret
            "refresh_token": "tb_refresh"  # pragma: allowlist secret
        }

        me_resp = MagicMock()
        me_resp.json.return_value = {"response": {"user": {"name": "myblog"}}}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=token_resp)
            mock_client.get = AsyncMock(return_value=me_resp)
            mc.return_value.__aenter__.return_value = mock_client
            result = await omod.tumblr_callback(code="authcode", state="state")

        assert result["ok"] is True
        assert result["handle"] == "myblog"
        conns = omod.load_connections()
        assert conns["tumblr"]["connected"] is True
        assert conns["tumblr"]["handle"] == "myblog"

    @pytest.mark.asyncio
    async def test_raises_when_no_access_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("SPACE_HOST", "test.hf.space")
        import importlib
        import api.social_oauth as omod
        importlib.reload(omod)

        empty_resp = MagicMock()
        empty_resp.json.return_value = {}

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=empty_resp)
            with pytest.raises(Exception):
                await omod.tumblr_callback(code="badcode", state="state")


class TestMastodonCompleteViaCallback:
    def test_mastodon_full_callback_saves_connection(self, oauth_client, tmp_path):
        c, mod = oauth_client
        import time
        state_id = "mstcb_state"
        mod.save_states({state_id: {
            "platform": "mastodon",
            "instance": "https://mastodon.social",
            "client_id": "cid",
            "client_secret": "csec",  # pragma: allowlist secret
            "callback": "https://test.hf.space/api/social/callback?platform=mastodon",
            "ts": time.time()
        }})

        token_resp = MagicMock()
        token_resp.json.return_value = {"access_token": "mst_access_token"}  # pragma: allowlist secret

        me_resp = MagicMock()
        me_resp.json.return_value = {"acct": "testuser@mastodon.social", "username": "testuser"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=token_resp)
            mock_client.get = AsyncMock(return_value=me_resp)
            mc.return_value.__aenter__.return_value = mock_client
            r = c.get(f"/social/callback?platform=mastodon&code=code123&state={state_id}", follow_redirects=False)

        assert r.status_code in (301, 302, 307)
        location = r.headers.get("location", "")
        assert "oauth_ok=mastodon" in location or "testuser" in location

    def test_mastodon_no_token_returns_error_redirect(self, oauth_client, tmp_path):
        c, mod = oauth_client
        import time
        state_id = "mstcb_notoken"
        mod.save_states({state_id: {
            "platform": "mastodon",
            "instance": "https://mastodon.social",
            "client_id": "cid",
            "client_secret": "csec",  # pragma: allowlist secret
            "callback": "https://test.hf.space/api/social/callback?platform=mastodon",
            "ts": time.time()
        }})

        no_token_resp = MagicMock()
        no_token_resp.json.return_value = {"error": "invalid_grant"}

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=no_token_resp)
            r = c.get(f"/social/callback?platform=mastodon&code=bad&state={state_id}", follow_redirects=False)

        # Should redirect (may be ok=False in redirect params or error)
        assert r.status_code in (200, 301, 302, 307)
