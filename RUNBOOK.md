# Auto-Affiliate Pipeline — Runbook

Maintained by: SRE duty cycle  
Space URL: https://vooom-fast-growth.hf.space  
Branch: claude/zealous-carson-oMr43  
Last updated: 2026-06-10

---

## 1. Run the Pipeline Manually

### Via dashboard (preferred)
1. Open https://vooom-fast-growth.hf.space (login with `DASHBOARD_PASSWORD`)
2. Click **"Run now"** on the dashboard home page.
3. Watch the run log appear in the Logs tab within 30 seconds.

### Via API (requires auth if DASHBOARD_PASSWORD is set)
```bash
curl -X POST https://vooom-fast-growth.hf.space/api/run \
  -H "Authorization: Bearer YOUR_DASHBOARD_PASSWORD"
# Returns: {"ok":true,"message":"Run triggered"}
# 409 = already running
```

---

## 2. Circuit Breakers

The app has 10 in-process circuit breakers (bluesky, groq, mistral, sovrn, mastodon, x, threads, tumblr, facebook, instagram).

```bash
# Check all breaker states
curl https://vooom-fast-growth.hf.space/health | jq '.circuit_breakers'

# Reset a specific breaker (requires auth)
curl -X POST https://vooom-fast-growth.hf.space/api/circuit-breakers/bluesky/reset \
  -H "Authorization: Bearer YOUR_DASHBOARD_PASSWORD"

# Reset all breakers
curl -X POST https://vooom-fast-growth.hf.space/api/circuit-breakers/reset-all \
  -H "Authorization: Bearer YOUR_DASHBOARD_PASSWORD"
```

Breaker opens after N consecutive failures; auto-closes after recovery_timeout seconds.

---

## 3. SLO & Error Budget

```bash
# Quick health (public, no auth)
curl https://vooom-fast-growth.hf.space/health
# Returns: slo_pct, error_budget_remaining_pct, circuit_breakers, pipeline_running

# Detailed SLO (requires auth)
curl https://vooom-fast-growth.hf.space/api/slo \
  -H "Authorization: Bearer YOUR_DASHBOARD_PASSWORD"
```

**KPIs:**
- SLO target: 90% successful runs (500-run rolling window)
- Error budget: 10% failure rate allowed
- If budget hits 0%: circuit breaker activates — halt feature deploys, fix stability

### Reset SLO baseline after fixing a systematic failure
```bash
curl -X POST https://vooom-fast-growth.hf.space/api/slo/reset \
  -H "Authorization: Bearer YOUR_DASHBOARD_PASSWORD"
# Clears run history so fresh SLO calculation starts from zero
```

---

## 4. Dedup Store

Products are deduped for 24 hours by default (configurable via `DEDUP_TTL_HOURS` env var).
With 55 products posting hourly, the catalog cycles cleanly within the 24h window.

```bash
# Check dedup status (requires auth)
curl https://vooom-fast-growth.hf.space/api/dedup \
  -H "Authorization: Bearer YOUR_DASHBOARD_PASSWORD"

# Clear dedup store (allows re-posting all products immediately)
curl -X POST https://vooom-fast-growth.hf.space/api/dedup/reset \
  -H "Authorization: Bearer YOUR_DASHBOARD_PASSWORD"
```

---

## 5. Fix Common Errors

### X (Twitter) 403
The app's Twitter credentials require "Read and Write" OAuth 1.0a permission.
1. Go to https://developer.twitter.com → your app → Settings → User authentication settings
2. Enable OAuth 1.0a with Read+Write permissions
3. Regenerate Access Token & Secret
4. Update `X_ACCESS_TOKEN` and `X_ACCESS_TOKEN_SECRET` in HF Space secrets

### Mastodon: "Auto Affiliate Bot" label on posts
The OAuth app name appears as the post author badge.
1. Go to mastodon.social/settings/applications
2. Rename the app to something neutral (e.g. your account name)

### SOVRN 400 / link not monetized
Fixed 2026-06-10: API URL now uses `out=` parameter (not `u=`).
If still broken: verify `SOVRN_API_KEY` is set in HF Space secrets.

### Bluesky rate limit (429)
Rate limit auto-respected — the app stores the reset timestamp and blocks login until clear.
Do NOT manually trigger runs during cooldown (cooldown auto-clears).

### Groq rate limit (429)
Pipeline auto-falls back to Mistral, then to template text. Never blocks posting.
Check Groq dashboard: https://console.groq.com

