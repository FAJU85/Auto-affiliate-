import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.content_recycler as m
    importlib.reload(m)
    return m


def test_can_recycle_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.can_recycle("c1", "twitter") is True


def test_record_post_blocks_recycle(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Great deal!", clicks=5)
    assert m.can_recycle("c1", "twitter", min_days=14) is False


def test_can_recycle_different_platform(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Great deal!")
    assert m.can_recycle("c1", "bluesky") is True


def test_freshness_score_new_content(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.freshness_score("c1", "twitter") == 1.0


def test_freshness_score_just_posted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Deal!", clicks=10)
    score = m.freshness_score("c1", "twitter", min_days=14)
    assert score < 1.0


def test_freshness_score_range(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Deal!")
    score = m.freshness_score("c1", "twitter")
    assert 0.0 <= score <= 1.0


def test_get_recyclable_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_recyclable() == []


def test_get_recyclable_includes_new(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Deal!", clicks=10)
    # min_days=0 makes everything recyclable
    results = m.get_recyclable(min_days=0)
    assert len(results) == 1


def test_get_recyclable_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Deal!")
    results = m.get_recyclable(min_days=0)
    entry = results[0]
    for key in ("content_id", "platform", "content", "times_posted", "total_clicks", "freshness_score"):
        assert key in entry


def test_get_recyclable_by_platform(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Deal!")
    m.record_post("c2", "bluesky", "Deal 2!")
    results = m.get_recyclable(platform="twitter", min_days=0)
    assert all(r["platform"] == "twitter" for r in results)


def test_get_recyclable_sorted_by_clicks(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Low", clicks=1)
    m.record_post("c2", "twitter", "High", clicks=100)
    results = m.get_recyclable(min_days=0)
    assert results[0]["content_id"] == "c2"


def test_recycler_stats_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.recycler_stats()
    assert s["total_tracked"] == 0


def test_recycler_stats(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("c1", "twitter", "Deal!", clicks=5)
    m.record_post("c2", "bluesky", "Deal 2!", clicks=3)
    s = m.recycler_stats()
    assert s["total_tracked"] == 2
    assert s["total_posts"] == 2
