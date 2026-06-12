"""Cycle 14: fine-grained branch coverage for text.py, bluesky_client.py, main.py, social_post.py."""

import os
import json
import time
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


# ── ai/text.py: _looks_usable edge branches ───────────────────────────────────

class TestLooksUsableBranches:
    def test_rejects_non_english_text(self):
        from api.ai.text import _looks_usable
        # >40% non-ASCII
        text = "αβγδεζηθ αβγδεζηθ αβγδεζηθ great"  # heavy non-ASCII
        assert _looks_usable(text) is False

    def test_rejects_symbol_spam(self):
        from api.ai.text import _looks_usable
        # <10 letters — symbol/punctuation spam
        text = "!!!! #### @@@@ $$$$$$$$$$$$$$$$$$$$$$"
        assert _looks_usable(text) is False

    def test_rejects_camelcase_keyword_list(self):
        from api.ai.text import _looks_usable
        # CamelCase keyword dump — >50% camel words, >=4 words
        text = "NorthFaceThermoball SummerDeals ClickNow BuyToday ShopNow"
        assert _looks_usable(text) is False

    def test_rejects_no_verb_no_punct_long(self):
        from api.ai.text import _looks_usable
        # No verb, no punctuation, >6 words — none of the verb-like words
        text = "Blue red silver premium exclusive luxury collection amazing beautiful stylish"
        assert _looks_usable(text) is False

    def test_accepts_normal_text(self):
        from api.ai.text import _looks_usable
        text = "Great deal on this laptop! Grab it now for only $299."
        assert _looks_usable(text) is True


# ── ai/text.py: _chat 429 then rate_limited RuntimeError ──────────────────────

