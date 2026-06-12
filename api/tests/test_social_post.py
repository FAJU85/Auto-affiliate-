"""Unit tests for social_post.py — OAuth signing and platform routing."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json


# ── OAuth 1.0a signing ───────────────────────────────────────────────────────

class TestPctEncode:
    def test_encodes_reserved_chars(self):
        from api.social_post import _pct
        assert _pct("hello world") == "hello%20world"
        assert _pct("a=b&c=d") == "a%3Db%26c%3Dd"

    def test_leaves_unreserved_unchanged(self):
        from api.social_post import _pct
        assert _pct("hello123") == "hello123"


class TestOauth1Sign:
    def test_returns_base64_string(self):
        from api.social_post import _oauth1_sign
        sig = _oauth1_sign("POST", "https://example.com", {"key": "val"},
                           "consumer_secret", "token_secret")
        assert isinstance(sig, str)
        assert len(sig) > 10

    def test_deterministic_for_same_params(self):
        from api.social_post import _oauth1_sign
        sig1 = _oauth1_sign("GET", "https://api.example.com/v1",
                            {"oauth_nonce": "abc", "oauth_timestamp": "1234567890"},
                            "csec", "tsec")
        sig2 = _oauth1_sign("GET", "https://api.example.com/v1",
                            {"oauth_nonce": "abc", "oauth_timestamp": "1234567890"},
                            "csec", "tsec")
        assert sig1 == sig2

    def test_different_secrets_produce_different_sigs(self):
        from api.social_post import _oauth1_sign
        params = {"oauth_nonce": "x", "oauth_timestamp": "1000"}
        s1 = _oauth1_sign("POST", "https://api.com", params, "secret1", "tsec")
        s2 = _oauth1_sign("POST", "https://api.com", params, "secret2", "tsec")
        assert s1 != s2


class TestOauth1Header:
    def test_returns_oauth_prefix(self):
        from api.social_post import _oauth1_header
        h = _oauth1_header("POST", "https://api.twitter.com/2/tweets",
                           "ckey", "csecret", "atoken", "asecret")
        assert h.startswith("OAuth ")

    def test_contains_required_fields(self):
        from api.social_post import _oauth1_header
        h = _oauth1_header("POST", "https://api.twitter.com/2/tweets",
                           "ckey", "csecret", "atoken", "asecret")
        assert "oauth_consumer_key" in h
        assert "oauth_signature" in h
        assert "oauth_timestamp" in h
        assert "oauth_nonce" in h


# ── Hashtag picking ──────────────────────────────────────────────────────────

class TestPickHashtags:
    def test_electronics_gets_tech_tags(self):
        from api.social_post import _pick_hashtags
        tags = _pick_hashtags({"category": "electronics", "name": "Laptop"})
        assert any("tech" in t.lower() or "electronics" in t.lower() for t in tags)

    def test_beauty_gets_beauty_tags(self):
        from api.social_post import _pick_hashtags
        tags = _pick_hashtags({"category": "beauty", "name": "Serum"})
        assert any("beauty" in t.lower() or "selfcare" in t.lower() for t in tags)

    def test_unknown_category_returns_fallback(self):
        from api.social_post import _pick_hashtags
        tags = _pick_hashtags({"category": "unknown_xyz", "name": "Mystery Item"})
        assert tags == ["#deals", "#shopping"]

    def test_fitness_gets_fitness_tags(self):
        from api.social_post import _pick_hashtags
        tags = _pick_hashtags({"category": "fitness", "name": "Yoga Mat"})
        assert any("fitness" in t.lower() for t in tags)


# ── Connection loading ───────────────────────────────────────────────────────

class TestLoadConnections:
    def test_returns_empty_dict_on_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        # Reload to pick up new DATA_DIR
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        result = sp._load_connections()
        assert isinstance(result, dict)

    def test_loads_valid_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"mastodon": {"connected": True}}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        result = sp._load_connections()
        assert result.get("mastodon", {}).get("connected") is True


# ── Platform posting — credential guards ─────────────────────────────────────

class TestPostMastodon:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="not connected"):
            await sp._post_mastodon("caption", "https://link.example.com")

    @pytest.mark.asyncio
    async def test_posts_successfully_on_201(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "mastodon": {
                "connected": True,
                "access_token": "fake-token",
                "instance": "https://mastodon.social"
            }
        }))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"url": "https://mastodon.social/@user/12345"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await sp._post_mastodon("Great deal!", "https://link.example.com")
        assert "mastodon.social" in result

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({
            "mastodon": {"connected": True, "access_token": "t", "instance": "https://mastodon.social"}
        }))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = "Unprocessable Entity"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(RuntimeError, match="HTTP 422"):
                await sp._post_mastodon("caption", "https://link.example.com")


class TestPostX:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="not connected"):
            await sp._post_x("caption", "https://link.example.com")

    @pytest.mark.asyncio
    async def test_raises_on_403(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"x": {
            "connected": True,
            "consumer_key": "ck", "consumer_secret": "cs",  # pragma: allowlist secret
            "access_token": "at", "access_secret": "as", "handle": "testuser"  # pragma: allowlist secret
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            with pytest.raises(RuntimeError, match="Read and Write"):
                await sp._post_x("caption", "https://link.example.com")

    @pytest.mark.asyncio
    async def test_posts_successfully(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"x": {
            "connected": True,
            "consumer_key": "ck", "consumer_secret": "cs",  # pragma: allowlist secret
            "access_token": "at", "access_secret": "as", "handle": "testuser"  # pragma: allowlist secret
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"data": {"id": "1234567890"}}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await sp._post_x("Great deal!", "https://link.example.com")
        assert "twitter.com" in result


class TestPostFacebook:
    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="not connected"):
            await sp._post_facebook("caption", "https://link.example.com")

    @pytest.mark.asyncio
    async def test_posts_successfully_without_image(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"facebook": {
            "connected": True, "page_access_token": "pat", "page_id": "pg123"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "pg123_post456"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = await sp._post_facebook("caption", "https://link.example.com")
        assert "facebook.com" in result


class TestPostInstagram:
    @pytest.mark.asyncio
    async def test_raises_when_no_image_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"instagram": {
            "connected": True, "access_token": "t", "ig_user_id": "123"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="image URL"):
            await sp._post_instagram("caption", "https://link.example.com", image_url=None)

    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with pytest.raises(RuntimeError, match="not connected"):
            await sp._post_instagram("caption", "https://link.example.com")


# ── post_to_platform dispatcher ──────────────────────────────────────────────

class TestPostToPlatform:
    @pytest.mark.asyncio
    async def test_mastodon_dispatched(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with patch.object(sp, "_post_mastodon", AsyncMock(return_value="https://mastodon.social/uri")) as mock_fn:
            result = await sp.post_to_platform("mastodon", "caption", "https://link.com")
        mock_fn.assert_called_once()
        assert result == "https://mastodon.social/uri"

    @pytest.mark.asyncio
    async def test_unknown_platform_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        result = await sp.post_to_platform("fakebook", "caption", "https://link.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_platform_error_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)
        with patch.object(sp, "_post_x", AsyncMock(side_effect=RuntimeError("creds missing"))):
            result = await sp.post_to_platform("x", "caption", "https://link.com")
        assert result is None
