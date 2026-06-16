"""Tests for auto-hashtag optimizer (Build #13)."""


class TestHashtagsFor:
    def test_returns_list_of_strings(self):
        from api.utils.hashtag_optimizer import hashtags_for
        result = hashtags_for("Electronics", platform="instagram")
        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)

    def test_all_start_with_hash(self):
        from api.utils.hashtag_optimizer import hashtags_for
        tags = hashtags_for("Beauty", platform="instagram")
        assert all(t.startswith("#") for t in tags)

    def test_respects_platform_limit_instagram(self):
        from api.utils.hashtag_optimizer import hashtags_for, _PLATFORM_TAG_LIMITS
        limit = _PLATFORM_TAG_LIMITS["instagram"]
        tags = hashtags_for("Electronics", platform="instagram")
        assert len(tags) <= limit

    def test_bluesky_returns_empty(self):
        from api.utils.hashtag_optimizer import hashtags_for
        assert hashtags_for("Electronics", platform="bluesky") == []

    def test_facebook_returns_empty(self):
        from api.utils.hashtag_optimizer import hashtags_for
        assert hashtags_for("Home", platform="facebook") == []

    def test_tumblr_returns_empty(self):
        from api.utils.hashtag_optimizer import hashtags_for
        assert hashtags_for("Books", platform="tumblr") == []

    def test_x_returns_max_2(self):
        from api.utils.hashtag_optimizer import hashtags_for
        tags = hashtags_for("Electronics", platform="x")
        assert len(tags) <= 2

    def test_n_overrides_platform_limit(self):
        from api.utils.hashtag_optimizer import hashtags_for
        tags = hashtags_for("Beauty", platform="instagram", n=3)
        assert len(tags) <= 3

    def test_unknown_category_uses_general(self):
        from api.utils.hashtag_optimizer import hashtags_for
        tags = hashtags_for("UnknownCategory", platform="instagram")
        assert len(tags) > 0

    def test_all_known_categories_have_tags(self):
        from api.utils.hashtag_optimizer import hashtags_for, _CATEGORY_TAGS
        for cat in _CATEGORY_TAGS:
            tags = hashtags_for(cat, platform="instagram")
            assert len(tags) > 0, f"No tags for category: {cat}"


class TestComputeHashtagCtr:
    def test_empty_runs_returns_empty(self):
        from api.utils.hashtag_optimizer import compute_hashtag_ctr
        assert compute_hashtag_ctr([]) == {}

    def test_failed_runs_excluded(self):
        from api.utils.hashtag_optimizer import compute_hashtag_ctr
        runs = [{"success": False, "caption": "#tech #deals", "clicks": 5}]
        assert compute_hashtag_ctr(runs) == {}

    def test_ctr_computed_from_clicks(self):
        from api.utils.hashtag_optimizer import compute_hashtag_ctr
        runs = [
            {"success": True, "caption": "#tech", "clicks": 3},
            {"success": True, "caption": "#tech", "clicks": 1},
        ]
        result = compute_hashtag_ctr(runs)
        assert "#tech" in result
        assert result["#tech"] == 2.0  # (3+1)/2

    def test_multiple_tags_per_post(self):
        from api.utils.hashtag_optimizer import compute_hashtag_ctr
        runs = [{"success": True, "caption": "#tech #deals #gadgets", "clicks": 2}]
        result = compute_hashtag_ctr(runs)
        assert "#tech" in result
        assert "#deals" in result
        assert "#gadgets" in result


class TestInjectHashtags:
    def test_appends_tags_to_caption(self):
        from api.utils.hashtag_optimizer import inject_hashtags
        result = inject_hashtags("Great product!", ["#tech", "#deals"])
        assert "#tech" in result
        assert "#deals" in result

    def test_no_duplicate_tags(self):
        from api.utils.hashtag_optimizer import inject_hashtags
        result = inject_hashtags("Love #tech stuff!", ["#tech", "#deals"])
        assert result.count("#tech") == 1

    def test_original_caption_preserved(self):
        from api.utils.hashtag_optimizer import inject_hashtags
        caption = "Amazing product at a great price!"
        result = inject_hashtags(caption, ["#deals"])
        assert caption.rstrip() in result

    def test_no_tags_returns_unchanged(self):
        from api.utils.hashtag_optimizer import inject_hashtags
        caption = "Buy this now!"
        assert inject_hashtags(caption, []) == caption


class TestCtrBoostReranking:
    def test_high_ctr_tag_ranked_first(self):
        from api.utils.hashtag_optimizer import hashtags_for
        # Seed run history where #deals gets high clicks
        runs = [
            {"success": True, "caption": "#deals", "clicks": 10},
            {"success": True, "caption": "#deals", "clicks": 8},
            {"success": True, "caption": "#tech", "clicks": 0},
        ]
        tags = hashtags_for("Electronics", platform="instagram", runs=runs)
        # #deals should appear before #tech after CTR reranking
        assert "#deals" in tags
        deals_idx = tags.index("#deals")
        if "#tech" in tags:
            tech_idx = tags.index("#tech")
            assert deals_idx < tech_idx


class TestOptimizedHashtags:
    def test_returns_list(self):
        from api.utils.hashtag_optimizer import optimized_hashtags
        product = {"name": "Sony Headphones", "category": "Electronics"}
        result = optimized_hashtags(product, platform="instagram")
        assert isinstance(result, list)

    def test_uses_product_category(self):
        from api.utils.hashtag_optimizer import optimized_hashtags, _CATEGORY_TAGS
        product = {"name": "Lipstick", "category": "Beauty"}
        tags = optimized_hashtags(product, platform="instagram")
        beauty_tags = set(_CATEGORY_TAGS["Beauty"])
        assert any(t in beauty_tags for t in tags)
