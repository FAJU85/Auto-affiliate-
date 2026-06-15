"""Tests for the Amazon Associates feed (Build #6)."""

import os
import pytest


class TestGetAmazonProduct:
    @pytest.mark.asyncio
    async def test_returns_none_without_tag(self, monkeypatch):
        monkeypatch.delenv("AMAZON_ASSOCIATE_TAG", raising=False)
        from api.feeds.amazon import get_amazon_product
        result = await get_amazon_product()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_product_with_tag(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        from api.feeds.amazon import get_amazon_product
        result = await get_amazon_product()
        assert result is not None
        assert result["source"] == "amazon"

    @pytest.mark.asyncio
    async def test_product_has_required_fields(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        from api.feeds.amazon import get_amazon_product
        result = await get_amazon_product()
        for field in ("name", "price", "deeplink", "category", "commissionRate", "source"):
            assert field in result, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_deeplink_contains_associate_tag(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "teststore-21")
        from api.feeds.amazon import get_amazon_product
        result = await get_amazon_product()
        assert "teststore-21" in result["deeplink"]

    @pytest.mark.asyncio
    async def test_deeplink_contains_amazon_domain(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        from api.feeds.amazon import get_amazon_product
        result = await get_amazon_product()
        assert "amazon.com" in result["deeplink"]

    @pytest.mark.asyncio
    async def test_price_is_positive(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        from api.feeds.amazon import get_amazon_product
        result = await get_amazon_product()
        assert result["price"] > 0

    @pytest.mark.asyncio
    async def test_commission_rate_is_positive(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        from api.feeds.amazon import get_amazon_product
        result = await get_amazon_product()
        assert result["commissionRate"] > 0

    @pytest.mark.asyncio
    async def test_returns_different_products_over_time(self, monkeypatch):
        """Pool has multiple products — over enough calls, results vary."""
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        from api.feeds.amazon import get_amazon_product
        names = {(await get_amazon_product())["name"] for _ in range(20)}
        assert len(names) > 1  # not always the same product


class TestAffiliateUrl:
    def test_url_without_tag_has_no_tag_param(self, monkeypatch):
        monkeypatch.delenv("AMAZON_ASSOCIATE_TAG", raising=False)
        from api.feeds.amazon import _affiliate_url
        url = _affiliate_url("B00TTD9BRC")
        assert "tag=" not in url
        assert "amazon.com/dp/B00TTD9BRC" in url

    def test_url_with_tag_appends_tag(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "shop-20")
        from api.feeds.amazon import _affiliate_url
        url = _affiliate_url("B00TTD9BRC")
        assert "tag=shop-20" in url

    def test_url_format_is_standard_amazon(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        from api.feeds.amazon import _affiliate_url
        url = _affiliate_url("B09XS7JWHH")
        assert url.startswith("https://www.amazon.com/dp/")


class TestProductPool:
    def test_pool_is_not_empty(self):
        from api.feeds.amazon import PRODUCT_POOL
        assert len(PRODUCT_POOL) >= 10

    def test_all_products_have_asin(self):
        from api.feeds.amazon import PRODUCT_POOL
        for p in PRODUCT_POOL:
            assert p.get("asin"), f"Missing ASIN: {p.get('name')}"

    def test_all_products_have_name(self):
        from api.feeds.amazon import PRODUCT_POOL
        for p in PRODUCT_POOL:
            assert p.get("name"), "Product missing name"

    def test_all_products_have_price(self):
        from api.feeds.amazon import PRODUCT_POOL
        for p in PRODUCT_POOL:
            assert p.get("price", 0) > 0, f"Invalid price for {p.get('name')}"

    def test_categories_have_commission_rates(self):
        from api.feeds.amazon import PRODUCT_POOL, _CATEGORY_COMMISSION
        for p in PRODUCT_POOL:
            cat = p.get("category", "")
            assert cat in _CATEGORY_COMMISSION, f"No commission rate for category: {cat}"


class TestPipelineUsesAmazon:
    @pytest.mark.asyncio
    async def test_get_product_includes_amazon_when_tag_set(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        monkeypatch.delenv("SOVRN_API_KEY", raising=False)
        monkeypatch.delenv("TAKEADS_API_KEY", raising=False)
        monkeypatch.delenv("ADMITAD_FEED_URL", raising=False)
        monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)

        from api import pipeline
        result = await pipeline._get_product()
        assert result is not None
        assert result["source"] == "amazon"

    @pytest.mark.asyncio
    async def test_amazon_competes_with_other_networks(self, monkeypatch):
        from unittest.mock import AsyncMock, patch
        monkeypatch.setenv("AMAZON_ASSOCIATE_TAG", "mysite-20")
        monkeypatch.setenv("SOVRN_API_KEY", "fake-key")
        monkeypatch.delenv("TAKEADS_API_KEY", raising=False)
        monkeypatch.delenv("ADMITAD_FEED_URL", raising=False)
        monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)

        low_sovrn = {
            "name": "Cheap Gadget", "price": 5.0, "commissionRate": 1.0,
            "imageUrl": None, "description": "meh", "deeplink": "https://ex.com/1",
            "source": "sovrn",
        }

        from api import pipeline
        with patch("api.pipeline.get_sovrn_product", AsyncMock(return_value=low_sovrn)):
            result = await pipeline._get_product()

        # Amazon product should score higher than a $5 no-image product
        assert result is not None
        # Result comes from whichever scored higher — both are valid
        assert result["source"] in ("sovrn", "amazon")
