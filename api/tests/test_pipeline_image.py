"""Tests for pipeline image fetch paths (Amazon og:image, _find_image fallback)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestFetchAmazonOgImage:
    @pytest.mark.asyncio
    async def test_returns_image_bytes_when_og_tag_found(self):
        from api.pipeline import _fetch_amazon_og_image
        html = '<meta property="og:image" content="https://images.amazon.com/img.jpg">'
        page_resp = MagicMock()
        page_resp.status_code = 200
        page_resp.text = html

        img_resp = MagicMock()
        img_resp.status_code = 200
        img_resp.headers = {"content-type": "image/jpeg"}
        img_resp.content = b"fakeimagedata"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=[page_resp, img_resp]
            )
            result = await _fetch_amazon_og_image("https://amazon.com/dp/B123")
        assert result == b"fakeimagedata"

    @pytest.mark.asyncio
    async def test_returns_none_when_page_not_200(self):
        from api.pipeline import _fetch_amazon_og_image
        page_resp = MagicMock()
        page_resp.status_code = 404

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(return_value=page_resp)
            result = await _fetch_amazon_og_image("https://amazon.com/dp/B123")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_og_tag(self):
        from api.pipeline import _fetch_amazon_og_image
        page_resp = MagicMock()
        page_resp.status_code = 200
        page_resp.text = "<html><body>No image here</body></html>"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(return_value=page_resp)
            result = await _fetch_amazon_og_image("https://amazon.com/dp/B123")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        from api.pipeline import _fetch_amazon_og_image
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("timeout"))
            result = await _fetch_amazon_og_image("https://amazon.com/dp/B123")
        assert result is None

    @pytest.mark.asyncio
    async def test_falls_back_to_media_amazon_pattern(self):
        from api.pipeline import _fetch_amazon_og_image
        # og:image not present, but media-amazon.com URL is
        html = 'content="https://m.media-amazon.com/images/I/abc.jpg"'
        page_resp = MagicMock()
        page_resp.status_code = 200
        page_resp.text = html

        img_resp = MagicMock()
        img_resp.status_code = 200
        img_resp.headers = {"content-type": "image/jpeg"}
        img_resp.content = b"amazonimage"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=[page_resp, img_resp]
            )
            result = await _fetch_amazon_og_image("https://amazon.com/dp/B123")
        assert result == b"amazonimage"

    @pytest.mark.asyncio
    async def test_returns_none_when_image_not_image_content_type(self):
        from api.pipeline import _fetch_amazon_og_image
        html = '<meta property="og:image" content="https://images.amazon.com/img.jpg">'
        page_resp = MagicMock()
        page_resp.status_code = 200
        page_resp.text = html

        img_resp = MagicMock()
        img_resp.status_code = 200
        img_resp.headers = {"content-type": "text/html"}
        img_resp.content = b"notanimage"

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=[page_resp, img_resp]
            )
            result = await _fetch_amazon_og_image("https://amazon.com/dp/B123")
        assert result is None


class TestFindImageAmazonFallback:
    @pytest.mark.asyncio
    async def test_tries_amazon_og_when_no_image_url(self):
        from api import pipeline
        amazon_product = {
            "siteUrl": "https://amazon.com/dp/B123",
            "deeplink": "https://amazon.com/dp/B123",
        }
        with patch.object(pipeline, "_fetch_amazon_og_image", AsyncMock(return_value=b"ogimg")):
            result = await pipeline._find_image(amazon_product)
        assert result == b"ogimg"

    @pytest.mark.asyncio
    async def test_returns_none_when_amazon_scrape_fails(self):
        from api import pipeline
        amazon_product = {"siteUrl": "https://amazon.com/dp/B456"}
        with patch.object(pipeline, "_fetch_amazon_og_image", AsyncMock(side_effect=Exception("scrape failed"))):
            result = await pipeline._find_image(amazon_product)
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_amazon_for_non_amazon_url(self):
        from api import pipeline
        non_amazon = {"siteUrl": "https://example.com/product", "imageUrl": None}
        with patch.object(pipeline, "_fetch_amazon_og_image", AsyncMock()) as mock_scrape:
            await pipeline._find_image(non_amazon)
        mock_scrape.assert_not_called()


class TestResolveRedirectFromMetrics:
    def test_resolves_from_run_history(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api import pipeline
        from datetime import datetime, timezone
        m.record_run({
            "success": True,
            "trackingId": "abc12345",
            "deeplink": "https://example.com/from-history",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        pipeline._REDIRECTS.clear()
        result = pipeline.resolve_redirect("abc12345")
        assert result == "https://example.com/from-history"
