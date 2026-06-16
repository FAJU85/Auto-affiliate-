from datetime import datetime, timezone, timedelta
from api.utils.social_proof import social_proof

_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)


def _run(clicks=5, days_ago=1, platform="bluesky"):
    ts = (_NOW - timedelta(days=days_ago)).isoformat()
    return {"success": True, "clicks": clicks, "platform": platform, "timestamp": ts}


def test_empty_runs():
    result = social_proof([])
    assert result["posts_last_30d"] == 0
    assert result["total_clicks"] == 0


def test_required_keys():
    result = social_proof([])
    for key in ("posts_last_30d", "total_clicks", "platforms_active", "platform_count", "badge"):
        assert key in result


def test_counts_successful_posts():
    runs = [_run(), _run(), {"success": False, "clicks": 10, "timestamp": _run()["timestamp"], "platform": "x"}]
    result = social_proof(runs)
    assert result["posts_last_30d"] == 2


def test_sums_clicks():
    runs = [_run(clicks=10), _run(clicks=5)]
    assert social_proof(runs)["total_clicks"] == 15


def test_old_runs_excluded():
    runs = [_run(days_ago=60)]
    assert social_proof(runs)["posts_last_30d"] == 0


def test_platform_count():
    runs = [_run(platform="bluesky"), _run(platform="instagram"), _run(platform="bluesky")]
    assert social_proof(runs)["platform_count"] == 2


def test_badge_getting_started():
    assert social_proof([])["badge"] == "🌱 Getting Started"


def test_badge_active_publisher():
    runs = [_run(clicks=1) for _ in range(20)]
    result = social_proof(runs)
    assert "Active Publisher" in result["badge"] or "Growing" in result["badge"] or "Starting" in result["badge"] or "Publishing" in result["badge"]


def test_badge_is_string():
    assert isinstance(social_proof([])["badge"], str)


def test_platforms_active_sorted():
    runs = [_run(platform="x"), _run(platform="bluesky")]
    result = social_proof(runs)
    assert result["platforms_active"] == sorted(result["platforms_active"])
