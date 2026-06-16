from api.utils.daily_digest import build_digest, digest_text

_NOW_TS = "2026-06-16T14:00:00+00:00"
_OLD_TS = "2025-01-01T00:00:00+00:00"


def _run(clicks=10, platform="bluesky", ts=_NOW_TS):
    return {"success": True, "clicks": clicks, "platform": platform, "timestamp": ts, "title": "Hat"}


def test_digest_structure():
    d = build_digest([])
    for key in ("generated_at", "period_days", "total_posts", "total_clicks",
                 "estimated_commission", "top_platform", "peak_hour",
                 "platform_breakdown", "top_posts", "hour_clicks"):
        assert key in d


def test_digest_empty_runs():
    d = build_digest([])
    assert d["total_posts"] == 0
    assert d["total_clicks"] == 0
    assert d["estimated_commission"] == 0.0


def test_digest_counts_posts():
    runs = [_run(), _run()]
    d = build_digest(runs)
    assert d["total_posts"] == 2


def test_digest_sums_clicks():
    runs = [_run(clicks=10), _run(clicks=20)]
    d = build_digest(runs)
    assert d["total_clicks"] == 30


def test_digest_excludes_old():
    runs = [_run(ts=_OLD_TS)]
    d = build_digest(runs, days=1)
    assert d["total_posts"] == 0


def test_digest_excludes_failed():
    runs = [{"success": False, "clicks": 100, "platform": "x", "timestamp": _NOW_TS}]
    d = build_digest(runs)
    assert d["total_posts"] == 0


def test_digest_top_platform():
    runs = [_run(clicks=5, platform="bluesky"), _run(clicks=50, platform="x")]
    d = build_digest(runs)
    assert d["top_platform"] == "x"


def test_digest_commission_estimate():
    runs = [_run(clicks=100)]
    d = build_digest(runs, conversion_rate=0.1, avg_order_value=100.0, commission_pct=0.1)
    assert d["estimated_commission"] == 100.0


def test_digest_top_posts_capped_at_3():
    runs = [_run(clicks=i) for i in range(10)]
    d = build_digest(runs)
    assert len(d["top_posts"]) <= 3


def test_digest_top_posts_sorted():
    runs = [_run(clicks=5), _run(clicks=50), _run(clicks=20)]
    d = build_digest(runs)
    clicks = [r["clicks"] for r in d["top_posts"]]
    assert clicks == sorted(clicks, reverse=True)


def test_digest_platform_breakdown_structure():
    runs = [_run(platform="bluesky"), _run(platform="x")]
    d = build_digest(runs)
    assert "bluesky" in d["platform_breakdown"]
    assert "x" in d["platform_breakdown"]


def test_digest_text_returns_string():
    d = build_digest([_run()])
    assert isinstance(digest_text(d), str)


def test_digest_text_contains_clicks():
    d = build_digest([_run(clicks=42)])
    assert "42" in digest_text(d)


def test_digest_text_empty():
    d = build_digest([])
    text = digest_text(d)
    assert "Digest" in text
