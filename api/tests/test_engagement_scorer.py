from datetime import datetime, timezone, timedelta
from api.utils.engagement_scorer import score_run, top_engaged_runs, engagement_summary

_NOW = datetime(2026, 6, 16, 12, 0, 0, tzinfo=timezone.utc)


def _run(clicks=5, platform="bluesky", days_ago=0, success=True):
    ts = (_NOW - timedelta(days=days_ago)).isoformat()
    return {"success": success, "clicks": clicks, "platform": platform, "timestamp": ts}


def test_failed_run_scores_zero():
    assert score_run(_run(success=False)) == 0.0


def test_zero_clicks_scores_zero():
    assert score_run(_run(clicks=0), now=_NOW) == 0.0


def test_positive_clicks_positive_score():
    assert score_run(_run(clicks=5), now=_NOW) > 0


def test_instagram_scores_higher_than_tumblr():
    ig = score_run(_run(clicks=10, platform="instagram"), now=_NOW)
    tb = score_run(_run(clicks=10, platform="tumblr"), now=_NOW)
    assert ig > tb


def test_older_run_scores_lower():
    new = score_run(_run(clicks=10, days_ago=0), now=_NOW)
    old = score_run(_run(clicks=10, days_ago=14), now=_NOW)
    assert new > old


def test_unknown_platform_uses_default():
    s = score_run(_run(clicks=5, platform="pinterest"), now=_NOW)
    assert s > 0


def test_top_engaged_runs_sorted_desc():
    runs = [_run(clicks=1), _run(clicks=10), _run(clicks=5)]
    top = top_engaged_runs(runs, n=3, now=_NOW)
    scores = [r["_engagement"] for r in top]
    assert scores == sorted(scores, reverse=True)


def test_top_engaged_runs_respects_n():
    runs = [_run(clicks=i) for i in range(10)]
    assert len(top_engaged_runs(runs, n=3, now=_NOW)) == 3


def test_top_engaged_excludes_failed():
    runs = [_run(clicks=100, success=False), _run(clicks=1)]
    top = top_engaged_runs(runs, now=_NOW)
    assert all(r["success"] for r in top)


def test_engagement_summary_keys():
    result = engagement_summary([], now=_NOW)
    for key in ("period_days", "runs_counted", "total_engagement", "avg_engagement", "top_run"):
        assert key in result


def test_engagement_summary_empty_runs():
    result = engagement_summary([], now=_NOW)
    assert result["total_engagement"] == 0.0
    assert result["top_run"] is None


def test_engagement_summary_filters_by_days():
    runs = [_run(clicks=10, days_ago=60), _run(clicks=5, days_ago=1)]
    result = engagement_summary(runs, days=30, now=_NOW)
    assert result["runs_counted"] == 1


def test_engagement_summary_avg_correct():
    runs = [_run(clicks=10, days_ago=0), _run(clicks=10, days_ago=0)]
    result = engagement_summary(runs, days=30, now=_NOW)
    assert result["avg_engagement"] == result["total_engagement"] / 2
