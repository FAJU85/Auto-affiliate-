from datetime import datetime, timezone, timedelta
from api.utils.performance_report import generate_report, format_report_text, format_report_html

_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)


def _run(clicks=5, days_ago=1, platform="bluesky", product_name="Widget"):
    ts = (_NOW - timedelta(days=days_ago)).isoformat()
    return {"success": True, "clicks": clicks, "timestamp": ts, "platform": platform,
            "product": {"name": product_name}}


def test_report_has_required_keys():
    result = generate_report([], now=_NOW)
    for key in ("period_days", "generated_at", "successful_posts", "total_clicks",
                "top_product", "best_platform", "projected_monthly_usd", "success_rate_pct"):
        assert key in result


def test_empty_runs_zeros():
    result = generate_report([], now=_NOW)
    assert result["total_clicks"] == 0
    assert result["successful_posts"] == 0


def test_total_clicks_summed():
    runs = [_run(clicks=3), _run(clicks=7)]
    assert generate_report(runs, now=_NOW)["total_clicks"] == 10


def test_old_runs_excluded():
    runs = [_run(clicks=100, days_ago=60)]
    result = generate_report(runs, days=7, now=_NOW)
    assert result["successful_posts"] == 0


def test_top_product_identified():
    runs = [_run(clicks=10, product_name="Alpha"), _run(clicks=2, product_name="Beta")]
    assert generate_report(runs, now=_NOW)["top_product"] == "Alpha"


def test_best_platform_identified():
    runs = [_run(clicks=10, platform="instagram"), _run(clicks=1, platform="bluesky")]
    assert generate_report(runs, now=_NOW)["best_platform"] == "instagram"


def test_projected_monthly_positive():
    runs = [_run(clicks=10)]
    result = generate_report(runs, days=7, now=_NOW)
    assert result["projected_monthly_usd"] > 0


def test_format_text_contains_key_info():
    runs = [_run(clicks=5)]
    report = generate_report(runs, now=_NOW)
    text = format_report_text(report)
    assert "Clicks" in text
    assert "Platform" in text
    assert "Monthly" in text


def test_format_html_contains_tags():
    report = generate_report([], now=_NOW)
    html = format_report_html(report)
    assert "<h2>" in html
    assert "<ul>" in html
    assert "<li>" in html


def test_format_text_returns_string():
    report = generate_report([], now=_NOW)
    assert isinstance(format_report_text(report), str)


def test_period_days_respected():
    result = generate_report([], days=14, now=_NOW)
    assert result["period_days"] == 14
