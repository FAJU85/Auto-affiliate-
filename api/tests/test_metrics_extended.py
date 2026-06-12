"""Extended metrics tests — network health, dedup, clicks, dedup_by_source."""

import pytest
from datetime import datetime, timezone


@pytest.fixture()
def m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import api.utils.metrics as mmod
    importlib.reload(mmod)
    yield mmod
    importlib.reload(mmod)


class TestGetNetworkHealth:
    def test_empty_when_no_runs(self, m):
        assert m.get_network_health() == {}

    def test_tracks_success_rate(self, m):
        ts = datetime.now(timezone.utc).isoformat()
        m.record_run({"success": True, "productSource": "sovrn", "timestamp": ts})
        m.record_run({"success": False, "productSource": "sovrn", "timestamp": ts})
        health = m.get_network_health()
        assert health["sovrn"]["attempts"] == 2
        assert health["sovrn"]["success"] == 1
        assert health["sovrn"]["rate"] == 0.5

    def test_ignores_runs_without_source(self, m):
        ts = datetime.now(timezone.utc).isoformat()
        m.record_run({"success": True, "timestamp": ts})  # no productSource
        assert m.get_network_health() == {}


class TestDedupStatus:
    def test_returns_counts(self, m):
        m.mark_posted("https://example.com/a", "ProductA", "sovrn")
        status = m.get_dedup_status()
        assert status["count"] == 1
        assert status["activeCount"] == 1

    def test_ttl_hours_in_output(self, m):
        status = m.get_dedup_status()
        assert "ttlHours" in status


class TestDedupBySource:
    def test_counts_by_source(self, m):
        m.mark_posted("https://a.com", "A", "sovrn")
        m.mark_posted("https://b.com", "B", "sovrn")
        m.mark_posted("https://c.com", "C", "amazon")
        by_src = m.get_dedup_by_source()
        assert by_src["sovrn"] == 2
        assert by_src["amazon"] == 1

    def test_empty_when_no_posts(self, m):
        assert m.get_dedup_by_source() == {}


class TestClearPostedStore:
    def test_clears_and_returns_count(self, m):
        m.mark_posted("https://example.com/a", "A", "sovrn")
        m.mark_posted("https://example.com/b", "B", "sovrn")
        count = m.clear_posted_store()
        assert count == 2
        assert m.get_dedup_status()["count"] == 0


class TestRecordClick:
    def test_increments_click_count(self, m):
        ts = datetime.now(timezone.utc).isoformat()
        m.record_run({"success": True, "trackingId": "abc123", "timestamp": ts})
        result = m.record_click("abc123")
        assert result is not None
        assert result["clicks"] == 1

    def test_returns_none_for_unknown_id(self, m):
        result = m.record_click("doesnotexist")
        assert result is None

    def test_accumulates_clicks(self, m):
        ts = datetime.now(timezone.utc).isoformat()
        m.record_run({"success": True, "trackingId": "xyz99", "clicks": 0, "timestamp": ts})
        m.record_click("xyz99")
        m.record_click("xyz99")
        run = m.record_click("xyz99")
        assert run["clicks"] == 3


class TestGetTotalClicks:
    def test_zero_when_no_clicks(self, m):
        ts = datetime.now(timezone.utc).isoformat()
        m.record_run({"success": True, "timestamp": ts})
        assert m.get_total_clicks() == 0

    def test_sums_across_runs(self, m):
        ts = datetime.now(timezone.utc).isoformat()
        m.record_run({"success": True, "trackingId": "t1", "clicks": 3, "timestamp": ts})
        m.record_run({"success": True, "trackingId": "t2", "clicks": 5, "timestamp": ts})
        assert m.get_total_clicks() == 8


class TestWasRecentlyPosted:
    def test_returns_false_for_new_url(self, m):
        assert m.was_recently_posted("https://new.example.com", "New Product") is False

    def test_returns_true_after_mark(self, m):
        m.mark_posted("https://example.com/x", "Widget", "sovrn")
        assert m.was_recently_posted("https://example.com/x", "Widget") is True

    def test_none_url_is_handled(self, m):
        assert m.was_recently_posted(None, None) is False
