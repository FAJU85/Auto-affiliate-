---
title: Auto Affiliate Pipeline
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
app_port: 7860
---

# Autonomous Affiliate Marketing Pipeline

Hourly pipeline: **multi-network affiliate feeds** → **HuggingFace Qwen2.5-72B** captions → **HuggingFace** image upscaling → **Bluesky** posts.

Supported affiliate networks: **Admitad XML feed**, **Takeads** (CPC). At least one must be configured.

## Status dashboard

Visit the Space URL to see live pipeline status, daily spend, and recent post history.

## Environment variables (set in Space Settings → Variables)

| Variable | Required | Description |
|---|---|---|
| `BSKY_HANDLE` | ✅ | Bluesky handle (e.g. `you.bsky.social`) |
| `BSKY_APP_PASSWORD` | ✅ | Bluesky app password |
| `ADMITAD_FEED_URL` | ⭐ at least one | Full Admitad XML feed URL (from webmaster panel, includes auth params) |
| `TAKEADS_API_KEY` | ⭐ at least one | Takeads CPC network API key |
| `HF_API_TOKEN` | ⭐ recommended | Text generation (Qwen2.5-72B → Mistral-7B) + image upscaling |
| `LANGSEARCH_API_KEY` | optional | Image search fallback |
| `DAILY_COST_CAP_USD` | optional | Default: `2.00` |
| `CRON_SCHEDULE` | optional | Default: `0 * * * *` (hourly) |

## Cost

$0.00/day — 100% free HuggingFace Inference API (community tier).

## Architecture

```
Affiliate feeds (parallel):
  ├─ Admitad XML feed → parse YML catalog → top 5 by commissionRate → random pick
  └─ Takeads API      → top 5 by commission → random pick
  → Pick one network at random from available results
  → Google Trends RSS context
  → 2-min rate limit wait
  → HF Qwen2.5-72B-Instruct caption (<200 chars, Mistral-7B fallback)
  → Image: feed image → LangSearch → og:image scrape
  → HF stable-diffusion-x4-upscaler
  → Bluesky AT Protocol publish (affiliate URL from feed = deeplink, no extra step)
```
