import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.leaderboard as m
    importlib.reload(m)
    return m


def test_record_creates_entry(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "Widget", clicks=10)
    assert m.get_entry("p1") is not None


def test_record_accumulates(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "Widget", clicks=5, revenue=1.0)
    m.record("p1", "Widget", clicks=5, revenue=2.0)
    entry = m.get_entry("p1")
    assert entry["clicks"] == 10
    assert abs(entry["revenue"] - 3.0) < 0.001


def test_get_entry_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_entry("nonexistent") is None


def test_record_computes_score(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "Widget", clicks=10, revenue=5.0, conversions=1)
    entry = m.get_entry("p1")
    assert entry["score"] > 0


def test_rank_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.rank() == []


def test_rank_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "Widget", clicks=10)
    result = m.rank()
    assert "rank" in result[0]
    assert "percentile" in result[0]


def test_rank_sorted_by_metric(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "Low", clicks=1)
    m.record("p2", "High", clicks=100)
    result = m.rank(metric="clicks")
    assert result[0]["product_id"] == "p2"


def test_rank_invalid_metric(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        m.rank(metric="invalid")


def test_rank_top_n(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for i in range(5):
        m.record(f"p{i}", f"Widget {i}", clicks=i)
    result = m.rank(top_n=3)
    assert len(result) == 3


def test_rank_first_is_rank_1(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "Widget", clicks=10)
    result = m.rank()
    assert result[0]["rank"] == 1


def test_podium_returns_max_3(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for i in range(5):
        m.record(f"p{i}", f"Widget {i}", clicks=i * 10)
    result = m.podium()
    assert len(result) <= 3


def test_reset_entry(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "Widget", clicks=100, revenue=50.0)
    assert m.reset_entry("p1") is True
    entry = m.get_entry("p1")
    assert entry["clicks"] == 0
    assert entry["revenue"] == 0.0


def test_reset_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.reset_entry("nonexistent") is False


def test_leaderboard_stats(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record("p1", "Widget A", clicks=10, revenue=5.0, conversions=1)
    m.record("p2", "Widget B", clicks=20, revenue=10.0, conversions=2)
    s = m.leaderboard_stats()
    assert s["total"] == 2
    assert s["total_clicks"] == 30
    assert abs(s["total_revenue"] - 15.0) < 0.001
    assert s["total_conversions"] == 3


def test_leaderboard_stats_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.leaderboard_stats()
    assert s["total"] == 0
