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

Hourly pipeline: **Admitad** product feed → **HuggingFace Qwen2.5-72B** captions → **HuggingFace** image upscaling → **Bluesky** posts.

## Status dashboard

Visit the Space URL to see live pipeline status, daily spend, and recent post history.

## Environment variables (set in Space Settings → Variables)

| Variable | Required | Description |
|---|---|---|
| `ADMITAD_CLIENT_ID` | ✅ | Admitad OAuth2 client ID |
| `ADMITAD_CLIENT_SECRET` | ✅ | Admitad OAuth2 client secret |
| `BSKY_HANDLE` | ✅ | Bluesky handle (e.g. `you.bsky.social`) |
| `BSKY_APP_PASSWORD` | ✅ | Bluesky app password |
| `HF_API_TOKEN` | ⭐ recommended | Text generation (Qwen2.5-72B → Mistral-7B) + image upscaling |
| `LANGSEARCH_API_KEY` | optional | Image search fallback |
| `DAILY_COST_CAP_USD` | optional | Default: `2.00` |
| `CRON_SCHEDULE` | optional | Default: `0 * * * *` (hourly) |

## Cost

$0.00/day — 100% free HuggingFace Inference API (community tier).

## Architecture

```
Admitad OAuth2 → Campaign feed (top 5 by ECPC, random pick)
  → Google Trends RSS context
  → 2-min rate limit wait
  → HF Qwen2.5-72B-Instruct caption (<200 chars, Mistral-7B fallback)
  → Image: Admitad logo → LangSearch → og:image scrape
  → HF stable-diffusion-x4-upscaler
  → Bluesky AT Protocol publish
```
