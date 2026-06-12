"""Cycle 13: fill remaining gaps in main.py, pipeline.py, social_post.py, bluesky_client.py, metrics.py."""

import os
import json
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


# ── main.py: health endpoint degraded/misconfigured paths ─────────────────────

@pytest.fixture(scope="module")
def main_client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)
    os.environ.pop("BSKY_HANDLE", None)
    os.environ.pop("BSKY_APP_PASSWORD", None)
    os.environ.pop("SOVRN_API_KEY", None)

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


class TestMainEndpointsExtra:
    def test_health_returns_status(self, main_client):
        r = main_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "ok" in data
        assert "status" in data

    def test_debug_endpoint(self, main_client):
        r = main_client.get("/api/debug")
        assert r.status_code == 200
        data = r.json()
        assert "env" in data
        assert "lastRun" in data

    def test_env_endpoint(self, main_client):
        r = main_client.get("/api/env")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_metrics_endpoint(self, main_client):
        r = main_client.get("/api/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "golden_signals" in data
        assert "circuit_breakers" in data

    def test_dry_run_endpoint(self, main_client):
        r = main_client.post("/api/dry-run")
        assert r.status_code == 200

    def test_stats_endpoint(self, main_client):
        r = main_client.get("/api/stats")
        assert r.status_code == 200

    def test_home_serves_html(self, main_client):
        r = main_client.get("/")
        assert r.status_code == 200

    def test_settings_with_cron_reschedules(self, main_client):
        r = main_client.post("/api/settings", json={"cronSchedule": "0 * * * *", "dailyCostCap": 2.0})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_oauth_callback_no_handler(self, main_client):
        # Mastodon /oauth/social/callback route exists
        r = main_client.get("/oauth/social/callback?platform=mastodon")
        # Either handled or 503 — just confirm it doesn't 404
        assert r.status_code != 404

    def test_bluesky_test_cooldown(self, main_client):
        import api.main as m
        m._last_bsky_test = time.time()  # just set it
        os.environ["BSKY_HANDLE"] = "user.bsky.social"
        os.environ["BSKY_APP_PASSWORD"] = "testpass"  # pragma: allowlist secret
        try:
            r = main_client.post("/api/accounts/bluesky/test")
            assert r.status_code == 200
            data = r.json()
            # Either cooldown or real attempt — both are valid
            assert "ok" in data
        finally:
            os.environ.pop("BSKY_HANDLE", None)
            os.environ.pop("BSKY_APP_PASSWORD", None)
            m._last_bsky_test = 0.0


# ── pipeline.py: bluesky disabled + creds missing fallthrough ─────────────────

class TestPipelineFallthrough:
    @pytest.mark.asyncio
    async def test_bluesky_disabled_falls_to_other_platforms(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "testpass")  # pragma: allowlist secret
        import importlib
        import api.utils.settings as smod
        import api.utils.metrics as mmod
        import api.utils.budget as bmod
        smod._cache = None
        importlib.reload(smod)
        importlib.reload(mmod)
        importlib.reload(bmod)
        import api.pipeline as pipeline
        importlib.reload(pipeline)

        # bluesky + mastodon, but bluesky disabled
        smod.save_settings({"publishPlatforms": ["bluesky", "mastodon"], "bskyEnabled": False, "dailyCostCap": 5.0})

        product = {
            "id": "prod-fallthrough",
            "name": "Test Widget",
            "source": "sovrn",
            "siteUrl": "https://example.com/p",
            "deeplink": "https://example.com/p",
        }

        with patch.object(pipeline, "_get_product", AsyncMock(return_value=product)):
            with patch("api.utils.metrics.was_posted_within", return_value=False):
                with patch("api.ai.text.generate_post_text", AsyncMock(return_value="Great deal!")):
                    with patch.object(pipeline, "_find_image", AsyncMock(return_value=None)):
                        with patch.object(pipeline, "check_allowed", return_value=(True, "allowed")):
                            with patch.object(pipeline, "post_to_platform", AsyncMock(return_value="https://mastodon.social/@u/1")):
                                result = await pipeline.run_pipeline()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_bluesky_creds_missing_falls_to_other(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.delenv("BSKY_HANDLE", raising=False)
        monkeypatch.delenv("BSKY_APP_PASSWORD", raising=False)
        import importlib
        import api.utils.settings as smod
        import api.utils.metrics as mmod
        import api.utils.budget as bmod
        smod._cache = None
        importlib.reload(smod)
        importlib.reload(mmod)
        importlib.reload(bmod)
        import api.pipeline as pipeline
        importlib.reload(pipeline)

        smod.save_settings({"publishPlatforms": ["bluesky", "mastodon"], "bskyEnabled": True, "dailyCostCap": 5.0})

        product = {
            "id": "prod-nocreds",
            "name": "Widget",
            "source": "sovrn",
            "siteUrl": "https://example.com/w",
            "deeplink": "https://example.com/w",
        }

        with patch.object(pipeline, "_get_product", AsyncMock(return_value=product)):
            with patch("api.utils.metrics.was_posted_within", return_value=False):
                with patch("api.ai.text.generate_post_text", AsyncMock(return_value="Amazing!")):
                    with patch.object(pipeline, "_find_image", AsyncMock(return_value=None)):
                        with patch.object(pipeline, "check_allowed", return_value=(True, "allowed")):
                            with patch.object(pipeline, "post_to_platform", AsyncMock(return_value="https://mastodon.social/@u/2")):
                                result = await pipeline.run_pipeline()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_no_product_returns_error(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as smod
        import api.utils.metrics as mmod
        import api.utils.budget as bmod
        smod._cache = None
        importlib.reload(smod)
        importlib.reload(mmod)
        importlib.reload(bmod)
        import api.pipeline as pipeline
        importlib.reload(pipeline)

        smod.save_settings({"publishPlatforms": ["mastodon"], "dailyCostCap": 5.0})

        with patch.object(pipeline, "_get_product", AsyncMock(return_value=None)):
            result = await pipeline.run_pipeline()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_guardian_skip_all_platforms(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as smod
        import api.utils.metrics as mmod
        import api.utils.budget as bmod
        smod._cache = None
        importlib.reload(smod)
        importlib.reload(mmod)
        importlib.reload(bmod)
        import api.pipeline as pipeline
        importlib.reload(pipeline)

        smod.save_settings({"publishPlatforms": ["mastodon"], "dailyCostCap": 5.0})

        product = {
            "id": "prod-guardian",
            "name": "Gadget",
            "source": "sovrn",
            "siteUrl": "https://example.com/g",
            "deeplink": "https://example.com/g",
        }

        with patch.object(pipeline, "_get_product", AsyncMock(return_value=product)):
            with patch("api.utils.metrics.was_posted_within", return_value=False):
                with patch("api.ai.text.generate_post_text", AsyncMock(return_value="Hot deal!")):
                    with patch.object(pipeline, "_find_image", AsyncMock(return_value=None)):
                        with patch.object(pipeline, "check_allowed", return_value=(False, "outside posting hours")):
                            result = await pipeline.run_pipeline()
        assert result["success"] is False


# ── social_post.py: X 403, Instagram full path, Threads ─────────────────────

class TestPostXExtra:
    @pytest.mark.asyncio
    async def test_raises_on_403(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"x": {
            "connected": True,
            "consumer_key": "ck", "consumer_secret": "cs",  # pragma: allowlist secret
            "access_token": "at", "access_secret": "as", "handle": "user"  # pragma: allowlist secret
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        resp_403 = MagicMock()
        resp_403.status_code = 403
        resp_403.text = "Forbidden"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp_403)
            with pytest.raises(RuntimeError, match="403"):
                await sp._post_x("Caption", "https://link.com")

    @pytest.mark.asyncio
    async def test_raises_on_non_200_201(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"x": {
            "connected": True,
            "consumer_key": "ck", "consumer_secret": "cs",  # pragma: allowlist secret
            "access_token": "at", "access_secret": "as", "handle": "user"  # pragma: allowlist secret
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.text = "Server Error"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp_500)
            with pytest.raises(RuntimeError, match="500"):
                await sp._post_x("Caption", "https://link.com")


class TestPostInstagram:
    @pytest.mark.asyncio
    async def test_raises_when_no_image_url(self, tmp_path, monkeypatch):
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

        with pytest.raises(RuntimeError, match="image URL"):
            await sp._post_instagram("Caption", "https://link.com", image_url=None)

    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        with pytest.raises(RuntimeError, match="not connected"):
            await sp._post_instagram("Caption", "https://link.com", image_url="https://img.example.com/img.jpg")

    @pytest.mark.asyncio
    async def test_raises_on_container_failure(self, tmp_path, monkeypatch):
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

        fail_resp = MagicMock()
        fail_resp.status_code = 400
        fail_resp.text = "Bad Request"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=fail_resp)
            with pytest.raises(RuntimeError, match="container"):
                await sp._post_instagram("Caption", "https://link.com", image_url="https://img.example.com/img.jpg")

    @pytest.mark.asyncio
    async def test_success_path(self, tmp_path, monkeypatch):
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
        container_resp.json.return_value = {"id": "container_abc"}

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "media_xyz"}

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp._post_instagram("Caption", "https://link.com", image_url="https://img.example.com/img.jpg")
        assert "instagram.com" in result


# ── bluesky_client.py: grapheme helpers and _build_post_text ──────────────────

class TestBlueskyHelpers:
    def test_grapheme_len_ascii(self):
        import api.bluesky_client as bc
        assert bc._grapheme_len("hello") == 5

    def test_grapheme_len_emoji(self):
        import api.bluesky_client as bc
        # Emoji counts as 1 grapheme cluster
        result = bc._grapheme_len("hi 🎉")
        assert result >= 4  # 'h', 'i', ' ', emoji

    def test_truncate_graphemes_short(self):
        import api.bluesky_client as bc
        text = "short"
        assert bc._truncate_graphemes(text, 300) == text

    def test_truncate_graphemes_truncates(self):
        import api.bluesky_client as bc
        text = "A" * 400
        result = bc._truncate_graphemes(text, 100)
        assert len(result) == 100

    def test_build_post_text_fits(self):
        import api.bluesky_client as bc
        caption = "Great product!"
        deeplink = "https://example.com/p"
        result = bc._build_post_text(caption, deeplink)
        assert deeplink in result
        assert "Great product!" in result

    def test_build_post_text_long_caption_truncated(self):
        import api.bluesky_client as bc
        caption = "A" * 400
        deeplink = "https://example.com/p"
        result = bc._build_post_text(caption, deeplink)
        assert deeplink in result
        # Total should not exceed limit
        assert len(result) < 500


# ── metrics.py: was_posted_within malformed ts, mark_posted eviction ─────────

class TestMetricsExtra:
    def test_was_posted_within_malformed_ts(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)

        # Inject a malformed timestamp into the store
        data = {"posted": {"test_key": {"ts": "not-a-date", "source": "sovrn"}}}
        (tmp_path / "metrics.json").write_text(json.dumps(data))

        # Should return False (malformed ts → allow re-post)
        result = m.was_posted_within("https://example.com", "Test", hours=24)
        assert result is False

    def test_mark_posted_evicts_old(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)

        # Fill beyond _MAX_POSTED limit
        for i in range(m._MAX_POSTED + 5):
            m.mark_posted(f"https://example.com/{i}", f"Product {i}", "sovrn")

        data_file = tmp_path / "metrics.json"
        data = json.loads(data_file.read_text())
        assert len(data.get("posted", {})) <= m._MAX_POSTED

    def test_get_dedup_status_counts_active(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)

        m.mark_posted("https://example.com/active", "Active Product", "sovrn")
        status = m.get_dedup_status()
        assert "count" in status
        assert "activeCount" in status
        assert status["activeCount"] >= 1


# ── pipeline.py: _find_image amazon fallback path ────────────────────────────

class TestPipelineFindImage:
    @pytest.mark.asyncio
    async def test_amazon_image_fallback(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.pipeline as pipeline
        importlib.reload(pipeline)

        amazon_product = {
            "name": "Amazon Widget",
            "siteUrl": "https://www.amazon.com/dp/B0001234",
            "deeplink": "https://www.amazon.com/dp/B0001234",
        }

        with patch.object(pipeline, "_fetch_amazon_og_image", AsyncMock(return_value=b"fakeimgbytes")):
            result = await pipeline._find_image(amazon_product)
        assert result == b"fakeimgbytes"

    @pytest.mark.asyncio
    async def test_amazon_image_fallback_exception(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.pipeline as pipeline
        importlib.reload(pipeline)

        amazon_product = {
            "name": "Amazon Widget",
            "siteUrl": "https://www.amazon.com/dp/B0001234",
        }

        with patch.object(pipeline, "_fetch_amazon_og_image", AsyncMock(side_effect=Exception("scrape failed"))):
            result = await pipeline._find_image(amazon_product)
        assert result is None
