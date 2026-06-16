from datetime import datetime, timezone, timedelta


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def social_proof(runs: list[dict], days: int = 30) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    recent = [
        r for r in runs
        if r.get("success") and (_parse_ts(r.get("timestamp", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    ]
    platforms = {(r.get("platform") or "unknown").lower() for r in recent}
    total_clicks = sum(int(r.get("clicks", 0)) for r in recent)
    return {
        "posts_last_30d": len(recent),
        "total_clicks": total_clicks,
        "platforms_active": sorted(platforms),
        "platform_count": len(platforms),
        "badge": _badge(len(recent), total_clicks, len(platforms)),
    }


def _badge(posts: int, clicks: int, platforms: int) -> str:
    if posts == 0:
        return "🌱 Getting Started"
    if clicks >= 1000 and platforms >= 3:
        return "🏆 Top Performer"
    if clicks >= 200 and platforms >= 2:
        return "🚀 Growing Fast"
    if posts >= 20:
        return "📈 Active Publisher"
    if posts >= 5:
        return "✅ Publishing"
    return "🌱 Just Starting"
