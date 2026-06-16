import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.funnel_tracker as m
    importlib.reload(m)
    return m


def test_get_funnel_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_funnel("p1") is None


def test_record_creates_entry(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "click")
    assert m.get_funnel("p1") is not None


def test_record_increments(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "click")
    m.record("p1", "click")
    assert m.get_funnel("p1")["click"] == 2


def test_record_invalid_stage(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        m.record("p1", "unknown_stage")


def test_record_all_stages(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for stage in ("impression", "click", "view", "cart", "purchase"):
        m.record("p1", stage)
    entry = m.get_funnel("p1")
    assert all(entry[s] == 1 for s in ("impression", "click", "view", "cart", "purchase"))


def test_conversion_rate_none_when_no_entry(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.conversion_rate("p1") is None


def test_conversion_rate_none_when_no_clicks(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "impression")
    assert m.conversion_rate("p1") is None


def test_conversion_rate_calculation(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for _ in range(10):
        m.record("p1", "click")
    for _ in range(2):
        m.record("p1", "purchase")
    rate = m.conversion_rate("p1")
    assert rate == 0.2


def test_funnel_summary_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.funnel_summary() == []


def test_funnel_summary_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "click")
    summary = m.funnel_summary()
    assert len(summary) == 1
    for key in ("product_id", "click", "purchase", "click_to_purchase"):
        assert key in summary[0]


def test_funnel_summary_sorted_by_clicks(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "click")
    for _ in range(5):
        m.record("p2", "click")
    summary = m.funnel_summary()
    assert summary[0]["product_id"] == "p2"


def test_reset_product(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "click")
    assert m.reset_product("p1") is True
    assert m.get_funnel("p1")["click"] == 0


def test_reset_product_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.reset_product("nonexistent") is False
