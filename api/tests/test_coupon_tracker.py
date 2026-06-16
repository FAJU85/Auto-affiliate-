import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.coupon_tracker as m
    importlib.reload(m)
    return m


def test_add_coupon_returns_entry(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    entry = m.add_coupon("SAVE10", discount="10%")
    assert entry["code"] == "SAVE10"
    assert entry["discount"] == "10%"


def test_code_uppercased(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    entry = m.add_coupon("save10")
    assert entry["code"] == "SAVE10"


def test_get_coupon(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("DEAL20")
    assert m.get_coupon("DEAL20") is not None


def test_get_coupon_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_coupon("NOPE") is None


def test_use_coupon_increments(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("CODE1")
    m.use_coupon("CODE1")
    m.use_coupon("CODE1")
    assert m.get_coupon("CODE1")["uses"] == 2


def test_use_coupon_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.use_coupon("NOPE") is False


def test_is_expired_no_expiry(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("NOEXP")
    assert m.is_expired("NOEXP") is False


def test_is_expired_past(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("OLD", expires_at="2020-01-01T00:00:00+00:00")
    assert m.is_expired("OLD") is True


def test_is_expired_future(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("FUTURE", expires_at="2099-01-01T00:00:00+00:00")
    assert m.is_expired("FUTURE") is False


def test_list_coupons_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.list_coupons() == []


def test_list_coupons_returns_all(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("A")
    m.add_coupon("B")
    assert len(m.list_coupons()) == 2


def test_list_coupons_filter_product(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("P1CODE", product_id="p1")
    m.add_coupon("P2CODE", product_id="p2")
    result = m.list_coupons(product_id="p1")
    assert len(result) == 1
    assert result[0]["code"] == "P1CODE"


def test_list_coupons_active_only(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("ACTIVE", expires_at="2099-01-01T00:00:00+00:00")
    m.add_coupon("EXPIRED", expires_at="2020-01-01T00:00:00+00:00")
    result = m.list_coupons(active_only=True)
    assert len(result) == 1
    assert result[0]["code"] == "ACTIVE"


def test_delete_coupon(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("DEL")
    assert m.delete_coupon("DEL") is True
    assert m.get_coupon("DEL") is None


def test_delete_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.delete_coupon("NOPE") is False


def test_coupon_stats(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_coupon("A")
    m.add_coupon("B", expires_at="2020-01-01T00:00:00+00:00")
    m.use_coupon("A")
    s = m.coupon_stats()
    assert s["total"] == 2
    assert s["expired"] == 1
    assert s["active"] == 1
    assert s["total_uses"] == 1
