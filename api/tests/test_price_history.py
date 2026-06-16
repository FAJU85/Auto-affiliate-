import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.price_history as m
    importlib.reload(m)
    return m


def test_latest_price_none_when_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.latest_price("p1") is None


def test_record_and_latest(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 99.99)
    assert m.latest_price("p1") == 99.99


def test_history_length(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 100.0)
    m.record_price("p1", 90.0)
    assert len(m.get_history("p1")) == 2


def test_price_change_drop(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 100.0)
    m.record_price("p1", 80.0)
    ch = m.price_change("p1")
    assert ch["direction"] == "drop"
    assert ch["pct"] == -20.0


def test_price_change_rise(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 50.0)
    m.record_price("p1", 60.0)
    ch = m.price_change("p1")
    assert ch["direction"] == "rise"


def test_price_change_unchanged(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 50.0)
    m.record_price("p1", 50.0)
    assert m.price_change("p1")["direction"] == "unchanged"


def test_price_change_none_when_single(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 50.0)
    assert m.price_change("p1") is None


def test_price_change_none_when_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.price_change("p1") is None


def test_price_summary_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.price_summary("p1")
    assert s["count"] == 0
    assert s["min"] is None


def test_price_summary_values(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 100.0)
    m.record_price("p1", 80.0)
    m.record_price("p1", 90.0)
    s = m.price_summary("p1")
    assert s["min"] == 80.0
    assert s["max"] == 100.0
    assert s["latest"] == 90.0
    assert s["count"] == 3


def test_all_drops_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.all_drops() == []


def test_all_drops_detects_drop(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 100.0)
    m.record_price("p1", 50.0)
    drops = m.all_drops(min_pct=5.0)
    assert len(drops) == 1
    assert drops[0]["product_id"] == "p1"


def test_all_drops_filters_small_drops(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 100.0)
    m.record_price("p1", 98.0)
    assert m.all_drops(min_pct=5.0) == []


def test_product_isolation(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_price("p1", 10.0)
    m.record_price("p2", 20.0)
    assert m.latest_price("p1") == 10.0
    assert m.latest_price("p2") == 20.0
