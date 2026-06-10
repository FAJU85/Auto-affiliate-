# Blameless Post-Mortem: Bluesky Posting Failures

**Date of incident:** 2026-06-10  
**Duration:** Multiple sessions (~weeks of failed scheduled posts)  
**Severity:** P2 — complete loss of posting capability  
**Status:** Resolved

---

## Summary

The auto-affiliate pipeline ran on schedule but produced zero Bluesky posts. Users saw "✗ Fail" badges on the dashboard with no error detail visible. Multiple root causes compounded: credential detection failures, byte-vs-grapheme truncation, and a broken tracking-URL builder.

---

## Timeline

| Time | Event |
|---|---|
| Session 1 | Pipeline deployed; first runs fail silently |
| Session 2 | Identified: `getBskyAgent()` throws if env vars missing even with OAuth configured |
| Session 2 | Fixed: unified agent tries OAuth → falls back to app-password |
| Session 3 | Still failing; identified: `publisher.js` sends `combined` (untruncated) as post text — Bluesky rejects >300 grapheme posts with 400 |
| Session 3 | Fixed: post record uses `truncated` string; facet offsets re-anchored via `lastIndexOf` |
| Session 3 | Fixed: `getSpaceHost()` built wrong URL from `SPACE_ID` (missing `.hf.space`) → broken tracking URLs |
| Session 4 | Rewrote backend to Python (atproto library) |
| Session 4 | Found: `bluesky_client.py:19` — `budget = GRAPHEME_LIMIT - len(suffix)` shadows module import and uses code-point length not graphemes |
| Session 5 | Fixed: proper grapheme counting, circuit breakers, timeouts, retry |

---

## Root Causes

### RC-1: Byte-based truncation exceeds Bluesky's grapheme limit
**File:** `src/bluesky/publisher.js` (JS backend, now replaced)  
**Impact:** Every post with >~270 bytes of caption silently failed with HTTP 400  
**Fix:** Use `Intl.Segmenter` for grapheme counting; Python replacement uses `unicodedata` + `regex`

### RC-2: Post record sent untruncated text
**File:** `src/bluesky/publisher.js:140`  
**Code:** `text: combined` instead of `text: truncated`  
**Impact:** Facet offsets calculated from truncated string but post body was the full untruncated string — guaranteed 400 for any long caption  
**Fix:** Changed to `text: truncated`

### RC-3: `getSpaceHost()` produced malformed URL
**File:** `src/config/settings.js`  
**Code:** `https://${SPACE_ID.replace('/', '-')}` → `https://owner-name` (missing `.hf.space`)  
**Impact:** Tracking URLs like `https://vooom-fast-growth/r/xyz` passed `isValidHttpUrl()` but were dead links; no clicks tracked  
**Fix:** Now correctly builds `https://owner-name.hf.space`

### RC-4: `budget` variable shadowed module import in Python client
**File:** `api/bluesky_client.py:19` (Python rewrite)  
**Code:** `budget = GRAPHEME_LIMIT - len(suffix)` — shadows `from .utils import budget`  
**Impact:** Would have caused `NameError` if budget util was ever called inside this scope  
**Fix:** Renamed variable; used `grapheme_budget`

### RC-5: Error messages not surfaced in dashboard
**File:** `src/dashboard.html` — Overview render never showed `lastRun.error`  
**Impact:** Operator (user) had no way to see what was failing without reading raw logs  
**Fix:** Added red error box under last-run stats; added `/api/debug` endpoint + "Debug Info" button in Logs tab

---

## Systemic Flaws

| Flaw | Description | Owner | Deadline |
|---|---|---|---|
| No grapheme validation tests | Unit tests only checked byte length | Engineering | Next sprint |
| Health endpoint returned `ok: true` always | Masked real failures from external monitors | Engineering | Done (Phase 2) |
| No circuit breaker on any external call | Cascading failures when Bluesky was slow | Engineering | Done (Phase 2) |
| No per-component latency tracking | Impossible to pinpoint which phase was slow | Engineering | Done (Phase 2) |
| CI/CD had no deploy health gate | Bad deploys reached production silently | Engineering | Done (Phase 3) |
| Error budget was never calculated | Couldn't quantify incident severity | Engineering | Done (Phase 4) |

---

## Action Items

