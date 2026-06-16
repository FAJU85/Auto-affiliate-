from datetime import datetime, timezone


def get_full_health() -> dict:
    from .feed_health import all_feeds_health
    from .latency_tracker import latency_summary
    from .commission_rates import get_all_rates
    from .budget import get_daily_spend, get_monthly_forecast

    feeds = all_feeds_health()
    latency = latency_summary()
    rates = get_all_rates()
    daily_spend = get_daily_spend()
    forecast = get_monthly_forecast()

    feeds_list = feeds if isinstance(feeds, list) else list(feeds.values())
    feed_statuses = [v.get("status", "unknown") if isinstance(v, dict) else "unknown" for v in feeds_list]
    if all(s == "healthy" for s in feed_statuses) or not feed_statuses:
        overall = "healthy"
    elif any(s == "down" for s in feed_statuses):
        overall = "degraded"
    else:
        overall = "warning"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "feeds": feeds,
        "latency": latency,
        "commission_rates": rates,
        "budget": {
            "daily_spend_usd": daily_spend,
            "monthly_est_usd": forecast.get("monthly_est_usd", 0.0),
            "cap_usd": forecast.get("cap_usd", 2.0),
            "on_track": forecast.get("on_track", True),
        },
    }
