from datetime import datetime, timezone, timedelta

_DEFAULTS = {
    "conversion_rate": 0.02,   # 2% of clicks convert to purchases
    "avg_order_value": 50.0,   # USD
    "commission_pct": 0.08,    # 8% commission
}


def estimate(
    clicks: int,
    conversion_rate: float = _DEFAULTS["conversion_rate"],
    avg_order_value: float = _DEFAULTS["avg_order_value"],
    commission_pct: float = _DEFAULTS["commission_pct"],
) -> dict:
    conversions = clicks * conversion_rate
    revenue = conversions * avg_order_value * commission_pct
    return {
        "clicks": clicks,
        "conversions": round(conversions, 2),
        "gross_revenue": round(conversions * avg_order_value, 2),
        "commission": round(revenue, 2),
        "conversion_rate": conversion_rate,
        "avg_order_value": avg_order_value,
        "commission_pct": commission_pct,
    }


def estimate_from_runs(
    runs: list[dict],
    days: int = 30,
    conversion_rate: float = _DEFAULTS["conversion_rate"],
    avg_order_value: float = _DEFAULTS["avg_order_value"],
    commission_pct: float = _DEFAULTS["commission_pct"],
) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    recent = []
    for r in runs:
        if not r.get("success"):
            continue
        try:
            ts = datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00"))
            if ts >= cutoff:
                recent.append(r)
        except Exception:
            pass

    total_clicks = sum(int(r.get("clicks", 0)) for r in recent)
    base = estimate(total_clicks, conversion_rate, avg_order_value, commission_pct)

    by_platform: dict[str, int] = {}
    for r in recent:
        p = (r.get("platform") or "unknown").lower()
        by_platform[p] = by_platform.get(p, 0) + int(r.get("clicks", 0))

    return {
        **base,
        "posts": len(recent),
        "days": days,
        "by_platform": {
            p: estimate(c, conversion_rate, avg_order_value, commission_pct)["commission"]
            for p, c in by_platform.items()
        },
    }


def roi(spend: float, commission: float) -> dict:
    if spend <= 0:
        return {"spend": spend, "commission": commission, "roi_pct": None, "profit": commission}
    profit = commission - spend
    roi_pct = (profit / spend) * 100
    return {
        "spend": spend,
        "commission": commission,
        "profit": round(profit, 2),
        "roi_pct": round(roi_pct, 2),
    }
