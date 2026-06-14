# CLAUDE.md — Auto-Affiliate Bot

## What this project is
FastAPI backend (`api/`) + single-page dashboard (`src/dashboard.html`).
Runs on HuggingFace Spaces (port 7860). Posts affiliate products to Bluesky,
Mastodon, X, Instagram, Facebook, Threads, Tumblr via a scheduled pipeline.

## Stack
- **Backend:** Python 3.11, FastAPI, APScheduler, httpx
- **AI:** Groq / Mistral (text generation via `api/ai/text.py`)
- **Affiliate feeds:** SOVRN → TakeAds → Admitad → Travelpayouts (priority order)
- **Tests:** pytest, pytest-asyncio, playwright (E2E)
- **Linter:** ruff

## Key files
| File | Purpose |
|---|---|
| `api/main.py` | All FastAPI routes |
| `api/pipeline.py` | Core posting pipeline — `run_pipeline()` |
| `api/feeds/` | One file per affiliate network |
| `api/utils/circuit_breaker.py` | `CircuitBreaker` + `AuthError` |
| `api/utils/settings.py` | Persistent settings with `DEFAULTS` dict |
| `api/utils/metrics.py` | Run history, dedup, click tracking |
| `api/social_post.py` | Per-platform posting logic |
| `src/dashboard.html` | Entire frontend (single file) |
| `api/tests/e2e/` | Playwright browser tests |
| `core/orchestrator.py` | Runs only tests for changed files |
| `scripts/pattern_detector.py` | Detects API response shape drift |

## Rules that matter
- **`AuthError(RuntimeError)`** — permanent credential failures (403, not connected).
  Never trips the circuit breaker. Use it instead of plain `RuntimeError` in social_post.py.
- **`_find_image()` returns `(bytes, url)`** — bytes for Bluesky/Mastodon/X,
  url for Instagram/Facebook/Threads (Meta fetches server-side).
- **DEFAULTS in settings.py** — every key the frontend reads must exist here
  or GET /api/settings will have an unstable shape.
- **Never commit real credentials.** `rzekl.com` affiliate wrapper and
  `aff_short_key` must be preserved in Admitad links.
- **Branch:** `claude/zealous-carson-oMr43` — always develop and push here.

## Session start gate
`api/tests/test_qa_suite.py` + `test_qa_intelligent.py` run automatically.
95 checks must pass before feature work. Do not break this gate.

## Before every task
1. State what you're attempting and the success criteria.
2. Make the change.
3. Run the relevant test: `pytest api/tests/` or `python core/orchestrator.py`.
4. End with: **Done: X. Blocked: Y. Why: Z.**
