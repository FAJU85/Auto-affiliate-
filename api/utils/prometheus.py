"""Prometheus text-format metrics exporter.

Exposes all internal telemetry as Prometheus gauges/counters so Grafana
can scrape GET /metrics (or GET /api/metrics-prom) without any external
push gateway.

Format: https://prometheus.io/docs/instrumenting/exposition_formats/
"""



def _line(name: str, value: float, labels: dict | None = None, mtype: str | None = None, help_text: str | None = None) -> list[str]:
    lines = []
    if help_text:
        lines.append(f"# HELP {name} {help_text}")
    if mtype:
        lines.append(f"# TYPE {name} {mtype}")
    label_str = ""
    if labels:
        pairs = ",".join(f'{k}="{v}"' for k, v in labels.items())
        label_str = f"{{{pairs}}}"
    lines.append(f"{name}{label_str} {value}")
    return lines


def build_prometheus_output() -> str:
    """Collect all metrics and return a Prometheus-format text blob."""
    from . import budget as budget_util
    from . import metrics as metrics_util
    from .telemetry import golden_signals
    from .circuit_breaker import all_statuses as cb_statuses
    from .. import pipeline

    lines: list[str] = []

    # ── Pipeline ──────────────────────────────────────────────────────────────
    lines += _line("affiliate_pipeline_runs_total", pipeline.STATE["runCount"],
                   mtype="counter", help_text="Total pipeline run attempts since startup")
    lines += _line("affiliate_pipeline_success_total", pipeline.STATE["successCount"],
                   mtype="counter", help_text="Total successful pipeline runs since startup")
    lines += _line("affiliate_pipeline_running", int(pipeline.STATE["running"]),
                   mtype="gauge", help_text="1 if pipeline is currently executing")
    lines += _line("affiliate_pipeline_paused", int(pipeline.STATE["paused"]),
                   mtype="gauge", help_text="1 if pipeline is paused (rate-limit or manual)")

    # ── SLO / error budget ───────────────────────────────────────────────────
    slo = pipeline.calculate_slo(500)
    if slo.get("slo_pct") is not None:
        lines += _line("affiliate_slo_pct", slo["slo_pct"],
                       mtype="gauge", help_text="30-day SLO compliance percentage")
        lines += _line("affiliate_error_budget_remaining_pct", slo["error_budget_remaining_pct"],
                       mtype="gauge", help_text="Error budget remaining (0=exhausted)")
        lines += _line("affiliate_slo_target", slo["slo_target"],
                       mtype="gauge", help_text="SLO target percentage")
        lines += _line("affiliate_run_failures_total", slo.get("failures", 0),
                       mtype="counter", help_text="Total failed pipeline runs in window")

    # ── FinOps ────────────────────────────────────────────────────────────────
    spend = budget_util.get_daily_spend()
    from .settings import get_settings
    cap = float(get_settings().get("dailyCostCap", 2.0))
    lines += _line("affiliate_daily_spend_usd", round(spend, 6),
                   mtype="gauge", help_text="AI cost spent today (USD)")
    lines += _line("affiliate_daily_cost_cap_usd", cap,
                   mtype="gauge", help_text="Configured daily cost cap (USD)")
    lines += _line("affiliate_cost_budget_used_pct", round(spend / cap * 100, 2) if cap > 0 else 0,
                   mtype="gauge", help_text="Percentage of daily cost cap consumed")

    # ── Click tracking ────────────────────────────────────────────────────────
    total_clicks = metrics_util.get_total_clicks()
    lines += _line("affiliate_clicks_total", total_clicks,
                   mtype="counter", help_text="Total affiliate link clicks tracked")

    # ── Dedup ────────────────────────────────────────────────────────────────
    dedup = metrics_util.get_dedup_status() if hasattr(metrics_util, "get_dedup_status") else {}
    if dedup:
        lines += _line("affiliate_dedup_active", dedup.get("activeCount", dedup.get("count", 0)),
                       mtype="gauge", help_text="Products currently in dedup cache")
        lines += _line("affiliate_dedup_ttl_hours", dedup.get("ttlHours", 24),
                       mtype="gauge", help_text="Dedup TTL in hours")

    # ── Circuit breakers ─────────────────────────────────────────────────────
    lines += ["# HELP affiliate_circuit_breaker_open 1 if circuit breaker is open (tripped)",
              "# TYPE affiliate_circuit_breaker_open gauge"]
    lines += ["# HELP affiliate_circuit_breaker_failures Circuit breaker consecutive failure count",
              "# TYPE affiliate_circuit_breaker_failures gauge"]
    for cb in cb_statuses():
        name = cb["name"]
        is_open = 1 if cb["state"] == "open" else 0
        failures = cb.get("failures", 0)
        lines.append(f'affiliate_circuit_breaker_open{{breaker="{name}"}} {is_open}')
        lines.append(f'affiliate_circuit_breaker_failures{{breaker="{name}"}} {failures}')

    # ── Four Golden Signals (latency, traffic, errors, saturation) ────────────
    signals = golden_signals()

    lines += ["# HELP affiliate_latency_p50_ms Median latency per component (ms)",
              "# TYPE affiliate_latency_p50_ms gauge"]
    for comp, val in signals["latency_p50_ms"].items():
        lines.append(f'affiliate_latency_p50_ms{{component="{comp}"}} {round(val, 2)}')

    lines += ["# HELP affiliate_latency_p99_ms 99th-percentile latency per component (ms)",
              "# TYPE affiliate_latency_p99_ms gauge"]
    for comp, val in signals["latency_p99_ms"].items():
        lines.append(f'affiliate_latency_p99_ms{{component="{comp}"}} {round(val, 2)}')

    lines += ["# HELP affiliate_traffic_total Total calls per component since startup",
              "# TYPE affiliate_traffic_total counter"]
    for comp, val in signals["traffic_total"].items():
        lines.append(f'affiliate_traffic_total{{component="{comp}"}} {val}')

    lines += ["# HELP affiliate_error_rate_pct Error rate per component (last 1h, %)",
              "# TYPE affiliate_error_rate_pct gauge"]
    for comp, val in signals["error_rate_pct"].items():
        lines.append(f'affiliate_error_rate_pct{{component="{comp}"}} {val}')

    lines += ["# HELP affiliate_saturation_hits Rate-limit hits per component since startup",
              "# TYPE affiliate_saturation_hits counter"]
    for comp, val in signals["saturation_hits"].items():
        lines.append(f'affiliate_saturation_hits{{component="{comp}"}} {val}')

    lines.append("")  # trailing newline Prometheus expects
    return "\n".join(lines)