### AI circuit breaker trips on 429
Fixed 2026-06-10: 429s now trigger exponential backoff (up to 3×, max 30s) before counting as a failure.

### All pipeline runs failing ("Product already posted recently")
Root cause: DEDUP_TTL_HOURS too long (was 168h). Fixed 2026-06-10 to 24h default.
Recovery: call `/api/slo/reset` to clear bad run history after fix deploys.

---

## 6. DR: Persistent Data

The HF Space mounts a persistent volume at `/data/`. All runtime state lives here.

| File | Contents | Restore procedure |
|------|----------|-------------------|
| `metrics.json` | Last 500 pipeline run records | Call `/api/slo/reset` to clear |
| `budget.json` | Daily AI spend tracker | Resets at UTC midnight automatically |
| `settings.json` | Pipeline settings | Restored from `PIPELINE_SETTINGS` env secret on restart |
| `bsky-ratelimit.json` | Bluesky rate limit cooldown | Delete to lift early |

**WORM backup:** Run history exports available via:
```bash
curl https://vooom-fast-growth.hf.space/api/history/csv \
  -H "Authorization: Bearer YOUR_DASHBOARD_PASSWORD" \
  -o backup-$(date +%Y%m%d).csv
```

**Full container rebuild:** Settings auto-restore from `PIPELINE_SETTINGS` HF secret. No manual action needed. Dedup store and run history are lost but non-critical.

**DR Game Day:** Recommended quarterly — rebuild the Space from scratch and verify all env secrets restore correctly.

---

## 7. API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | None | Public health — returns SLO, budget, circuit breakers |
| `/api/run` | POST | Bearer | Trigger manual pipeline run |
| `/api/slo` | GET | Bearer | SLO + error budget details |
| `/api/slo/reset` | POST | Bearer | Purge run history (resets SLO baseline) |
| `/api/logs` | GET | Bearer | Recent log lines |
| `/api/settings` | GET/POST | Bearer | Read/update pipeline settings |
| `/api/history` | GET | Bearer | Recent run records |
| `/api/history/csv` | GET | Bearer | CSV export |
| `/api/dedup` | GET | Bearer | Dedup store status |
| `/api/dedup/reset` | POST | Bearer | Clear dedup store |
| `/api/circuit-breakers/{name}/reset` | POST | Bearer | Reset named circuit breaker |
| `/api/circuit-breakers/reset-all` | POST | Bearer | Reset all circuit breakers |
| `/r/{id}` | GET | None | Public affiliate redirect (must stay public) |

---

## 8. Post-Mortem — SLO Collapse 2026-06-10

**Incident:** SLO dropped to 58.25%, error budget exhausted (0% remaining).

**Impact:** ~41.75% of pipeline runs failing for an estimated 2–4 days. Zero affiliate link posts during failure windows. No user-facing outage (redirect links and dashboard remained accessible).

**Root cause:** `DEDUP_TTL_HOURS` defaulted to 168 hours (7 days). The product pool contains 55 products. With hourly posts, all 55 products were exhausted in ~2.3 days. After exhaustion, `sovrn._pick_product()` logged a warning and returned a random fallback product, but the pipeline-level dedup guard caught this and recorded every subsequent run as `success: False`. The SLO window (last 500 runs) filled with failures.

**Contributing factor:** The pipeline dedup guard used the same 168h TTL as the sovrn-level guard, making both layers equally strict. When sovrn fell back gracefully, the pipeline cancelled the work anyway.

**Fix (deployed 2026-06-10 commit 6c768d9):**
1. Reduced default `DEDUP_TTL_HOURS` from 168h to 24h
2. Pipeline-level dedup now uses a 1-hour hard block (prevents exact repeat within a session only)
3. Added `POST /api/slo/reset` endpoint to clear run history after fixing systematic failures
4. Added `clear_run_history()` to metrics module

**Action items:**
- [ ] After fix deploys: call `POST /api/slo/reset` to clear bad history and restart SLO baseline — owner: operator — deadline: immediately after deploy
- [ ] Expand product pool beyond 55 items to increase catalog diversity — owner: product — deadline: next cycle
- [ ] Add monitoring alert when SLO drops below 80% (warn) and 70% (page) — owner: SRE — deadline: next duty cycle

**Detection time (MTTD):** ~3 days (no alerting on SLO degradation)
**Fix time (MTTR):** <30 minutes once root cause identified

**Toil reduction:** Added `/api/slo/reset` endpoint so future systematic failures can be recovered with a single API call instead of manual `/data/metrics.json` surgery.
