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

Hourly pipeline: **Admitad** product feed → **Groq/Llama-3.3-70B** captions → **HuggingFace** image upscaling → **Bluesky** posts.

## Status dashboard

Visit the Space URL to see live pipeline status, daily spend, and recent post history.

## Environment variables (set in Space Settings → Variables)

| Variable | Required | Description |
|---|---|---|
| `ADMITAD_CLIENT_ID` | ✅ | Admitad OAuth2 client ID |
| `ADMITAD_CLIENT_SECRET` | ✅ | Admitad OAuth2 client secret |
| `BSKY_HANDLE` | ✅ | Bluesky handle (e.g. `you.bsky.social`) |
| `BSKY_APP_PASSWORD` | ✅ | Bluesky app password |
| `GROQ_API_KEY` | ⭐ recommended | Free text generation — [get one](https://console.groq.com) |
| `HF_API_TOKEN` | recommended | Image upscaling via stable-diffusion-x4-upscaler |
| `LANGSEARCH_API_KEY` | optional | Image search fallback |
| `DEEPSEEK_API_KEY` | optional | Paid text fallback if Groq unavailable |
| `DAILY_COST_CAP_USD` | optional | Default: `2.00` |
| `CRON_SCHEDULE` | optional | Default: `0 * * * *` (hourly) |

## Cost

~$0.00/day with Groq free tier. Only HuggingFace upscaling uses your `HF_API_TOKEN` (free community tier).

## Architecture

```
Admitad OAuth2 → Campaign feed (top 5 by ECPC, random pick)
  → Google Trends RSS context
  → 2-min rate limit wait
  → Groq llama-3.3-70b-versatile caption (<200 chars)
  → Image: Admitad logo → LangSearch → og:image scrape
  → HF stable-diffusion-x4-upscaler
  → Bluesky AT Protocol publish
```
