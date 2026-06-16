from api.utils.audience_insights import peak_hours, peak_weekdays, platform_breakdown, audience_summary


def _run(clicks=5, platform="bluesky", ts="2026-06-16T14:00:00+00:00", success=True):
    return {"success": success, "clicks": clicks, "platform": platform, "timestamp": ts}


def test_peak_hours_empty():
    assert peak_hours([]) == []


def test_peak_hours_returns_sorted():
    runs = [
        _run(clicks=10, ts="2026-06-16T14:00:00+00:00"),
        _run(clicks=5, ts="2026-06-16T09:00:00+00:00"),
    ]
    result = peak_hours(runs)
    assert result[0]["hour"] == 14
    assert result[0]["clicks"] == 10


def test_peak_hours_skips_failed():
    runs = [_run(clicks=100, success=False)]
    assert peak_hours(runs) == []


def test_peak_weekdays_empty():
    assert peak_weekdays([]) == []


def test_peak_weekdays_has_weekday_name():
    runs = [_run(ts="2026-06-15T10:00:00+00:00")]  # Monday
    result = peak_weekdays(runs)
    assert result[0]["weekday"] == "Mon"


def test_peak_weekdays_sorted_by_clicks():
    runs = [
        _run(clicks=20, ts="2026-06-15T10:00:00+00:00"),  # Mon
        _run(clicks=5, ts="2026-06-16T10:00:00+00:00"),   # Tue
    ]
    result = peak_weekdays(runs)
    assert result[0]["clicks"] == 20


def test_platform_breakdown_empty():
    assert platform_breakdown([]) == []


def test_platform_breakdown_structure():
    runs = [_run(platform="bluesky", clicks=10), _run(platform="x", clicks=5)]
    result = platform_breakdown(runs)
    for entry in result:
        for key in ("platform", "posts", "clicks", "avg_clicks"):
            assert key in entry


def test_platform_breakdown_sorted_by_clicks():
    runs = [_run(platform="x", clicks=20), _run(platform="bluesky", clicks=5)]
    result = platform_breakdown(runs)
    assert result[0]["platform"] == "x"


def test_platform_breakdown_avg_clicks():
    runs = [_run(platform="bluesky", clicks=10), _run(platform="bluesky", clicks=20)]
    result = platform_breakdown(runs)
    assert result[0]["avg_clicks"] == 15.0


def test_audience_summary_structure():
    s = audience_summary([])
    for key in ("best_hour", "best_weekday", "best_platform", "peak_hours", "peak_weekdays", "platform_breakdown"):
        assert key in s


def test_audience_summary_empty():
    s = audience_summary([])
    assert s["best_hour"] is None
    assert s["best_platform"] is None


def test_audience_summary_best_platform():
    runs = [_run(platform="bluesky", clicks=50), _run(platform="x", clicks=5)]
    s = audience_summary(runs)
    assert s["best_platform"] == "bluesky"


def test_audience_summary_peak_hours_capped():
    runs = [_run(ts=f"2026-06-16T{h:02d}:00:00+00:00", clicks=h) for h in range(6)]
    s = audience_summary(runs)
    assert len(s["peak_hours"]) <= 3
