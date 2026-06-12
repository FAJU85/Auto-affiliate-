"""End-to-end pipeline execution tests — full _execute path with mocked deps."""

import pytest
from unittest.mock import AsyncMock, patch


PRODUCT = {
    "name": "Sony WH-1000XM5",
    "price": 279.99,
    "currency": "USD",
    "category": "Electronics",
    "siteUrl": "https://amazon.com/sony-wh1000xm5",
    "deeplink": "https://amazon.com/sony-wh1000xm5",
    "imageUrl": None,
    "source": "sovrn",
}


@pytest.fixture(autouse=True)
def reset_state():
    from api import pipeline
    pipeline.STATE["running"] = False
    pipeline.STATE["paused"] = False
    pipeline.STATE["pausedUntil"] = None
    pipeline.STATE["runCount"] = 0
    pipeline.STATE["successCount"] = 0
    pipeline.STATE["lastError"] = None
    yield
    pipeline.STATE["running"] = False
    pipeline.STATE["paused"] = False
    pipeline.STATE["pausedUntil"] = None


class TestExecuteFullPath:
    @pytest.mark.asyncio
    async def test_succeeds_end_to_end_bluesky(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "app-password")
        import importlib
        import api.utils.metrics as m
        import api.utils.budget as b
        importlib.reload(m)
        importlib.reload(b)
        from api import pipeline
        from api.utils import settings as smod
        smod._cache = None

        with patch.object(pipeline, "_get_product", AsyncMock(return_value=PRODUCT)), \
             patch.object(pipeline, "_find_image", AsyncMock(return_value=(None, None))), \
             patch("api.ai.text.generate_post_text", AsyncMock(return_value="Great Sony headphones! Get it now.")), \
             patch("api.pipeline.check_allowed", return_value=(True, "allowed")), \
             patch("api.pipeline.post_to_bluesky", AsyncMock(return_value="at://did:plc:abc/app.bsky.feed.post/123")):
            result = await pipeline.run_pipeline()

        assert result["success"] is True
        assert result["product"] == "Sony WH-1000XM5"
        assert "bluesky" in result["platforms"]

    @pytest.mark.asyncio
    async def test_fails_when_no_product(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "app-password")
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api import pipeline
        from api.utils import settings as smod
        smod._cache = None

        with patch.object(pipeline, "_get_product", AsyncMock(return_value=None)):
            result = await pipeline.run_pipeline()

        assert result["success"] is False
        assert "product" in result["error"].lower() or "network" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fails_when_cost_cap_reached(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        import api.utils.metrics as m
        importlib.reload(b)
        importlib.reload(m)
        from api import pipeline
        from api.utils import settings as smod
        smod._cache = None
        # Set cap to 0.00 so any spend triggers it
        smod._cache = {"dailyCostCap": 0.001, "publishPlatforms": ["bluesky"]}
        b.add_spend(1.0)  # exceed cap

        result = await pipeline.run_pipeline()
        assert result["success"] is False
        assert "cap" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_fails_when_no_platforms_configured(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api import pipeline
        from api.utils import settings as smod
        smod._cache = {"publishPlatforms": [], "dailyCostCap": 10.0}

        result = await pipeline.run_pipeline()
        assert result["success"] is False
        assert "platform" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_skips_bluesky_when_credentials_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.delenv("BSKY_HANDLE", raising=False)
        monkeypatch.delenv("BSKY_APP_PASSWORD", raising=False)
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api import pipeline
        from api.utils import settings as smod
        smod._cache = {
            "publishPlatforms": ["bluesky"],
            "dailyCostCap": 10.0,
            "bskyEnabled": True,
        }
        with patch.object(pipeline, "_get_product", AsyncMock(return_value=PRODUCT)):
            result = await pipeline.run_pipeline()
        # bluesky creds missing → no platform left → fails
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_dedup_skip_already_posted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "app-password")
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api import pipeline
        from api.utils import settings as smod
        smod._cache = {"publishPlatforms": ["bluesky"], "dailyCostCap": 10.0}
        # Mark this product as already posted
        m.mark_posted(PRODUCT["siteUrl"], PRODUCT["name"], "sovrn")

        with patch.object(pipeline, "_get_product", AsyncMock(return_value=PRODUCT)):
            result = await pipeline.run_pipeline()

        assert result["success"] is False
        assert "dedup" in result["error"].lower() or "recently" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_bluesky_rate_limit_pauses_pipeline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("BSKY_HANDLE", "user.bsky.social")
        monkeypatch.setenv("BSKY_APP_PASSWORD", "app-password")
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api import pipeline
        from api.utils import settings as smod
        smod._cache = {"publishPlatforms": ["bluesky"], "dailyCostCap": 10.0}

        with patch.object(pipeline, "_get_product", AsyncMock(return_value=PRODUCT)), \
             patch.object(pipeline, "_find_image", AsyncMock(return_value=(None, None))), \
             patch("api.ai.text.generate_post_text", AsyncMock(return_value="Great deal. Buy now!")), \
             patch("api.pipeline.check_allowed", return_value=(True, "allowed")), \
             patch("api.pipeline.post_to_bluesky",
                   AsyncMock(side_effect=RuntimeError("rate limit 429 too many requests"))):
            await pipeline.run_pipeline()

        # Pipeline should have set paused=True due to rate limit
        assert pipeline.STATE["paused"] is True
        assert pipeline.STATE["pausedUntil"] is not None