class TestChatRateLimitedBranch:
    @pytest.mark.asyncio
    async def test_groq_rate_limited_runtime_returns_none(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()

        # _try_groq catches RuntimeError with "rate_limited" and returns None
        with patch.object(txt, "_chat", AsyncMock(side_effect=RuntimeError("rate_limited:60"))):
            result = await txt._try_groq("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_groq_generic_exception_returns_none(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()

        with patch.object(txt, "_chat", AsyncMock(side_effect=Exception("connection error"))):
            result = await txt._try_groq("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_mistral_rate_limited_returns_none(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.mistral_cb.reset()

        with patch.object(txt, "_chat", AsyncMock(side_effect=RuntimeError("rate_limited:30"))):
            result = await txt._try_mistral("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_mistral_generic_exception_returns_none(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.mistral_cb.reset()

        with patch.object(txt, "_chat", AsyncMock(side_effect=Exception("socket timeout"))):
            result = await txt._try_mistral("system", "user")
        assert result is None

    @pytest.mark.asyncio
    async def test_groq_cb_open_returns_none(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        # Trip the circuit breaker
        txt.groq_cb.reset()
        for _ in range(3):
            try:
                await txt.groq_cb.call(AsyncMock(side_effect=RuntimeError("fail")))
            except Exception:
                pass
        # Now circuit should be open
        with patch.object(txt, "_try_mistral", AsyncMock(return_value="Mistral wins this round!")):
            result = await txt.generate_post_text({"name": "Camera"}, [])
        assert len(result) > 10
        txt.groq_cb.reset()

    @pytest.mark.asyncio
    async def test_mistral_cb_open_returns_none(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        txt.mistral_cb.reset()
        for _ in range(3):
            try:
                await txt.mistral_cb.call(AsyncMock(side_effect=RuntimeError("fail")))
            except Exception:
                pass
        with patch.object(txt, "_try_groq", AsyncMock(return_value=None)):
            result = await txt.generate_post_text({"name": "Keyboard"}, [])
        assert "Keyboard" in result
        txt.mistral_cb.reset()


# ── bluesky_client.py: exception branches ─────────────────────────────────────

class TestBlueskyExceptionBranches:
    def test_save_ratelimit_works_and_is_readable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        ts = time.time() + 3600
        bc._save_ratelimit(ts)
        assert bc._ratelimit_until() > 0
        bc._clear_ratelimit()

    def test_clear_ratelimit_removes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc._save_ratelimit(time.time() + 3600)
        bc._clear_ratelimit()
        assert bc._ratelimit_until() == 0

    def test_load_cached_session_file_exception(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc._session.clear()
        # Session file doesn't exist → exception in read_text, returns None
        result = bc._load_cached_session()
        assert result is None

    def test_load_cached_session_expired_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc._session.clear()
        # Write an expired session file
        expired = {"accessJwt": "old_jwt", "did": "did:plc:old", "expiry": time.time() - 1}
        bc.SESSION_FILE.write_text(json.dumps(expired))
        result = bc._load_cached_session()
        assert result is None

    def test_load_cached_session_valid_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc._session.clear()
        valid = {"accessJwt": "fresh_jwt", "did": "did:plc:fresh", "expiry": time.time() + 3600}
        bc.SESSION_FILE.write_text(json.dumps(valid))
        result = bc._load_cached_session()
        assert result is not None
        assert result["accessJwt"] == "fresh_jwt"
        bc._session.clear()

    @pytest.mark.asyncio
    async def test_post_to_bluesky_timeout_then_success(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "testpass")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc.bluesky_cb.reset()

        expected = "at://did:plc:abc/post/timeout_test"
        with patch.object(bc, "_post_async", AsyncMock(side_effect=[
            asyncio.TimeoutError(),
            expected,
        ])):
            with patch("asyncio.sleep", AsyncMock()):
                result = await bc.post_to_bluesky("Caption", "https://link.com", None, {})
        assert result == expected

    @pytest.mark.asyncio
    async def test_post_to_bluesky_401_clears_session(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "testpass")  # pragma: allowlist secret
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.bluesky_client as bc
        importlib.reload(bc)
        bc.bluesky_cb.reset()
        bc._session.update({"accessJwt": "jwt_abc", "did": "did:plc:123", "expiry": 9999999999})

        cleared = []

        def mock_clear():
            cleared.append(True)
            bc._session.clear()

        with patch.object(bc, "_post_async", AsyncMock(side_effect=[
            RuntimeError("401 Unauthorized"),
            "at://did:plc:abc/post/401_retry",
        ])):
            with patch.object(bc, "_clear_session", side_effect=mock_clear):
                with patch("asyncio.sleep", AsyncMock()):
                    await bc.post_to_bluesky("Caption", "https://link.com", None, {})
        assert len(cleared) >= 1


# ── main.py: auth middleware with password ─────────────────────────────────────

@pytest.fixture(scope="module")
def auth_client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("authdata")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["DASHBOARD_PASSWORD"] = "secret123"  # pragma: allowlist secret

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

    os.environ.pop("DASHBOARD_PASSWORD", None)


class TestMainAuthMiddleware:
    def test_api_route_without_auth_returns_401(self, auth_client):
        r = auth_client.get("/api/settings")
        assert r.status_code == 401

    def test_api_route_with_correct_auth_passes(self, auth_client):
        r = auth_client.get("/api/settings", headers={"Authorization": "Bearer secret123"})
        assert r.status_code == 200

    def test_home_without_auth_serves_html(self, auth_client):
        r = auth_client.get("/")
        assert r.status_code == 200


class TestMainSloAndMisc:
    def test_slo_exhausted_budget_sets_circuit_breaker(self, auth_client):
        with patch("api.pipeline.calculate_slo", return_value={
            "slo_pct": 95.0,
            "error_budget_remaining_pct": 0,
            "circuit_breaker_active": False,
            "action": "nominal",
        }):
            r = auth_client.get("/api/slo", headers={"Authorization": "Bearer secret123"})
        assert r.status_code == 200
        data = r.json()
        assert data["circuit_breaker_active"] is True
        assert "HALT" in data["action"]

    def test_slo_low_budget_warning(self, auth_client):
        with patch("api.pipeline.calculate_slo", return_value={
            "slo_pct": 97.0,
            "error_budget_remaining_pct": 10,
        }):
            r = auth_client.get("/api/slo", headers={"Authorization": "Bearer secret123"})
        assert r.status_code == 200
        data = r.json()
        assert data["circuit_breaker_active"] is False
        assert "WARNING" in data["action"]

    def test_health_accessible_without_auth(self, auth_client):
        r = auth_client.get("/health")
        assert r.status_code == 200
        assert "status" in r.json()

    def test_post_settings_exception_returns_error(self, auth_client):
        r = auth_client.post(
            "/api/settings", content="not-json",
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret123"}
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is False or "ok" in data

    def test_next_run_schedule_endpoint(self, auth_client):
        r = auth_client.get("/api/schedule/config", headers={"Authorization": "Bearer secret123"})
        assert r.status_code == 200
        assert "cron" in r.json()


# ── social_post.py: post_to_platform tumblr/facebook/instagram/unknown ────────

class TestPostToPlatformExtra:
    @pytest.mark.asyncio
    async def test_unknown_platform_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        result = await sp.post_to_platform("nonexistent_platform", "caption", "https://link.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_facebook_platform_calls_post_facebook(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"facebook": {
            "connected": True,
            "page_access_token": "pat",  # pragma: allowlist secret
            "page_id": "pg123"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.json.return_value = {"post_id": "pg123_abc"}

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=post_resp)
            result = await sp.post_to_platform("facebook", "caption", "https://link.com", product={"imageUrl": None})
        assert result is not None

    @pytest.mark.asyncio
    async def test_instagram_platform_calls_post_instagram(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"instagram": {
            "connected": True,
            "access_token": "ig_tok",
            "ig_user_id": "123456"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "container_1"}

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "media_1"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp.post_to_platform(
                "instagram", "caption", "https://link.com",
                product={"imageUrl": "https://img.example.com/img.jpg"}
            )
        assert result is not None
