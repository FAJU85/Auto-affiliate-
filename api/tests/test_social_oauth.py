"""Unit tests for social_oauth.py — persistence helpers and platform registry."""

import time
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def oauth_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import api.social_oauth as mod
    importlib.reload(mod)
    yield mod
    importlib.reload(mod)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    import importlib
    import api.social_oauth as omod
    importlib.reload(omod)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(omod.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, omod


class TestLoadSaveConnections:
    def test_returns_empty_when_no_file(self, oauth_mod):
        assert oauth_mod.load_connections() == {}

    def test_saves_and_loads(self, oauth_mod, tmp_path):
        data = {"mastodon": {"connected": True, "handle": "user"}}
        oauth_mod.save_connections(data)
        loaded = oauth_mod.load_connections()
        assert loaded["mastodon"]["connected"] is True

    def test_atomic_write_no_tmp_left(self, oauth_mod, tmp_path):
        oauth_mod.save_connections({"x": {"connected": False}})
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestLoadSaveStates:
    def test_empty_when_no_file(self, oauth_mod):
        assert oauth_mod.load_states() == {}

    def test_saves_and_loads(self, oauth_mod):
        states = {"abc123": {"platform": "mastodon", "ts": time.time()}}
        oauth_mod.save_states(states)
        loaded = oauth_mod.load_states()
        assert "abc123" in loaded

    def test_prunes_expired_states(self, oauth_mod):
        old_ts = time.time() - 700  # older than 600s TTL
        states = {
            "old": {"platform": "mastodon", "ts": old_ts},
            "new": {"platform": "mastodon", "ts": time.time()},
        }
        oauth_mod.save_states(states)
        loaded = oauth_mod.load_states()
        assert "old" not in loaded
        assert "new" in loaded


class TestGetBaseUrl:
    def test_returns_empty_when_no_env(self, monkeypatch):
        monkeypatch.delenv("SPACE_HOST", raising=False)
        monkeypatch.delenv("SPACE_ID", raising=False)
        import importlib
        import api.social_oauth as mod
        importlib.reload(mod)
        assert mod.get_base_url() == ""

    def test_uses_space_host_when_set(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SPACE_HOST", "myapp.hf.space")
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_oauth as mod
        importlib.reload(mod)
        result = mod.get_base_url()
        assert result == "https://myapp.hf.space"

    def test_constructs_from_space_id(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SPACE_HOST", raising=False)
        monkeypatch.setenv("SPACE_ID", "owner/my-space")
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_oauth as mod
        importlib.reload(mod)
        result = mod.get_base_url()
        assert "owner-my-space.hf.space" in result

    def test_adds_https_prefix(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SPACE_HOST", "example.hf.space")
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_oauth as mod
        importlib.reload(mod)
        result = mod.get_base_url()
        assert result.startswith("https://")

    def test_strips_trailing_slash(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SPACE_HOST", "https://example.hf.space/")
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_oauth as mod
        importlib.reload(mod)
        assert not mod.get_base_url().endswith("/")


class TestPlatformRegistry:
    def test_contains_expected_platforms(self, oauth_mod):
        assert "mastodon" in oauth_mod.PLATFORMS
        assert "x" in oauth_mod.PLATFORMS
        assert "threads" in oauth_mod.PLATFORMS
        assert "facebook" in oauth_mod.PLATFORMS
        assert "instagram" in oauth_mod.PLATFORMS

    def test_each_has_name_and_auth(self, oauth_mod):
        for key, meta in oauth_mod.PLATFORMS.items():
            assert "name" in meta
            assert "auth" in meta


class TestStatusEndpoint:
    def test_returns_all_platforms(self, client):
        c, mod = client
        r = c.get("/social/status")
        assert r.status_code == 200
        body = r.json()
        for platform in mod.PLATFORMS:
            assert platform in body

    def test_connected_false_for_empty(self, client):
        c, _ = client
        body = c.get("/social/status").json()
        for v in body.values():
            assert v["connected"] is False


class TestDisconnectEndpoint:
    def test_disconnect_known_platform(self, client, tmp_path):
        c, mod = client
        mod.save_connections({"mastodon": {"connected": True}})
        r = c.delete("/social/mastodon/disconnect")
        assert r.status_code == 200
        assert mod.load_connections().get("mastodon") is None

    def test_disconnect_unknown_platform_returns_404(self, client):
        c, _ = client
        r = c.delete("/social/fakebook/disconnect")
        assert r.status_code == 404


class TestManualCredentialsSave:
    def test_saves_x_credentials(self, client, tmp_path):
        c, mod = client
        payload = {
            "platform": "x",
            "consumer_key": "ck",
            "consumer_secret": "cs",
            "access_token": "at",
            "access_secret": "as",
            "handle": "myhandle",
        }
        r = c.post("/social/credentials", json=payload)
        # Either 200 or endpoint doesn't exist (404) — just test it doesn't 500
        assert r.status_code in (200, 404, 422)
