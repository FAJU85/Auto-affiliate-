import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.ab_test_manager as m
    importlib.reload(m)
    return m


def test_create_test_returns_id(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test A", variants=["v1", "v2"])
    assert isinstance(tid, str) and len(tid) > 0


def test_create_test_needs_two_variants(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        m.create_test("Bad", variants=["v1"])


def test_get_test_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    t = m.get_test(tid)
    for key in ("id", "name", "metric", "status", "variants", "created_at"):
        assert key in t


def test_get_test_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_test("nonexistent") is None


def test_initial_status_running(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    assert m.get_test(tid)["status"] == "running"


def test_record_impression(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    assert m.record_impression(tid, "a") is True
    assert m.get_test(tid)["variants"]["a"]["impressions"] == 1


def test_record_conversion(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    m.record_impression(tid, "a")
    assert m.record_conversion(tid, "a") is True
    assert m.get_test(tid)["variants"]["a"]["conversions"] == 1


def test_record_unknown_variant(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    assert m.record_impression(tid, "c") is False


def test_conversion_rate_none_no_impressions(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    assert m.conversion_rate(tid, "a") is None


def test_conversion_rate_correct(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    for _ in range(10):
        m.record_impression(tid, "a")
    for _ in range(3):
        m.record_conversion(tid, "a")
    assert m.conversion_rate(tid, "a") == 0.3


def test_winner_none_no_data(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    assert m.winner(tid) is None


def test_winner_correct(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    for _ in range(10):
        m.record_impression(tid, "a")
        m.record_impression(tid, "b")
    for _ in range(8):
        m.record_conversion(tid, "a")
    for _ in range(2):
        m.record_conversion(tid, "b")
    w = m.winner(tid)
    assert w["variant"] == "a"


def test_significance_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["control", "treatment"])
    for _ in range(100):
        m.record_impression(tid, "control")
        m.record_impression(tid, "treatment")
    for _ in range(10):
        m.record_conversion(tid, "control")
    for _ in range(25):
        m.record_conversion(tid, "treatment")
    s = m.significance(tid, "control", "treatment")
    for key in ("control", "treatment", "z_score", "is_significant", "lift_pct"):
        assert key in s


def test_update_status(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    assert m.update_status(tid, "completed") is True
    assert m.get_test(tid)["status"] == "completed"


def test_update_status_invalid(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("Test", variants=["a", "b"])
    with pytest.raises(ValueError):
        m.update_status(tid, "invalid")


def test_list_tests(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.create_test("A", variants=["a", "b"])
    m.create_test("B", variants=["a", "b"])
    assert len(m.list_tests()) == 2


def test_list_tests_filtered(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    tid = m.create_test("A", variants=["a", "b"])
    m.create_test("B", variants=["a", "b"])
    m.update_status(tid, "completed")
    assert len(m.list_tests(status="completed")) == 1
