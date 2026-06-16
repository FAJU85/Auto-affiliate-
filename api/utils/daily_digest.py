from datetime import datetime, timezone, timedelta
from collections import defaultdict


def _today_runs(runs: list[dict], days: int = 1) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = []
    for r in runs:
        if not r.get("success"):
            continue
        try:
            ts = datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00"))
            if ts >= cutoff:
                result.append(r)
        except Exception:
            pass
    return result


def build_digest(
    runs: list[dict],
    days: int = 1,
    conversion_rate: float = 0.02,
    avg_order_value: float = 50.0,
    commission_pct: float = 0.08,
) -> dict:
    recent = _today_runs(runs, days)
    total_posts = len(recent)
    total_clicks = sum(int(r.get("clicks", 0)) for r in recent)

    # platform breakdown
    platform_stats: dict[str, dict] = defaultdict(lambda: {"posts": 0, "clicks": 0})
    for r in recent:
        p = (r.get("platform") or "unknown").lower()
        platform_stats[p]["posts"] += 1
        platform_stats[p]["clicks"] += int(r.get("clicks", 0))

    top_platform = max(platform_stats, key=lambda p: platform_stats[p]["clicks"], default=None)

    # revenue estimate
    conversions = total_clicks * conversion_rate
    commission = round(conversions * avg_order_value * commission_pct, 2)

    # top posts by clicks
    top_posts = sorted(recent, key=lambda r: int(r.get("clicks", 0)), reverse=True)[:3]

    # click histogram by hour
    hour_clicks: dict[int, int] = defaultdict(int)
    for r in recent:
        try:
            h = datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00")).hour
            hour_clicks[h] += int(r.get("clicks", 0))
        except Exception:
            pass

    peak_hour = max(hour_clicks, key=lambda h: hour_clicks[h], default=None)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_days": days,
        "total_posts": total_posts,
        "total_clicks": total_clicks,
        "estimated_commission": commission,
        "top_platform": top_platform,
        "peak_hour": peak_hour,
        "platform_breakdown": dict(platform_stats),
        "top_posts": top_posts,
        "hour_clicks": dict(hour_clicks),
    }


def digest_text(digest: dict) -> str:
    lines = [
        f"📊 Daily Digest — {digest['generated_at'][:10]}",
        f"Posts: {digest['total_posts']}  |  Clicks: {digest['total_clicks']}  |  Est. Commission: ${digest['estimated_commission']}",
        f"Top Platform: {digest['top_platform'] or 'N/A'}  |  Peak Hour: {digest['peak_hour'] or 'N/A'}:00",
    ]
    if digest["top_posts"]:
        lines.append("Top Posts:")
        for i, p in enumerate(digest["top_posts"], 1):
            title = p.get("title") or p.get("product_title") or "—"
            lines.append(f"  {i}. {title} ({p.get('clicks', 0)} clicks) [{p.get('platform', '')}]")
    return "\n".join(lines)
