import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.product_watchlist as m
    importlib.reload(m)
    return m


def test_watch_returns_true(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.watch("p1", "Nice Widget", "https://shop.com/p1") is True


def test_watch_duplicate_returns_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Nice Widget", "https://shop.com/p1")
    assert m.watch("p1", "Nice Widget", "https://shop.com/p1") is False


def test_get_item_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget", "https://shop.com/p1", target_price=9.99)
    item = m.get_item("p1")
    for key in ("product_id", "title", "url", "target_price", "last_price", "price_history", "alerts", "added_at"):
        assert key in item


def test_get_item_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_item("nonexistent") is None


def test_unwatch(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget", "https://shop.com/p1")
    assert m.unwatch("p1") is True
    assert m.get_item("p1") is None


def test_unwatch_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.unwatch("nonexistent") is False


def test_update_price_sets_last_price(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget", "https://shop.com/p1")
    m.update_price("p1", 19.99)
    assert m.get_item("p1")["last_price"] == 19.99


def test_update_price_unknown_returns_none(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.update_price("nonexistent", 9.99) is None


def test_update_price_drop_returns_alert(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget", "https://shop.com/p1")
    m.update_price("p1", 20.0)
    alert = m.update_price("p1", 15.0)
    assert alert is not None
    assert alert["type"] == "price_drop"
    assert alert["drop_pct"] == 25.0


def test_update_price_no_drop_no_alert(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget", "https://shop.com/p1")
    m.update_price("p1", 10.0)
    alert = m.update_price("p1", 12.0)
    assert alert is None


def test_target_price_alert(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget", "https://shop.com/p1", target_price=15.0)
    alert = m.update_price("p1", 14.99)
    assert alert is not None
    assert alert["type"] == "target_reached"


def test_get_alerts(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget", "https://shop.com/p1")
    m.update_price("p1", 20.0)
    m.update_price("p1", 15.0)
    alerts = m.get_alerts("p1")
    assert len(alerts) == 1


def test_list_watched(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget A", "https://shop.com/p1")
    m.watch("p2", "Widget B", "https://shop.com/p2")
    items = m.list_watched()
    assert len(items) == 2


def test_watchlist_stats(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.watch("p1", "Widget", "https://shop.com/p1", target_price=9.99)
    m.watch("p2", "Gadget", "https://shop.com/p2")
    s = m.watchlist_stats()
    assert s["total"] == 2
    assert s["with_target_price"] == 1
