import importlib
import time


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.content_freshness as m
    importlib.reload(m)
    return m


def test_is_fresh_never_posted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.is_fresh("prod1", "bluesky") is True


def test_record_and_last_posted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("prod1", "bluesky")
    lp = m.last_posted("prod1", "bluesky")
    assert lp is not None


def test_is_fresh_after_recent_post(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("prod1", "bluesky")
    assert m.is_fresh("prod1", "bluesky", min_hours=24) is False


def test_platform_isolation(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("prod1", "bluesky")
    assert m.is_fresh("prod1", "mastodon") is True


def test_product_isolation(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("prod1", "bluesky")
    assert m.is_fresh("prod2", "bluesky") is True


def test_freshness_report_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    report = m.freshness_report()
    for key in ("total_tracked", "stale_count", "fresh_count", "stale", "fresh"):
        assert key in report


def test_freshness_report_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    report = m.freshness_report()
    assert report["total_tracked"] == 0
    assert report["stale_count"] == 0


def test_freshness_report_counts_fresh(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("prod1", "bluesky")
    m.record_post("prod2", "x")
    report = m.freshness_report(min_hours=24)
    assert report["fresh_count"] == 2
    assert report["stale_count"] == 0


def test_freshness_report_counts_stale(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("prod1", "bluesky")
    report = m.freshness_report(min_hours=0)
    assert report["stale_count"] == 1


def test_clear_product(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("prod1", "bluesky")
    m.record_post("prod1", "x")
    m.record_post("prod2", "bluesky")
    removed = m.clear_product("prod1")
    assert removed == 2
    assert m.last_posted("prod1", "bluesky") is None
    assert m.last_posted("prod2", "bluesky") is not None


def test_clear_product_no_entries(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.clear_product("nonexistent") == 0


def test_last_posted_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.last_posted("x", "y") is None


def test_total_tracked(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_post("p1", "bluesky")
    m.record_post("p1", "x")
    m.record_post("p2", "bluesky")
    assert m.freshness_report()["total_tracked"] == 3
