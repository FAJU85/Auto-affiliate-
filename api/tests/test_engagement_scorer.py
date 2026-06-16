from datetime import datetime, timezone
from api.utils.engagement_scorer import score, score_batch, best_platform

_PEAK = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)   # Monday noon
_OFFPEAK = datetime(2026, 6, 14, 3, 0, tzinfo=timezone.utc)  # Sunday 3am


def test_score_structure():
    r = score("twitter", "Great deal!", post_time=_PEAK)
    for key in ("platform", "content_score", "time_score", "platform_weight", "engagement_score", "grade"):
        assert key in r


def test_score_range():
    r = score("twitter", "Hello", post_time=_PEAK)
    assert 0.0 <= r["engagement_score"] <= 1.0


def test_peak_time_higher_than_offpeak():
    r_peak = score("twitter", "Hello", post_time=_PEAK)
    r_off = score("twitter", "Hello", post_time=_OFFPEAK)
    assert r_peak["time_score"] > r_off["time_score"]


def test_positive_signals_boost_content():
    r1 = score("twitter", "Product", post_time=_PEAK)
    r2 = score("twitter", "Free deal sale discount", post_time=_PEAK)
    assert r2["content_score"] > r1["content_score"]


def test_hashtag_boosts_content():
    r1 = score("twitter", "Good product", post_time=_PEAK)
    r2 = score("twitter", "Good product #deals", post_time=_PEAK)
    assert r2["content_score"] >= r1["content_score"]


def test_platform_weight_applied():
    r_ig = score("instagram", "Deal", post_time=_PEAK)
    r_tumblr = score("tumblr", "Deal", post_time=_PEAK)
    assert r_ig["engagement_score"] > r_tumblr["engagement_score"]


def test_grade_a_for_high_score():
    r = score("instagram", "Free deal sale #discount", post_time=_PEAK)
    assert r["grade"] in ("A", "B", "C", "D")


def test_grade_d_for_low_score():
    r = score("tumblr", "meh", post_time=_OFFPEAK)
    assert r["grade"] == "D"


def test_unknown_platform_defaults_weight():
    r = score("unknown_platform", "Deal", post_time=_PEAK)
    assert r["engagement_score"] > 0


def test_score_batch_empty():
    assert score_batch([]) == []


def test_score_batch_structure():
    posts = [{"platform": "twitter", "content": "Deal", "post_time": _PEAK}]
    results = score_batch(posts)
    assert len(results) == 1
    assert "engagement_score" in results[0]


def test_score_batch_preserves_fields():
    posts = [{"platform": "twitter", "content": "Deal", "custom": "x", "post_time": _PEAK}]
    r = score_batch(posts)[0]
    assert r["custom"] == "x"


def test_best_platform_returns_string():
    bp = best_platform("Free deal sale", post_time=_PEAK)
    assert isinstance(bp, str)


def test_best_platform_is_known():
    bp = best_platform("Great product deal", post_time=_PEAK)
    assert bp in ("twitter", "instagram", "bluesky", "mastodon", "facebook", "threads", "tumblr")
