"""Tests for the price drop tracker (Build #7)."""

import time
import pytest


_PRODUCT = {
    "name": "Sony WH-1000XM5",
    "asin": "B09XS7JWHH",
    "price": 279.99,
    "source": "amazon",
}


class TestRecordPrice:
    def test_records_price(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price(_PRODUCT)
        history = pt.get_price_history(_PRODUCT)
        assert history is not None
        assert history["price"] == pytest.approx(279.99)

    def test_overwrites_old_price(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price({**_PRODUCT, "price": 300.0})
        pt.record_price({**_PRODUCT, "price": 250.0})
        history = pt.get_price_history(_PRODUCT)
        assert history["price"] == pytest.approx(250.0)

    def test_ignores_zero_price(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price({**_PRODUCT, "price": 0})
        assert pt.get_price_history(_PRODUCT) is None

    def test_ignores_missing_price(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        p = {k: v for k, v in _PRODUCT.items() if k != "price"}
        pt.record_price(p)
        assert pt.get_price_history(p) is None


class TestProductKey:
    def test_asin_key_preferred(self):
        from api.utils.price_tracker import _product_key
        key = _product_key({"asin": "B001", "deeplink": "https://ex.com"})
        assert key == "asin:B001"

    def test_url_key_fallback(self):
        from api.utils.price_tracker import _product_key
        key = _product_key({"deeplink": "https://ex.com/dp/B001"})
        assert key.startswith("url:")

    def test_name_key_last_resort(self):
        from api.utils.price_tracker import _product_key
        key = _product_key({"name": "Widget"})
        assert key.startswith("name:")

    def test_no_identifiable_key_returns_none(self):
        from api.utils.price_tracker import _product_key
        assert _product_key({}) is None


class TestCheckPriceDrop:
    def test_no_history_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        result = pt.check_price_drop(_PRODUCT)
        assert result is None

    def test_20pct_drop_triggers_alert(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price({**_PRODUCT, "price": 100.0})
        result = pt.check_price_drop({**_PRODUCT, "price": 80.0})  # 20% drop
        assert result is not None
        assert result["drop_pct"] == pytest.approx(0.20)
        assert result["old_price"] == pytest.approx(100.0)
        assert result["new_price"] == pytest.approx(80.0)

    def test_19pct_drop_does_not_trigger(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price({**_PRODUCT, "price": 100.0})
        result = pt.check_price_drop({**_PRODUCT, "price": 81.5})  # 18.5% drop
        assert result is None

    def test_price_increase_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price({**_PRODUCT, "price": 100.0})
        result = pt.check_price_drop({**_PRODUCT, "price": 120.0})
        assert result is None

    def test_stale_history_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price({**_PRODUCT, "price": 100.0})
        # Manually age the record beyond MAX_AGE_DAYS
        data = pt._load()
        key = pt._product_key(_PRODUCT)
        data[key]["timestamp"] = time.time() - (pt.MAX_AGE_DAYS + 1) * 86_400
        pt._save(data)

        result = pt.check_price_drop({**_PRODUCT, "price": 50.0})
        assert result is None

    def test_drop_pct_in_result(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price({**_PRODUCT, "price": 200.0})
        result = pt.check_price_drop({**_PRODUCT, "price": 100.0})  # 50% drop
        assert result["drop_pct"] == pytest.approx(0.50)

    def test_name_in_result(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price({**_PRODUCT, "price": 300.0})
        result = pt.check_price_drop({**_PRODUCT, "price": 200.0})
        assert result["name"] == _PRODUCT["name"]


class TestClearStale:
    def test_removes_old_entries(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price(_PRODUCT)
        data = pt._load()
        key = pt._product_key(_PRODUCT)
        data[key]["timestamp"] = time.time() - (pt.MAX_AGE_DAYS + 2) * 86_400
        pt._save(data)

        removed = pt.clear_stale()
        assert removed == 1
        assert pt.get_price_history(_PRODUCT) is None

    def test_keeps_fresh_entries(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.price_tracker as pt
        pt.DATA_DIR = tmp_path
        importlib.reload(pt)

        pt.record_price(_PRODUCT)
        removed = pt.clear_stale()
        assert removed == 0
        assert pt.get_price_history(_PRODUCT) is not None
