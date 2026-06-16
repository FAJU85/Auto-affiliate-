from datetime import datetime, timezone, timedelta


_PLATFORM_WEIGHT: dict[str, float] = {
    "instagram": 1.3,
    "facebook": 1.2,
    "threads": 1.1,
    "x": 1.0,
    "bluesky": 0.9,
    "mastodon": 0.9,
    "tumblr": 0.8,
    "default": 1.0,
}

_DECAY_HALF_LIFE_DAYS = 7.0


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _age_decay(posted_at: datetime, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    age_days = max((now - posted_at).total_seconds() / 86400, 0)
    return 0.5 ** (age_days / _DECAY_HALF_LIFE_DAYS)


def score_run(run: dict, now: datetime | None = None) -> float:
    if not run.get("success"):
        return 0.0
    clicks = max(int(run.get("clicks", 0)), 0)
    platform = (run.get("platform") or "default").lower()
    weight = _PLATFORM_WEIGHT.get(platform, _PLATFORM_WEIGHT["default"])
    ts = _parse_ts(run.get("timestamp", ""))
    decay = _age_decay(ts, now) if ts else 0.5
    return round(clicks * weight * decay, 4)


def top_engaged_runs(runs: list[dict], n: int = 10, now: datetime | None = None) -> list[dict]:
    scored = [
        {**r, "_engagement": score_run(r, now)}
        for r in runs
        if r.get("success")
    ]
    scored.sort(key=lambda x: x["_engagement"], reverse=True)
    return scored[:n]


def engagement_summary(runs: list[dict], days: int = 30, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    recent = [
        r for r in runs
        if r.get("success") and (_parse_ts(r.get("timestamp", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    ]
    scores = [score_run(r, now) for r in recent]
    total = round(sum(scores), 4)
    return {
        "period_days": days,
        "runs_counted": len(recent),
        "total_engagement": total,
        "avg_engagement": round(total / len(scores), 4) if scores else 0.0,
        "top_run": top_engaged_runs(recent, n=1, now=now)[0] if recent else None,
    }
