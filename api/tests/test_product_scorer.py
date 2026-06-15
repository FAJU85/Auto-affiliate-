"""Tests for product scoring and best-candidate selection."""

import pytest
from api.utils.product_scorer import (
    ProductScore,
    score_product,
    pick_best,
    rank_products,
    _IDEAL_PRICE_MIN,
    _IDEAL_PRICE_MAX,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _p(
    name="Widget",
    price=99.0,
    commission=8.0,
    image_url="https://img.example.com/widget.jpg",
    description="A great widget you will love buying today.",
    source="sovrn",
) -> dict:
    return {
        "name": name,
        "price": price,
        "commissionRate": commission,
        "imageUrl": image_url,
        "description": description,
        "source": source,
    }


# ── ProductScore unit ─────────────────────────────────────────────────────────

class TestProductScoreTotal:
    def test_perfect_product_scores_near_1(self):
        sc = ProductScore(commission=1.0, price_band=1.0, has_image=1.0, description=1.0)
        assert sc.total == pytest.approx(1.0)

    def test_zero_product_scores_0(self):
        sc = ProductScore(commission=0.0, price_band=0.0, has_image=0.0, description=0.0)
        assert sc.total == pytest.approx(0.0)

    def test_commission_weight_is_40pct(self):
        sc = ProductScore(commission=1.0, price_band=0.0, has_image=0.0, description=0.0)
        assert sc.total == pytest.approx(0.40)

    def test_price_weight_is_30pct(self):
        sc = ProductScore(commission=0.0, price_band=1.0, has_image=0.0, description=0.0)
        assert sc.total == pytest.approx(0.30)

    def test_image_weight_is_20pct(self):
        sc = ProductScore(commission=0.0, price_band=0.0, has_image=1.0, description=0.0)
        assert sc.total == pytest.approx(0.20)

    def test_description_weight_is_10pct(self):
        sc = ProductScore(commission=0.0, price_band=0.0, has_image=0.0, description=1.0)
        assert sc.total == pytest.approx(0.10)

    def test_str_contains_percentage(self):
        sc = ProductScore(commission=1.0, price_band=1.0, has_image=1.0, description=1.0)
        assert "100%" in str(sc)


# ── score_product ─────────────────────────────────────────────────────────────

class TestScoreProductCommission:
    def test_excellent_commission_scores_1(self):
        sc = score_product(_p(commission=12.0))
        assert sc.commission == 1.0

    def test_good_commission_scores_07(self):
        sc = score_product(_p(commission=6.0))
        assert sc.commission == pytest.approx(0.7)

    def test_ok_commission_scores_04(self):
        sc = score_product(_p(commission=3.0))
        assert sc.commission == pytest.approx(0.4)

    def test_low_commission_scores_02(self):
        sc = score_product(_p(commission=1.0))
        assert sc.commission == pytest.approx(0.2)

    def test_no_commission_data_scores_05(self):
        """SOVRN products don't include commission rate — default to 0.5."""
        p = _p()
        p.pop("commissionRate", None)
        sc = score_product(p)
        assert sc.commission == pytest.approx(0.5)

    def test_zero_commission_scores_05(self):
        sc = score_product(_p(commission=0))
        assert sc.commission == pytest.approx(0.5)


class TestScoreProductPriceBand:
    def test_ideal_price_scores_1(self):
        sc = score_product(_p(price=150.0))
        assert sc.price_band == pytest.approx(1.0)

    def test_min_ideal_price_scores_1(self):
        sc = score_product(_p(price=_IDEAL_PRICE_MIN))
        assert sc.price_band == pytest.approx(1.0)

    def test_max_ideal_price_scores_1(self):
        sc = score_product(_p(price=_IDEAL_PRICE_MAX))
        assert sc.price_band == pytest.approx(1.0)

    def test_very_cheap_scores_below_1(self):
        sc = score_product(_p(price=5.0))
        assert sc.price_band < 1.0
        assert sc.price_band >= 0.3

    def test_very_expensive_scores_below_1(self):
        sc = score_product(_p(price=1500.0))
        assert sc.price_band < 1.0
        assert sc.price_band >= 0.3

    def test_zero_price_scores_03(self):
        sc = score_product(_p(price=0))
        assert sc.price_band == pytest.approx(0.3)

    def test_missing_price_scores_03(self):
        p = _p()
        p.pop("price", None)
        sc = score_product(p)
        assert sc.price_band == pytest.approx(0.3)


class TestScoreProductImage:
    def test_has_image_url_scores_1(self):
        sc = score_product(_p(image_url="https://example.com/img.jpg"))
        assert sc.has_image == 1.0

    def test_no_image_url_scores_0(self):
        p = _p(image_url=None)
        sc = score_product(p)
        assert sc.has_image == 0.0

    def test_image_search_fallback_scores_1(self):
        p = _p(image_url=None)
        p["imageSearch"] = "sony headphones"
        sc = score_product(p)
        assert sc.has_image == 1.0


class TestScoreProductDescription:
    def test_long_description_scores_1(self):
        sc = score_product(_p(description="x" * 100))
        assert sc.description == 1.0

    def test_medium_description_scores_07(self):
        sc = score_product(_p(description="x" * 60))
        assert sc.description == pytest.approx(0.7)

    def test_short_description_scores_04(self):
        sc = score_product(_p(description="x" * 30))
        assert sc.description == pytest.approx(0.4)

    def test_very_short_description_scores_01(self):
        sc = score_product(_p(description="hi"))
        assert sc.description == pytest.approx(0.1)

    def test_missing_description_uses_name(self):
        p = _p()
        p.pop("description", None)
        sc = score_product(p)
        assert sc.description > 0.0


# ── pick_best ─────────────────────────────────────────────────────────────────

class TestPickBest:
    def test_returns_none_on_empty_list(self):
        assert pick_best([]) is None

    def test_returns_single_product(self):
        p = _p()
        assert pick_best([p]) is p

    def test_picks_higher_commission(self):
        low = _p(name="Low", commission=1.0, price=100.0)
        high = _p(name="High", commission=15.0, price=100.0)
        assert pick_best([low, high]) is high

    def test_picks_better_price_band(self):
        cheap = _p(name="Cheap", commission=0, price=2.0)
        ideal = _p(name="Ideal", commission=0, price=150.0)
        assert pick_best([cheap, ideal]) is ideal

    def test_picks_product_with_image_over_without(self):
        no_img = _p(name="NoImg", image_url=None, commission=0)
        has_img = _p(name="HasImg", image_url="https://img.jpg", commission=0)
        assert pick_best([no_img, has_img]) is has_img

    def test_three_candidates_picks_highest(self):
        a = _p(name="A", commission=2.0, price=5.0, image_url=None)
        b = _p(name="B", commission=8.0, price=150.0)
        c = _p(name="C", commission=5.0, price=80.0)
        assert pick_best([a, b, c]) is b


# ── rank_products ─────────────────────────────────────────────────────────────

class TestRankProducts:
    def test_returns_list_of_tuples(self):
        products = [_p(name="A"), _p(name="B")]
        ranked = rank_products(products)
        assert len(ranked) == 2
        assert all(isinstance(sc, ProductScore) for _, sc in ranked)

    def test_sorted_descending(self):
        low = _p(name="Low", commission=1.0, price=5.0, image_url=None)
        high = _p(name="High", commission=12.0, price=150.0)
        ranked = rank_products([low, high])
        assert ranked[0][0] is high
        assert ranked[1][0] is low

    def test_empty_list_returns_empty(self):
        assert rank_products([]) == []


# ── Integration: pipeline _get_product uses scorer ───────────────────────────

class TestPipelineUsesScorer:
    @pytest.mark.asyncio
    async def test_get_product_returns_best_when_multiple_networks(self, monkeypatch):
        """When two networks return products, pipeline returns the higher-scoring one."""
        from unittest.mock import AsyncMock, patch
        from api import pipeline

        low_value = _p(name="LowValue", commission=1.0, price=5.0, image_url=None, source="sovrn")
        high_value = _p(name="HighValue", commission=12.0, price=150.0, source="takeads")

        monkeypatch.setenv("SOVRN_API_KEY", "fake-sovrn")
        monkeypatch.setenv("TAKEADS_API_KEY", "fake-takeads")
        monkeypatch.delenv("ADMITAD_FEED_URL", raising=False)
        monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)

        with patch("api.pipeline.get_sovrn_product", AsyncMock(return_value=low_value)), \
             patch("api.pipeline.get_takeads_product", AsyncMock(return_value=high_value)):
            result = await pipeline._get_product()

        assert result is not None
        assert result["name"] == "HighValue"

    @pytest.mark.asyncio
    async def test_get_product_returns_none_when_all_fail(self, monkeypatch):
        from unittest.mock import AsyncMock, patch
        from api import pipeline

        monkeypatch.setenv("SOVRN_API_KEY", "fake")
        monkeypatch.delenv("TAKEADS_API_KEY", raising=False)
        monkeypatch.delenv("ADMITAD_FEED_URL", raising=False)
        monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)

        with patch("api.pipeline.get_sovrn_product", AsyncMock(return_value=None)):
            result = await pipeline._get_product()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_product_returns_none_when_no_keys(self, monkeypatch):
        from api import pipeline
        monkeypatch.delenv("SOVRN_API_KEY", raising=False)
        monkeypatch.delenv("TAKEADS_API_KEY", raising=False)
        monkeypatch.delenv("ADMITAD_FEED_URL", raising=False)
        monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)
        result = await pipeline._get_product()
        assert result is None
