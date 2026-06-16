from api.utils.product_scorer import score_product, rank_products


def test_score_structure():
    r = score_product({"price": "10.00"})
    assert "score" in r
    assert "breakdown" in r


def test_score_cheap_product_high():
    r = score_product({"price": "5.00"}, clicks=50)
    assert r["score"] > 0.5


def test_score_expensive_product_lower_price_component():
    cheap = score_product({"price": "10.00"})
    expensive = score_product({"price": "190.00"})
    assert cheap["breakdown"]["price"] > expensive["breakdown"]["price"]


def test_score_no_price_neutral():
    r = score_product({})
    assert r["breakdown"]["price"] == 0.5


def test_score_clicks_zero():
    r = score_product({}, clicks=0)
    assert r["breakdown"]["clicks"] == 0.0


def test_score_clicks_100():
    r = score_product({}, clicks=100)
    assert r["breakdown"]["clicks"] == 1.0


def test_score_freshness_never_posted():
    r = score_product({}, last_posted_hours=None)
    assert r["breakdown"]["freshness"] == 1.0


def test_score_freshness_recent():
    r = score_product({}, last_posted_hours=2.0)
    assert r["breakdown"]["freshness"] == 0.0


def test_score_freshness_old():
    r = score_product({}, last_posted_hours=72.0)
    assert r["breakdown"]["freshness"] == 1.0


def test_score_has_image():
    r = score_product({"image": "https://img.com/x.jpg"})
    assert r["breakdown"]["has_image"] == 1.0


def test_score_no_image():
    r = score_product({})
    assert r["breakdown"]["has_image"] == 0.0


def test_score_range():
    r = score_product({"price": "50"}, clicks=10, last_posted_hours=None)
    assert 0.0 <= r["score"] <= 1.0


def test_rank_products_empty():
    assert rank_products([]) == []


def test_rank_products_adds_score():
    products = [{"id": "p1", "price": "20"}]
    result = rank_products(products)
    assert "score" in result[0]
    assert "score_breakdown" in result[0]


def test_rank_products_sorted_descending():
    products = [
        {"id": "p1", "price": "190"},
        {"id": "p2", "price": "5", "image": "x.jpg"},
    ]
    result = rank_products(products, clicks_map={"p2": 50})
    assert result[0]["id"] == "p2"


def test_rank_products_uses_clicks_map():
    products = [{"id": "p1", "price": "10"}]
    r1 = rank_products(products, clicks_map={"p1": 0})
    r2 = rank_products(products, clicks_map={"p1": 100})
    assert r2[0]["score"] > r1[0]["score"]
