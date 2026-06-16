from api.utils.product_scorer import score_product, rank_products, pick_best, pick_best_with_freshness, ProductScore


def test_score_returns_product_score():
    r = score_product({"price": "10.00"})
    assert isinstance(r, ProductScore)


def test_score_has_total():
    r = score_product({"price": "50"})
    assert 0.0 <= r.total <= 1.0


def test_score_ideal_price_band():
    r = score_product({"price": "100.00"})
    assert r.price_band == 1.0


def test_score_ideal_beats_extremes():
    ideal = score_product({"price": "100.00"})
    cheap = score_product({"price": "5.00"})
    expensive = score_product({"price": "800.00"})
    assert ideal.price_band > cheap.price_band
    assert ideal.price_band > expensive.price_band


def test_score_no_price_neutral():
    r = score_product({})
    assert r.price_band == 0.3


def test_score_no_commission_default():
    r = score_product({})
    assert r.commission == 0.5


def test_score_high_commission():
    r = score_product({"commissionRate": 15})
    assert r.commission == 1.0


def test_score_has_image():
    r = score_product({"image": "https://img.com/x.jpg"})
    assert r.has_image == 1.0


def test_score_no_image():
    r = score_product({})
    assert r.has_image == 0.0


def test_score_description_full():
    r = score_product({"description": "x" * 100})
    assert r.description == 1.0


def test_score_freshness_default_is_1():
    r = score_product({})
    assert r.freshness == 1.0


def test_score_total_range():
    r = score_product({"price": "50", "image": "x.jpg", "commissionRate": 10, "description": "x" * 100})
    assert 0.0 <= r.total <= 1.0


def test_rank_products_empty():
    assert rank_products([]) == []


def test_rank_products_sorted():
    products = [
        {"price": "500", "commissionRate": 0},
        {"price": "100", "commissionRate": 15, "image": "x.jpg", "description": "x" * 100},
    ]
    result = rank_products(products)
    scores = [s.total for _, s in result]
    assert scores == sorted(scores, reverse=True)


def test_pick_best_empty():
    assert pick_best([]) is None


def test_pick_best_returns_product():
    products = [{"price": "50", "image": "x.jpg"}, {"price": "500"}]
    result = pick_best(products)
    assert result is not None


def test_pick_best_with_freshness_empty():
    assert pick_best_with_freshness([], []) is None


def test_pick_best_with_freshness_returns_product():
    products = [{"id": "p1", "price": "50"}]
    result = pick_best_with_freshness(products, [])
    assert result is not None
