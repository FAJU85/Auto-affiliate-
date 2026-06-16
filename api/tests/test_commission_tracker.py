import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.commission_tracker as m
    importlib.reload(m)
    return m


def test_record_returns_true(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.record("tx1", "p1", "admitad", 5.00) is True


def test_record_duplicate_returns_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    assert m.record("tx1", "p1", "admitad", 5.00) is False


def test_get_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    e = m.get("tx1")
    for key in ("transaction_id", "product_id", "network", "amount", "currency", "status", "created_at"):
        assert key in e


def test_get_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get("nonexistent") is None


def test_initial_status_pending(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    assert m.get("tx1")["status"] == "pending"


def test_update_status(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    assert m.update_status("tx1", "confirmed") is True
    assert m.get("tx1")["status"] == "confirmed"


def test_update_status_invalid(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    with pytest.raises(ValueError):
        m.update_status("tx1", "invalid")


def test_update_status_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.update_status("nonexistent", "confirmed") is False


def test_by_status_pending(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    m.record("tx2", "p2", "sovrn", 3.00)
    m.update_status("tx1", "confirmed")
    pending = m.by_status("pending")
    assert len(pending) == 1
    assert pending[0]["transaction_id"] == "tx2"


def test_by_network(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    m.record("tx2", "p2", "sovrn", 3.00)
    result = m.by_network("admitad")
    assert len(result) == 1
    assert result[0]["network"] == "admitad"


def test_total_by_status(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    m.record("tx2", "p2", "sovrn", 3.00)
    total = m.total_by_status("pending")
    assert abs(total - 8.0) < 0.001


def test_commission_stats_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.commission_stats()
    assert s["total_transactions"] == 0


def test_commission_stats_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("tx1", "p1", "admitad", 5.00)
    s = m.commission_stats()
    assert s["total_transactions"] == 1
    assert "pending" in s
    assert s["pending"]["count"] == 1
    assert abs(s["pending"]["amount_usd"] - 5.0) < 0.001
    assert "admitad" in s["by_network"]
