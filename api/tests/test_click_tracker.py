"""Tests for api/utils/click_tracker.py."""

import importlib
import sys



def _reload(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Remove cached module so DATA_DIR is re-evaluated at import time
    sys.modules.pop("api.utils.click_tracker", None)
    import api.utils.click_tracker as ct
    importlib.reload(ct)
    return ct


# ---------------------------------------------------------------------------
# Basic reads on empty store
# ---------------------------------------------------------------------------


def test_get_clicks_empty(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    assert ct.get_clicks() == []


def test_clicks_today_empty(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    assert ct.clicks_today() == 0


def test_clicks_summary_keys(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    s = ct.clicks_summary()
    assert "total" in s
    assert "today" in s
    assert "by_platform" in s
    assert "by_source" in s


# ---------------------------------------------------------------------------
# record_click return value shape
# ---------------------------------------------------------------------------


def test_record_click_returns_dict(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ev = ct.record_click("Widget", "https://example.com")
    assert isinstance(ev, dict)


def test_record_click_required_keys(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ev = ct.record_click("Widget", "https://example.com", platform="bluesky", source="feed")
    for key in ("id", "product_name", "url", "platform", "source", "timestamp"):
        assert key in ev, f"Missing key: {key}"


def test_record_click_values(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ev = ct.record_click("Widget", "https://example.com", platform="bluesky", source="feed")
    assert ev["product_name"] == "Widget"
    assert ev["url"] == "https://example.com"
    assert ev["platform"] == "bluesky"
    assert ev["source"] == "feed"


# ---------------------------------------------------------------------------
# Persistence — recorded click appears in get_clicks
# ---------------------------------------------------------------------------


def test_recorded_click_appears_in_get_clicks(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ct.record_click("GadgetX", "https://example.com/gadget")
    results = ct.get_clicks()
    assert len(results) == 1
    assert results[0]["product_name"] == "GadgetX"


def test_clicks_today_increments(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    assert ct.clicks_today() == 0
    ct.record_click("A", "https://a.com")
    assert ct.clicks_today() == 1
    ct.record_click("B", "https://b.com")
    assert ct.clicks_today() == 2


# ---------------------------------------------------------------------------
# clicks_summary aggregation
# ---------------------------------------------------------------------------


def test_clicks_summary_total(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ct.record_click("A", "https://a.com")
    ct.record_click("B", "https://b.com")
    assert ct.clicks_summary()["total"] == 2


def test_by_platform_groups(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ct.record_click("A", "https://a.com", platform="bluesky")
    ct.record_click("B", "https://b.com", platform="bluesky")
    ct.record_click("C", "https://c.com", platform="mastodon")
    s = ct.clicks_summary()
    assert s["by_platform"]["bluesky"] == 2
    assert s["by_platform"]["mastodon"] == 1


def test_by_source_groups(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ct.record_click("A", "https://a.com", source="feed")
    ct.record_click("B", "https://b.com", source="feed")
    ct.record_click("C", "https://c.com", source="dashboard")
    s = ct.clicks_summary()
    assert s["by_source"]["feed"] == 2
    assert s["by_source"]["dashboard"] == 1


# ---------------------------------------------------------------------------
# get_clicks limit
# ---------------------------------------------------------------------------


def test_get_clicks_limit(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    for i in range(5):
        ct.record_click(f"Item{i}", f"https://example.com/{i}")
    results = ct.get_clicks(limit=2)
    assert len(results) == 2


def test_get_clicks_most_recent_first(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ct.record_click("First", "https://first.com")
    ct.record_click("Second", "https://second.com")
    results = ct.get_clicks()
    assert results[0]["product_name"] == "Second"
    assert results[1]["product_name"] == "First"


# ---------------------------------------------------------------------------
# Unique IDs
# ---------------------------------------------------------------------------


def test_ids_are_unique(monkeypatch, tmp_path):
    ct = _reload(monkeypatch, tmp_path)
    ids = [ct.record_click(f"P{i}", f"https://x.com/{i}")["id"] for i in range(10)]
    assert len(set(ids)) == 10
