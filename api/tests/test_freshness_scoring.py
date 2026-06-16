"""Tests for content deduplication & freshness scoring (Build #11)."""

from datetime import datetime, timezone, timedelta


def _ts(hours_ago: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.isoformat()


def _product(name: str, commission: float = 5.0, price: float = 99.0, image: bool = True) -> dict:
    return {
        "name": name, "commissionRate": commission, "price": price,
        "imageUrl": "https://img.test/a.jpg" if image else None,
        "description": "A great product with a full description that is long enough.",
        "source": "sovrn",
    }


class TestFreshnessScore:
    def test_fresh_product_gets_max_freshness(self):
        from api.utils.product_scorer import score_product
        p = _product("Brand New Widget")
        s = score_product(p, recently_posted=set())
        assert s.freshness == 1.0

    def test_recently_posted_gets_zero_freshness(self):
        from api.utils.product_scorer import score_product
        p = _product("Old Widget")
        s = score_product(p, recently_posted={"Old Widget"})
        assert s.freshness == 0.0

    def test_freshness_influences_total_score(self):
        from api.utils.product_scorer import score_product
        p = _product("Widget")
        fresh = score_product(p, recently_posted=set())
        stale = score_product(p, recently_posted={"Widget"})
        assert fresh.total > stale.total

    def test_score_without_recently_posted_defaults_to_fresh(self):
        from api.utils.product_scorer import score_product
        p = _product("Any Widget")
        s = score_product(p)
        assert s.freshness == 1.0

    def test_freshness_weight_is_10_percent(self):
        from api.utils.product_scorer import score_product
        p = _product("W")
        fresh = score_product(p, recently_posted=set())
        stale = score_product(p, recently_posted={"W"})
        diff = round(fresh.total - stale.total, 4)
        assert abs(diff - 0.10) < 0.001


class TestPickBest:
    def test_prefers_fresh_over_stale_equal_quality(self):
        from api.utils.product_scorer import pick_best
        fresh = _product("New Item")
        stale = _product("Old Item")
        result = pick_best([fresh, stale], recently_posted={"Old Item"})
        assert result["name"] == "New Item"

    def test_high_commission_still_wins_when_both_fresh(self):
        from api.utils.product_scorer import pick_best
        cheap = _product("Budget Item", commission=1.0, price=5.0)
        premium = _product("Premium Item", commission=15.0, price=150.0)
        result = pick_best([cheap, premium], recently_posted=set())
        assert result["name"] == "Premium Item"

    def test_returns_none_for_empty_list(self):
        from api.utils.product_scorer import pick_best
        assert pick_best([]) is None

    def test_returns_only_item(self):
        from api.utils.product_scorer import pick_best
        p = _product("Solo")
        assert pick_best([p]) is p


class TestPickBestWithFreshness:
    def test_uses_run_history_to_detect_stale(self):
        from api.utils.product_scorer import pick_best_with_freshness
        runs = [{"success": True, "timestamp": _ts(1), "product": "Old Widget"}]
        fresh = _product("New Widget")
        stale = _product("Old Widget")
        result = pick_best_with_freshness([fresh, stale], runs)
        assert result["name"] == "New Widget"

    def test_ignores_old_runs_outside_dedup_window(self):
        from api.utils.product_scorer import pick_best_with_freshness
        from api.utils.metrics import DEDUP_TTL_HOURS
        # Run from beyond the dedup window — should not count as stale
        runs = [{"success": True, "timestamp": _ts(DEDUP_TTL_HOURS + 2), "product": "Widget A"}]
        p_a = _product("Widget A")
        p_b = _product("Widget B", commission=1.0)  # lower quality
        # Widget A should win because its old run doesn't count as stale
        result = pick_best_with_freshness([p_a, p_b], runs)
        assert result["name"] == "Widget A"

    def test_ignores_failed_runs(self):
        from api.utils.product_scorer import pick_best_with_freshness
        runs = [{"success": False, "timestamp": _ts(1), "product": "Widget A"}]
        p_a = _product("Widget A")
        p_b = _product("Widget B", commission=1.0)
        # Failed run doesn't make Widget A stale
        result = pick_best_with_freshness([p_a, p_b], runs)
        assert result["name"] == "Widget A"

    def test_empty_runs_treats_all_as_fresh(self):
        from api.utils.product_scorer import pick_best_with_freshness
        p = _product("Widget")
        assert pick_best_with_freshness([p], []) is p


class TestProductScoreString:
    def test_str_includes_fresh_field(self):
        from api.utils.product_scorer import score_product
        s = score_product(_product("W"))
        assert "fresh=" in str(s)

    def test_total_weights_sum_to_one(self):
        from api.utils.product_scorer import ProductScore
        s = ProductScore(commission=1.0, price_band=1.0, has_image=1.0, description=1.0, freshness=1.0)
        assert abs(s.total - 1.0) < 0.001


class TestDedupTTLConfigurable:
    def test_dedup_ttl_default_is_24(self):
        from api.utils.metrics import DEDUP_TTL_HOURS
        assert DEDUP_TTL_HOURS == 24

    def test_dedup_ttl_env_override(self, monkeypatch):
        monkeypatch.setenv("DEDUP_TTL_HOURS", "48")
        import importlib
        import api.utils.metrics as m
        importlib.reload(m)
        assert m.DEDUP_TTL_HOURS == 48
        monkeypatch.delenv("DEDUP_TTL_HOURS", raising=False)
        importlib.reload(m)