| # | Action | Owner | Status | Deadline |
|---|---|---|---|---|
| 1 | Add grapheme-count unit tests to publisher | Engineering | Open | 2026-06-17 |
| 2 | Add E2E smoke test: post a real draft post | Engineering | Open | 2026-06-17 |
| 3 | Set up external uptime monitor (UptimeRobot / BetterStack) on `/health` | Ops | Open | 2026-06-14 |
| 4 | Add Bluesky credential validation on startup with clear error log | Engineering | Done | 2026-06-10 |
| 5 | DR Game Day: simulate Space rebuild + secrets loss | Ops | Open | 2026-06-24 |

---

## Cycle 2 Findings (2026-06-10 SRE Cycle 2)

### RC-6: Python bluesky_client.py created new session on every run
**File:** `api/bluesky_client.py`  
**Code:** `Client().login(handle, password)` called every `_post_sync()` invocation  
**Impact:** Bluesky `createSession` rate limit hit within first few hours of operation → auth failures → zero posts  
**Fix:** Session persistence to `/data/bsky-session.json`; in-memory 90-minute TTL; session resume via `login(session_string=...)` on subsequent runs

### RC-7: Dedup store had no TTL — all products blocked after 17 hours
**File:** `api/utils/metrics.py` — `was_recently_posted()` checked presence only, no timestamp  
**Impact:** With 17 products at hourly cron, all products exhausted in 17 runs → `"dedup skip"` on every subsequent run  
**Fix:** 7-day TTL (`DEDUP_TTL_HOURS=168` env var); timestamp comparison in `was_recently_posted()`

### RC-8: Dashboard `st.lastRun` was undefined — Last Run section always blank
**File:** `api/main.py` — `/api/status` put `lastRun` inside `pipeline` sub-object  
**Impact:** Dashboard `renderOverview()` reads `st.lastRun` (top-level) → always `undefined` → all Last Run fields showed `—`  
**Fix:** Also expose `lastRun` at top level of `/api/status` response

### RC-9: Logger returned plain strings; dashboard expected structured objects
**File:** `api/utils/logger.py` — `get_recent_logs()` returned `["[2026-...] [INFO] msg"]` strings  
**Impact:** Dashboard `filterLogs()` filters on `l.level === 'error'` → always 0; all log filtering broken  
**Fix:** Logger now returns `{ts, level, msg}` dicts

### RC-10: SOVRN random selection hit dedup-blocked products, wasting runs
**File:** `api/feeds/sovrn.py` — `random.choice(PRODUCT_POOL)` with no dedup awareness  
**Impact:** After several runs, randomly picking blocked products → pipeline aborts at dedup gate; wasted run  
**Fix:** Smart `_pick_product()` shuffles pool and returns first non-blocked product; pool expanded 17→59

### RC-11: SLO target 99.9% was unreachable by design
**File:** `api/pipeline.py` — `target = 99.9`  
**Impact:** Any single transient Bluesky/Groq API error depleted 100% error budget → circuit breaker always triggered → no meaningful error budget signal  
**Fix:** Target recalibrated to 90%; allows ~2-3 failures per day before budget action

### RC-12: `social_oauth.py` built malformed callback URLs from SPACE_ID
**File:** `api/social_oauth.py` — `get_base_url()` missing `.hf.space` suffix  
**Impact:** All OAuth callbacks (Mastodon, Threads, Tumblr) sent to `https://vooom-fast-growth` instead of `https://vooom-fast-growth.hf.space` → OAuth flows fail immediately  
**Fix:** Added `.hf.space` suffix; matches fix already applied to JS `getSpaceHost()`

---

## DR Readiness Status

| Item | Status |
|---|---|
| Settings backed up to HF Secrets (`PIPELINE_SETTINGS`) | ✓ Implemented |
| Bluesky session persisted to `/data/bsky-session.json` | ✓ Implemented (Cycle 2) |
| Metrics/run history (`/data/metrics.json`) | ⚠ Only persisted if HF volume mounted |
| Rollback: re-push previous commit to HF Space | ✓ Possible via git push |
| CI import gate + health gate | ✓ Implemented (Cycle 1) |
| Last DR Game Day | ✗ Never conducted |

**Next DR Game Day target:** 2026-06-24 — simulate: volume wipe + credential reset + fresh deploy
