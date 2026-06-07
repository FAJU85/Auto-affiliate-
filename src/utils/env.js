import { getConnectedDid } from '../auth/bluesky-oauth.js';

const OPTIONAL_LABELS = {
  ADMITAD_FEED_URL:        'Admitad XML product feed URL (no OAuth needed)',
  ADMITAD_CLIENT_ID:       'Admitad OAuth2 client ID (for API campaigns + deeplinks)',
  ADMITAD_CLIENT_SECRET:   'Admitad OAuth2 client secret',
  ADMITAD_WEBSITE_ID:      'Admitad website/ad-space ID (enables deeplink generation)',
  ADMITAD_CATALOG_URL_1:   'Admitad catalog export URL 1 (JSON/XML feed)',
  ADMITAD_CATALOG_URL_2:   'Admitad catalog export URL 2 (JSON/XML feed)',
  ADMITAD_CATALOG_URL_3:   'Admitad catalog export URL 3 (JSON/XML feed)',
  ADMITAD_CATALOG_URL_4:   'Admitad catalog export URL 4 (JSON/XML feed)',
  ADMITAD_CATALOG_URL_5:   'Admitad catalog export URL 5 (JSON/XML feed)',
  TEMU_AFFILIATE_URL_1:    'Temu affiliate landing page link 1 (temu.to/k/...)',
  TEMU_AFFILIATE_URL_2:    'Temu affiliate landing page link 2 (temu.to/m/...)',
  TEMU_AFFILIATE_URL_3:    'Temu affiliate landing page link 3 (temu.to/k/...)',
  IMPACT_ACCOUNT_SID:      'Impact.com publisher Account SID (Settings → API)',
  IMPACT_AUTH_TOKEN:       'Impact.com publisher Auth Token (Settings → API)',
  CJ_API_KEY:              'CJ Affiliate personal access token (developers.cj.com → API Keys)',
  CJ_WEBSITE_ID:           'CJ Affiliate publisher CID / website ID (members.cj.com → Account)',
  SHAREASALE_TOKEN:        'ShareASale API token (Reports → API Reporting)',
  SHAREASALE_SECRET:       'ShareASale API secret key (same page as token)',
  SHAREASALE_AFFILIATE_ID: 'ShareASale affiliate/publisher ID (shown in account top-right)',
  TAKEADS_API_KEY:         'Takeads CPC network API key',
  TRAVELPAYOUTS_TOKEN:     'Travelpayouts API token (flight deals data)',
  TRAVELPAYOUTS_MARKER:    'Travelpayouts partner marker ID (for affiliate link tracking)',
  POSTING_HOURS:           'UTC hour window for auto-posts, format "start-end" e.g. "8-22" (default: 8-22)',
  GROQ_API_KEY:            'Groq text generation — free, 14 400 req/day (llama-3.3-70b-versatile)',
  MISTRAL_API_KEY:         'Mistral text generation — mistral-small-latest fallback',
  EXA_API_KEY:             'Exa web search — enriches AI captions with real product highlights',
  HF_TOKEN:                'HuggingFace token (image upscaling + secret persistence)',
};

export async function validateEnv() {
  // Show what is actually configured at startup
  const allKeys = [...Object.keys(OPTIONAL_LABELS), 'BSKY_HANDLE', 'BSKY_APP_PASSWORD'];
  for (const k of allKeys) {
    const v = process.env[k];
    if (v !== undefined) console.log(`[ENV] ${k} set (length=${v.length})`);
    else console.log(`[ENV] ${k} NOT SET`);
  }

  for (const [k, label] of Object.entries(OPTIONAL_LABELS)) {
    if (!process.env[k]) console.warn(`[WARN] ${k} not set — ${label}`);
  }

  // Bluesky: OK if OAuth session exists OR app-password vars are set
  const oauthDid = await getConnectedDid().catch(() => null);
  const bskyOk   = oauthDid || (process.env.BSKY_HANDLE && process.env.BSKY_APP_PASSWORD);
  const missing  = bskyOk ? [] : ['BSKY — connect via dashboard or set BSKY_HANDLE + BSKY_APP_PASSWORD'];

  const schedule = process.env.CRON_SCHEDULE || '0 * * * *';
  if (!isValidCron(schedule)) {
    throw new Error(`CRON_SCHEDULE "${schedule}" is not a valid 5-field cron expression`);
  }

  return missing;
}

function isValidCron(expr) {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return false;
  return parts.every(p => /^[\d\*\/,\-]+$/.test(p));
}
