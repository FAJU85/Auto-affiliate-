"""Tests for api/utils/image_scorer.py — Build #31."""

from api.utils.image_scorer import best_image_url, rank_image_urls, score_image_url


# ---------------------------------------------------------------------------
# score_image_url
# ---------------------------------------------------------------------------

def test_none_url_scores_zero():
    assert score_image_url(None) == 0.0


def test_empty_string_scores_zero():
    assert score_image_url("") == 0.0


def test_jpg_extension_boosts_score():
    base = "http://example.com/product"
    with_jpg = "http://example.com/product.jpg"
    assert score_image_url(with_jpg) > score_image_url(base)


def test_known_extensions_all_boost():
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        url = f"http://example.com/image{ext}"
        assert score_image_url(url) > score_image_url("http://example.com/image"), ext


def test_large_hint_boosts_score():
    base = "http://example.com/product.jpg"
    large = "http://example.com/product_large.jpg"
    assert score_image_url(large) > score_image_url(base)


def test_other_large_hints():
    for hint in ["big", "high", "1200", "800", "original"]:
        url = f"http://example.com/product_{hint}.jpg"
        assert score_image_url(url) > score_image_url("http://example.com/product.jpg"), hint


def test_thumb_hint_lowers_score():
    base = "http://example.com/product.jpg"
    thumb = "http://example.com/product_thumb.jpg"
    assert score_image_url(thumb) < score_image_url(base)


def test_small_size_hints_penalise():
    for hint in ["small", "50x", "75x", "100x"]:
        url = f"http://example.com/product_{hint}.jpg"
        assert score_image_url(url) < score_image_url("http://example.com/product.jpg"), hint


def test_placeholder_severely_penalises():
    # baseline 0.5 + jpg +0.3 - placeholder -0.5 = 0.3; without extension: 0.0
    url_no_ext = "http://example.com/placeholder"
    assert score_image_url(url_no_ext) == 0.0  # clamped to 0
    # Even with .jpg extension the score is very low (≤ 0.35)
    url_jpg = "http://example.com/placeholder.jpg"
    assert score_image_url(url_jpg) <= 0.35


def test_placeholder_variants():
    for word in ["noimage", "default", "blank", "missing"]:
        url = f"http://example.com/{word}"
        assert score_image_url(url) == 0.0, word


def test_cdn_domain_boosts_score():
    plain = "http://example.com/product.jpg"
    cdn = "http://images.example.com/product.jpg"
    assert score_image_url(cdn) > score_image_url(plain)


def test_score_always_in_range():
    urls = [
        "http://images.cdn.com/large_original.jpg",
        "http://example.com/thumb_placeholder_blank_50x.png",
        "",
        None,
        "http://static.shop.com/product_800.webp",
    ]
    for url in urls:
        s = score_image_url(url)
        assert 0.0 <= s <= 1.0, f"Out of range for {url!r}: {s}"


# ---------------------------------------------------------------------------
# best_image_url
# ---------------------------------------------------------------------------

def test_best_image_empty_list_returns_none():
    assert best_image_url([]) is None


def test_best_image_returns_highest_score():
    urls = [
        "http://example.com/thumb.gif",
        "http://images.example.com/large_product.jpg",
        "http://example.com/placeholder.png",
    ]
    result = best_image_url(urls)
    assert result == "http://images.example.com/large_product.jpg"


def test_best_image_all_zero_scores_returns_a_url():
    # All placeholder URLs score 0 after clamping; best_image_url should still return one
    urls = ["http://example.com/placeholder1.jpg", "http://example.com/placeholder2.jpg"]
    result = best_image_url(urls)
    assert result in urls


# ---------------------------------------------------------------------------
# rank_image_urls
# ---------------------------------------------------------------------------

def test_rank_sorted_descending():
    urls = [
        "http://example.com/placeholder.jpg",
        "http://images.example.com/large_product.jpg",
        "http://example.com/product_thumb.jpg",
    ]
    ranked = rank_image_urls(urls)
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_returns_all_urls():
    urls = ["http://a.com/a.jpg", "http://b.com/b.png", "http://c.com/c"]
    ranked = rank_image_urls(urls)
    assert len(ranked) == 3
    assert {u for u, _ in ranked} == set(urls)


def test_rank_empty_list():
    assert rank_image_urls([]) == []
