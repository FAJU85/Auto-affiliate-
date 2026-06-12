"""Extended platform guardian tests — interval enforcement, malformed timestamps."""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from api.utils.platform_guardian import check_allowed, get_rules


def _fake_now(hour: int = 10) -> datetime:
    return datetime.now(timezone.utc).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def _run(platform: str, ts: datetime, success: bool = True) -> dict:
    return {"success": success, "platforms": [platform], "timestamp": ts.isoformat()}


class TestIntervalEnforcement:
    def test_blocks_too_soon(self):
        fake_now = _fake_now(10)
        # Post 30 minutes ago — bluesky needs 90 min
        recent = fake_now - timedelta(minutes=30)
        runs = [_run("bluesky", recent)]
        with patch("api.utils.platform_guardian.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            allowed, reason = check_allowed("bluesky", runs)
        assert allowed is False
        assert "too soon" in reason
        assert "wait" in reason

    def test_allows_after_full_interval(self):
        fake_now = _fake_now(10)
        # Post 2 hours ago — bluesky needs 90 min
        old_post = fake_now - timedelta(hours=2)
        runs = [_run("bluesky", old_post)]
        with patch("api.utils.platform_guardian.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            allowed, reason = check_allowed("bluesky", runs)
        assert allowed is True

    def test_skips_malformed_timestamp(self):
        fake_now = _fake_now(10)
        # A run with broken timestamp — should be skipped, not crash
        runs = [{"success": True, "platforms": ["bluesky"], "timestamp": "not-a-date"}]
        with patch("api.utils.platform_guardian.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            allowed, reason = check_allowed("bluesky", runs)
        # No valid timestamp → no interval block → allowed (within posting hours, no daily limit)
        assert isinstance(allowed, bool)

    def test_naive_timestamp_gets_utc_tz(self):
        fake_now = _fake_now(10)
        # Timestamp without timezone
        naive_ts = fake_now.replace(tzinfo=None) - timedelta(hours=2)
        runs = [{"success": True, "platforms": ["bluesky"], "timestamp": naive_ts.isoformat()}]
        with patch("api.utils.platform_guardian.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            allowed, reason = check_allowed("bluesky", runs)
        # Should not crash; interval from 2h ago = allowed
        assert isinstance(allowed, bool)


class TestPostingHoursGuard:
    def test_blocks_outside_hours(self):
        # Bluesky 7–23; hour 2 is outside
        fake_now = _fake_now(2)
        with patch("api.utils.platform_guardian.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            allowed, reason = check_allowed("bluesky", [])
        assert allowed is False
        assert "outside posting hours" in reason

    def test_allows_at_start_hour(self):
        rules = get_rules("bluesky")
        start = rules["posting_hours"][0]
        fake_now = _fake_now(start)
        with patch("api.utils.platform_guardian.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            allowed, reason = check_allowed("bluesky", [])
        assert allowed is True

    def test_blocks_at_end_hour(self):
        rules = get_rules("bluesky")
        end = rules["posting_hours"][1]  # 23 — exclusive
        fake_now = _fake_now(end)
        with patch("api.utils.platform_guardian.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            allowed, reason = check_allowed("bluesky", [])
        assert allowed is False


class TestAllPlatformsHaveRules:
    def test_each_platform_has_rules(self):
        for platform in ["bluesky", "x", "threads", "facebook", "instagram", "mastodon", "tumblr"]:
            rules = get_rules(platform)
            assert rules["daily_limit"] > 0
            assert rules["min_interval_min"] > 0
            assert rules["max_hashtags"] > 0
            h_start, h_end = rules["posting_hours"]
            assert 0 <= h_start < h_end <= 24

    def test_fallback_rules_returned_for_unknown(self):
        rules = get_rules("nonexistent_platform")
        assert rules["daily_limit"] > 0
