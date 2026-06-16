from datetime import datetime, timezone, timedelta


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _recent(runs: list[dict], days: int, now: datetime) -> list[dict]:
    cutoff = now - timedelta(days=days)
    return [
        r for r in runs
        if r.get("success") and (_parse_ts(r.get("timestamp", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    ]


def _top_product(runs: list[dict]) -> str:
    counts: dict[str, int] = {}
    for r in runs:
        name = (r.get("product") or {}).get("name") if isinstance(r.get("product"), dict) else str(r.get("product", ""))
        if name:
            counts[name] = counts.get(name, 0) + int(r.get("clicks", 0))
    return max(counts, key=counts.__getitem__) if counts else "—"


def _best_platform(runs: list[dict]) -> str:
    platform_clicks: dict[str, int] = {}
    for r in runs:
        p = (r.get("platform") or "unknown").lower()
        platform_clicks[p] = platform_clicks.get(p, 0) + int(r.get("clicks", 0))
    return max(platform_clicks, key=platform_clicks.__getitem__) if platform_clicks else "—"


def generate_report(runs: list[dict], days: int = 7, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    period = _recent(runs, days, now)
    total_clicks = sum(int(r.get("clicks", 0)) for r in period)
    projected_monthly = round(total_clicks * 0.05 * (30 / max(days, 1)), 2)
    top_product = _top_product(period)
    best_platform = _best_platform(period)
    success_rate = round(len(period) / max(len([r for r in runs if _parse_ts(r.get("timestamp", "")) and (_parse_ts(r.get("timestamp", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= now - timedelta(days=days)]), 1) * 100, 1)

    return {
        "period_days": days,
        "generated_at": now.isoformat(),
        "successful_posts": len(period),
        "total_clicks": total_clicks,
        "top_product": top_product,
        "best_platform": best_platform,
        "projected_monthly_usd": projected_monthly,
        "success_rate_pct": success_rate,
    }


def format_report_text(report: dict) -> str:
    lines = [
        f"📊 Weekly Performance Report ({report['period_days']}-day)",
        f"Generated: {report['generated_at'][:10]}",
        "",
        f"✅ Successful Posts: {report['successful_posts']}",
        f"👆 Total Clicks: {report['total_clicks']}",
        f"🏆 Top Product: {report['top_product']}",
        f"📱 Best Platform: {report['best_platform']}",
        f"💰 Projected Monthly: ${report['projected_monthly_usd']:.2f}",
        f"📈 Success Rate: {report['success_rate_pct']}%",
    ]
    return "\n".join(lines)


def format_report_html(report: dict) -> str:
    return (
        f"<h2>📊 Performance Report ({report['period_days']}-day)</h2>"
        f"<p><strong>Generated:</strong> {report['generated_at'][:10]}</p>"
        f"<ul>"
        f"<li>✅ Successful Posts: <strong>{report['successful_posts']}</strong></li>"
        f"<li>👆 Total Clicks: <strong>{report['total_clicks']}</strong></li>"
        f"<li>🏆 Top Product: <strong>{report['top_product']}</strong></li>"
        f"<li>📱 Best Platform: <strong>{report['best_platform']}</strong></li>"
        f"<li>💰 Projected Monthly: <strong>${report['projected_monthly_usd']:.2f}</strong></li>"
        f"<li>📈 Success Rate: <strong>{report['success_rate_pct']}%</strong></li>"
        f"</ul>"
    )
