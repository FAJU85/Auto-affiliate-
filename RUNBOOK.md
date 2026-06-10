# Auto-Affiliate Pipeline — Runbook

Maintained by: SRE duty cycle  
Space URL: https://vooom-fast-growth.hf.space  
Branch: claude/zealous-carson-oMr43

---

## 1. Run the Pipeline Manually

### Via dashboard (preferred)
1. Open https://vooom-fast-growth.hf.space
2. Click **"Run now"** on the dashboard home page.
3. Watch the run log appear in the Logs tab within 30 seconds.

### Via API
```bash
curl -X POST https://vooom-fast-growth.hf.space/api/run
# Returns: {"ok":true,"message":"Run triggered"}
# 409 = already running, 503 = not configured
```

### Via CLI (local dev)
```bash
cd /home/user/Auto-affiliate-
node -e "import('./src/pipeline/run.js').then(m => m.runPipeline())"
```

---

## 2. Reset a Circuit Breaker

This app uses Node.js in-memory state — there are no explicit circuit breakers.
To reset after a feed failure:

1. Check which network failed: `GET /api/networks`
2. If a network is showing errors, verify its env var is set: `GET /api/env-status`
3. For Bluesky auth failures: restart or call `POST /api/accounts/bluesky/disconnect` and reconnect
4. For transient network errors: wait for the next scheduled run (errors auto-clear)
5. To force a fresh run after fixing: `POST /api/run`

---

## 3. Check Metrics / SLO

### Quick health check
```bash
curl https://vooom-fast-growth.hf.space/health
# Returns: {"status":"ok","successRate":"85%","hoursSinceLastSuccess":2,...}
```

### Full SLO stats (rolling 24h window, 90% target)
```bash
curl https://vooom-fast-growth.hf.space/api/status | jq '.stats'
```

### Recent run history
```bash
curl https://vooom-fast-growth.hf.space/api/history?n=20
```

### SLO calculation
- **Target**: 90% success rate (configurable via dashboard Settings → `sloTarget`)
- **Window**: 24 hours rolling
- **Error budget**: 10% of runs allowed to fail per 24h
- **Budget used**: `failures / (total * 0.10) * 100%`
- Example: 100 runs, 15 failed → budget used = 150% (exhausted, investigate)

### CSV export (for offline analysis)
```bash
curl https://vooom-fast-growth.hf.space/api/history/csv -o pipeline-history.csv
```

---

## 4. Fix Common Errors

### X (Twitter) 403
Not applicable — this bot posts to Bluesky only. If you see 403 in logs, it
is from the FastAPI social-post proxy. Check `GET /api/social/status` for
OAuth token expiry. Re-authenticate via the Accounts page in the dashboard.

### Mastodon image upload fail
1. Check logs: `GET /api/logs`
2. Image may exceed Mastodon's 8 MB limit — the upscaler can produce large files.
3. Temporary fix: set `SKIP_IMAGE_UPSCALE=true` in HF Space secrets.
4. Permanent fix: ensure `upscaleImage()` returns a buffer ≤ 8 MB.

### SOVRN 400 / link not monetized
Symptom: logs show `SOVRN link API 400` or monetized URL === original URL.

1. Verify `SOVRN_API_KEY` is set in HF Space secrets.
2. The API URL must use `out=<encoded-url>` (not `u=`). This was fixed 2026-06-10.
3. Test monetization:
   ```bash
   curl "https://api.viglink.com/api/link?key=YOUR_KEY&out=https%3A%2F%2Famazon.com%2Fdp%2FB09XS7JWHH"
   ```
4. If the response `url` field equals the input URL, the key may be invalid or
   the merchant is not in SOVRN's network.

### Admitad feed empty / 0 offers parsed
1. Check `ADMITAD_FEED_URL` is set and not expired.
2. The feed is streamed up to 2 MB — if all products are in the first 2 MB, this
   is fine. If the feed is entirely non-Latin, all offers will be filtered out.
3. Test: `curl "$ADMITAD_FEED_URL" | head -c 500` — should show `<yml_catalog>`.

### Bluesky rate limit (createSession 429)
The session is persisted to `data/bsky-session.json`. After a 429, a 15-minute
cooldown file is written to `data/bsky-ratelimit.json`.
- Do NOT manually trigger runs during the cooldown window.
- The cooldown auto-clears after 15 minutes.
- If the session file is corrupted: delete `data/bsky-session.json` and restart.

### Groq rate limit (14,400 req/day)
The bot uses ~1 API call per pipeline run. At 24 runs/day, daily usage is well
within the free tier limit. If you see `429` from Groq:
1. The pipeline auto-falls back to Mistral (if `MISTRAL_API_KEY` is set).
2. If both fail, it uses a template fallback (never blocks posting).
3. Check Groq dashboard for quota usage: https://console.groq.com

---

## 5. DR: Persistent Data in /data/

The HF Space mounts a persistent volume at `/data/`. All state lives here.

| File | Contents | Restore procedure |
|------|----------|-------------------|
| `data/metrics.json` | Last 500 pipeline run records | Delete to reset history; will be recreated on next run |
| `data/budget.json` | Daily AI spend tracker (resets at UTC midnight) | Delete to reset today's spend counter |
| `data/posted-products.json` | 60-day dedup store (prevents re-posting same product) | Delete to allow re-posting all products |
| `data/caption-cache.json` | Per-product AI caption cache (1 day TTL) | Delete to force caption regeneration on next run |
| `data/bsky-session.json` | Bluesky auth session (refreshed every 90 min) | Delete to force re-login on next run |
| `data/bsky-ratelimit.json` | Bluesky rate limit cooldown timestamp | Delete to lift the 15-min cooldown early |
| `data/settings.json` | Pipeline settings (cost caps, schedule, SLO target) | Delete to reset to defaults; or restore from `PIPELINE_SETTINGS` env secret |

### Full restore after container rebuild
Settings are persisted to both `/data/settings.json` AND the HF secret
`PIPELINE_SETTINGS`. On startup, if `/data/` is empty, the code reads
`PIPELINE_SETTINGS` and re-writes the file. No manual action needed.

### Backup run history off-space
```bash
curl https://vooom-fast-growth.hf.space/api/history/csv -o backup-$(date +%Y%m%d).csv
```

---

## 6. Useful API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health gate — returns 200/503 |
| `/api/status` | GET | Full dashboard payload |
| `/api/run` | POST | Trigger a manual pipeline run |
| `/api/settings` | GET/POST | Read/update pipeline settings |
| `/api/history` | GET | Recent run records (`?n=N`) |
| `/api/history/csv` | GET | CSV export of all runs |
| `/api/logs` | GET | Recent log lines (`?n=N`) |
| `/api/networks` | GET | Per-network status and error info |
| `/api/dedup` | GET | Dedup store status |
| `/api/dedup` | DELETE | Clear dedup store |
| `/api/dry-run` | POST | Fetch product + generate caption without posting |
| `/api/debug` | GET | Env var + last run diagnostics |
| `/api/schedule/pause` | POST | Pause the cron scheduler |
| `/api/schedule/resume` | POST | Resume the cron scheduler |
