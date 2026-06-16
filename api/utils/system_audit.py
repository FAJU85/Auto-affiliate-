from datetime import datetime, timezone


def run_audit() -> dict:
    now = datetime.now(timezone.utc)
    checks: list[dict] = []

    def _check(name: str, fn):
        try:
            result = fn()
            checks.append({"name": name, "status": "ok", "detail": result})
        except Exception as e:  # noqa: BLE001
            checks.append({"name": name, "status": "error", "detail": str(e)})

    from .budget import get_daily_spend, get_monthly_forecast
    _check("budget.daily_spend", get_daily_spend)
    _check("budget.monthly_forecast", lambda: get_monthly_forecast())

    from .feed_health import all_feeds_health
    _check("feeds.health", all_feeds_health)

    from .latency_tracker import latency_summary
    _check("latency.summary", latency_summary)

    from .commission_rates import get_all_rates
    _check("commission_rates", get_all_rates)

    from .blacklist import get_blacklist
    _check("blacklist", get_blacklist)

    from .platform_queue import get_enabled_platforms
    from .settings import get_settings
    _check("platform_queue", lambda: get_enabled_platforms(get_settings()))

    from .ab_test import get_results as _ab_results
    _check("ab_test.results", _ab_results)

    from .retry_queue import queue_depth
    _check("retry_queue.depth", queue_depth)

    from .analytics import monthly_summary
    _check("analytics.monthly", lambda: monthly_summary([]))

    from .campaign_tracker import list_campaigns
    _check("campaigns", list_campaigns)

    from .post_queue import get_queue
    _check("post_queue", lambda: len(get_queue()))

    ok = sum(1 for c in checks if c["status"] == "ok")
    errors = sum(1 for c in checks if c["status"] == "error")

    return {
        "timestamp": now.isoformat(),
        "total_checks": len(checks),
        "passed": ok,
        "failed": errors,
        "overall": "healthy" if errors == 0 else "degraded",
        "checks": checks,
    }
