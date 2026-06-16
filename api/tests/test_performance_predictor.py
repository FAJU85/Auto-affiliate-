from api.utils.performance_predictor import predict, best_time_to_post, rank_platforms, learn_from_history


def test_predict_structure():
    r = predict("bluesky", hour=12)
    for key in ("platform", "hour", "predicted_clicks", "factors"):
        assert key in r


def test_predict_returns_positive():
    r = predict("instagram", hour=19, category="fashion", word_count=40)
    assert r["predicted_clicks"] > 0


def test_predict_instagram_higher_than_tumblr():
    ig = predict("instagram", hour=12)
    tb = predict("tumblr", hour=12)
    assert ig["predicted_clicks"] > tb["predicted_clicks"]


def test_predict_peak_hour_higher():
    peak = predict("x", hour=19)
    off = predict("x", hour=3)
    assert peak["predicted_clicks"] > off["predicted_clicks"]


def test_predict_high_category_factor():
    elec = predict("bluesky", hour=12, category="electronics")
    plain = predict("bluesky", hour=12, category="")
    assert elec["predicted_clicks"] > plain["predicted_clicks"]


def test_predict_short_text_penalized():
    short = predict("bluesky", hour=12, word_count=5)
    normal = predict("bluesky", hour=12, word_count=30)
    assert short["predicted_clicks"] < normal["predicted_clicks"]


def test_predict_factors_structure():
    r = predict("x", hour=10)
    for key in ("platform", "hour", "category", "word_count"):
        assert key in r["factors"]


def test_best_time_to_post_structure():
    r = best_time_to_post("instagram")
    assert "best_hour" in r
    assert "predicted_clicks" in r


def test_best_time_to_post_valid_hour():
    r = best_time_to_post("bluesky")
    assert 0 <= r["best_hour"] <= 23


def test_rank_platforms_sorted():
    platforms = ["bluesky", "instagram", "tumblr", "x"]
    result = rank_platforms(platforms, hour=19)
    clicks = [r["predicted_clicks"] for r in result]
    assert clicks == sorted(clicks, reverse=True)


def test_rank_platforms_empty():
    assert rank_platforms([]) == []


def test_learn_from_history_empty():
    r = learn_from_history([])
    assert r["best_platform"] is None
    assert r["best_hour"] is None


def test_learn_from_history_structure():
    runs = [
        {"success": True, "clicks": 10, "platform": "bluesky", "timestamp": "2026-06-16T10:00:00+00:00"},
        {"success": True, "clicks": 20, "platform": "x", "timestamp": "2026-06-16T19:00:00+00:00"},
    ]
    r = learn_from_history(runs)
    assert "platform_avg" in r
    assert "hour_avg" in r
    assert r["best_platform"] == "x"


def test_learn_from_history_excludes_failed():
    runs = [
        {"success": False, "clicks": 999, "platform": "bluesky", "timestamp": "2026-06-16T10:00:00+00:00"},
    ]
    r = learn_from_history(runs)
    assert r["best_platform"] is None
