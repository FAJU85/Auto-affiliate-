"""Unit tests for SOVRN feed module (feeds/sovrn.py)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestPickProduct:
    def test_returns_a_dict(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api.feeds.sovrn import _pick_product
        result = _pick_product()
        assert isinstance(result, dict)
        assert "name" in result
        assert "url" in result

    def test_skips_recently_posted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api.feeds import sovrn as smod
        from api.feeds.sovrn import PRODUCT_POOL
        # Mark all but last product as posted
        for p in PRODUCT_POOL[:-1]:
            m.mark_posted(p["url"], p["name"], "sovrn")
        result = smod._pick_product()
        assert result is not None  # falls back when all posted


class TestMonetizeUrl:
    @pytest.mark.asyncio
    async def test_returns_original_when_no_key(self, monkeypatch):
        monkeypatch.delenv("SOVRN_API_KEY", raising=False)
        from api.feeds.sovrn import monetize_url
        result = await monetize_url("https://example.com/product")
        assert result == "https://example.com/product"

    @pytest.mark.asyncio
    async def test_returns_original_when_empty_url(self, monkeypatch):
        monkeypatch.setenv("SOVRN_API_KEY", "fake-key")
        from api.feeds.sovrn import monetize_url
        result = await monetize_url("")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_monetized_url_on_success(self, monkeypatch):
        monkeypatch.setenv("SOVRN_API_KEY", "fake-key")
        from api.feeds.sovrn import monetize_url
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"url": "https://viglink.com/monetized?out=example.com"}
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            result = await monetize_url("https://example.com/product")
        assert "viglink" in result or "monetized" in result

    @pytest.mark.asyncio
    async def test_returns_original_on_non_200(self, monkeypatch):
        monkeypatch.setenv("SOVRN_API_KEY", "fake-key")
        from api.feeds.sovrn import monetize_url
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            result = await monetize_url("https://example.com/product")
        assert result == "https://example.com/product"

    @pytest.mark.asyncio
    async def test_returns_original_on_exception(self, monkeypatch):
        monkeypatch.setenv("SOVRN_API_KEY", "fake-key")
        from api.feeds.sovrn import monetize_url
        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.get = AsyncMock(side_effect=Exception("timeout"))
            result = await monetize_url("https://example.com/product")
        assert result == "https://example.com/product"


class TestGetSovrnProduct:
    @pytest.mark.asyncio
    async def test_returns_none_without_key(self, monkeypatch):
        monkeypatch.delenv("SOVRN_API_KEY", raising=False)
        from api.feeds.sovrn import get_sovrn_product
        result = await get_sovrn_product()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_product_dict_with_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SOVRN_API_KEY", "fake-key")
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api.feeds import sovrn as smod
        with patch.object(smod, "monetize_url", AsyncMock(return_value="https://example.com/monetized")):
            result = await smod.get_sovrn_product()
        assert result is not None
        assert result["source"] == "sovrn"
        assert "name" in result
        assert "deeplink" in result

    @pytest.mark.asyncio
    async def test_product_has_required_fields(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SOVRN_API_KEY", "fake-key")
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        from api.feeds import sovrn as smod
        with patch.object(smod, "monetize_url", AsyncMock(return_value="https://example.com/link")):
            result = await smod.get_sovrn_product()
        required = {"id", "name", "description", "siteUrl", "deeplink", "price", "currency", "category"}
        assert required <= set(result.keys())
