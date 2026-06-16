"""Tests for CTR feedback loop (Build #12)."""


def _run(name: str, source: str, clicks: int = 0, success: bool = True) -> dict:
    return {"success": success, "product": name, "productSource": source, "clicks": clicks}


class TestComputeCtrTable:
    def test_empty_runs_returns_empty(self):
        from api.utils.ctr_feedback import compute_ctr_table
        assert compute_ctr_table([]) == []

    def test_failed_runs_excluded(self):
        from api.utils.ctr_feedback import compute_ctr_table
        runs = [_run("Widget", "amazon", clicks=5, success=False)]
        assert compute_ctr_table(runs) == []

    def test_ctr_calculated_correctly(self):
        from api.utils.ctr_feedback import compute_ctr_table
        runs = [_run("Widget", "amazon", clicks=1)] * 4  # 4 posts, 4 clicks total
        table = compute_ctr_table(runs)
        assert len(table) == 1
        assert table[0].ctr == 1.0  # 4/4

    def test_multiple_products_aggregated(self):
        from api.utils.ctr_feedback import compute_ctr_table
        runs = (
            [_run("A", "sovrn", clicks=2)] * 3
            + [_run("B", "amazon", clicks=0)] * 5
        )
        table = compute_ctr_table(runs)
        assert len(table) == 2
        names = {p.name for p in table}
        assert {"A", "B"} == names

    def test_sorted_by_ctr_descending(self):
        from api.utils.ctr_feedback import compute_ctr_table
        runs = (
            [_run("Low", "sovrn", clicks=0)] * 5
            + [_run("High", "amazon", clicks=3)] * 3
        )
        table = compute_ctr_table(runs)
        assert table[0].name == "High"


class TestCtrBoostFor:
    def test_neutral_when_no_data(self):
        from api.utils.ctr_feedback import ctr_boost_for
        assert ctr_boost_for("Unknown", "amazon", []) == 0.5

    def test_neutral_below_min_impressions(self):
        from api.utils.ctr_feedback import ctr_boost_for, MIN_IMPRESSIONS
        runs = [_run("Widget", "amazon", clicks=1)] * (MIN_IMPRESSIONS - 1)
        assert ctr_boost_for("Widget", "amazon", runs) == 0.5

    def test_high_ctr_returns_above_neutral(self):
        from api.utils.ctr_feedback import ctr_boost_for, MIN_IMPRESSIONS
        runs = [_run("Best", "amazon", clicks=5)] * MIN_IMPRESSIONS
        boost = ctr_boost_for("Best", "amazon", runs)
        assert boost > 0.5

    def test_zero_ctr_returns_below_neutral(self):
        from api.utils.ctr_feedback import ctr_boost_for, MIN_IMPRESSIONS
        runs = (
            [_run("Zero", "sovrn", clicks=0)] * MIN_IMPRESSIONS
            + [_run("Top", "amazon", clicks=5)] * MIN_IMPRESSIONS
        )
        boost = ctr_boost_for("Zero", "sovrn", runs)
        assert boost < 0.5

    def test_boost_in_valid_range(self):
        from api.utils.ctr_feedback import ctr_boost_for, MIN_IMPRESSIONS
        runs = [_run("W", "amazon", clicks=2)] * MIN_IMPRESSIONS
        boost = ctr_boost_for("W", "amazon", runs)
        assert 0.0 <= boost <= 1.0


class TestTopProducts:
    def test_returns_list_of_dicts(self):
        from api.utils.ctr_feedback import top_products, MIN_IMPRESSIONS
        runs = [_run("Widget", "amazon", clicks=1)] * MIN_IMPRESSIONS
        result = top_products(runs)
        assert isinstance(result, list)
        if result:
            assert "name" in result[0]
            assert "ctr" in result[0]

    def test_respects_n_limit(self):
        from api.utils.ctr_feedback import top_products, MIN_IMPRESSIONS
        runs = []
        for i in range(5):
            runs += [_run(f"Product{i}", "amazon", clicks=i)] * MIN_IMPRESSIONS
        result = top_products(runs, n=3)
        assert len(result) <= 3

    def test_excludes_below_min_impressions(self):
        from api.utils.ctr_feedback import top_products, MIN_IMPRESSIONS
        runs = [_run("Rare", "amazon", clicks=10)] * (MIN_IMPRESSIONS - 1)
        result = top_products(runs)
        assert all(p["impressions"] >= MIN_IMPRESSIONS for p in result)


class TestSourceCtrSummary:
    def test_groups_by_source(self):
        from api.utils.ctr_feedback import source_ctr_summary
        runs = (
            [_run("A", "amazon", clicks=1)] * 4
            + [_run("B", "sovrn", clicks=0)] * 3
        )
        result = source_ctr_summary(runs)
        sources = {r["source"] for r in result}
        assert "amazon" in sources
        assert "sovrn" in sources

    def test_ctr_computed_per_source(self):
        from api.utils.ctr_feedback import source_ctr_summary
        runs = [_run("W", "amazon", clicks=2)] * 4  # 4 impressions, 8 clicks
        result = source_ctr_summary(runs)
        amazon = next(r for r in result if r["source"] == "amazon")
        assert amazon["ctr"] == 2.0  # 8 clicks / 4 impressions


class TestCtrSummary:
    def test_returns_required_keys(self):
        from api.utils.ctr_feedback import ctr_summary
        result = ctr_summary([])
        for key in ("overall_ctr", "total_impressions", "total_clicks", "top_products", "by_source"):
            assert key in result

    def test_overall_ctr_zero_with_no_clicks(self):
        from api.utils.ctr_feedback import ctr_summary, MIN_IMPRESSIONS
        runs = [_run("W", "amazon", clicks=0)] * MIN_IMPRESSIONS
        result = ctr_summary(runs)
        assert result["overall_ctr"] == 0.0

    def test_total_counts_correct(self):
        from api.utils.ctr_feedback import ctr_summary
        runs = [_run("W", "amazon", clicks=3)] * 5
        result = ctr_summary(runs)
        assert result["total_impressions"] == 5
        assert result["total_clicks"] == 15


class TestCtrBoostInScoring:
    def test_pick_best_uses_ctr_to_break_ties(self):
        """High-CTR product wins when quality scores are otherwise equal."""
        from api.utils.product_scorer import pick_best_with_freshness
        from api.utils.ctr_feedback import MIN_IMPRESSIONS

        equal_product_a = {
            "name": "Product A", "source": "amazon", "commissionRate": 5.0,
            "price": 99.0, "imageUrl": "https://img.test/a.jpg",
            "description": "A" * 100,
        }
        equal_product_b = {
            "name": "Product B", "source": "amazon", "commissionRate": 5.0,
            "price": 99.0, "imageUrl": "https://img.test/b.jpg",
            "description": "B" * 100,
        }
        # Product A has click history, Product B has none
        runs = [{"success": True, "product": "Product A", "productSource": "amazon",
                 "clicks": 3, "timestamp": "2026-01-01T12:00:00Z"}] * MIN_IMPRESSIONS

        result = pick_best_with_freshness([equal_product_a, equal_product_b], runs)
        assert result["name"] == "Product A"
