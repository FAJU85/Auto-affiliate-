const REQUIRED = [
  'BSKY_HANDLE',
  'BSKY_APP_PASSWORD',
];

const OPTIONAL_LABELS = {
  ADMITAD_FEED_URL:     'Admitad XML product feed URL (no OAuth needed)',
  ADMITAD_CLIENT_ID:    'Admitad OAuth2 client ID (for API campaigns + deeplinks)',
  ADMITAD_CLIENT_SECRET:'Admitad OAuth2 client secret',
  ADMITAD_WEBSITE_ID:   'Admitad website/ad-space ID (enables deeplink generation)',
  TAKEADS_API_KEY:      'Takeads CPC network API key',
  TRAVELPAYOUTS_TOKEN:  'Travelpayouts API token (flight & hotel deals)',
  GROQ_API_KEY:         'Groq text generation — free, 14,400 req/day (llama-3.3-70b-versatile)',
  MISTRAL_API_KEY:      'Mistral text generation — mistral-small-latest fallback',
  HF_API_TOKEN:         'HuggingFace image upscaling (stable-diffusion-x4-upscaler)',
  LANGSEARCH_API_KEY:   'LangSearch image search (og:image scrape used as fallback)',
};

export function validateEnv() {
  // Startup diagnostic — shows what's actually received (names + lengths only)
  const allKeys = [...REQUIRED, ...Object.keys(OPTIONAL_LABELS)];
  for (const k of allKeys) {
    const v = process.env[k];
    if (v !== undefined) {
      console.log(`[ENV] ${k} set (length=${v.length}, first_char="${v[0]}")`);
    } else {
      console.log(`[ENV] ${k} NOT SET`);
    }
  }

  const missing = REQUIRED.filter(k => !process.env[k]);

  for (const [k, label] of Object.entries(OPTIONAL_LABELS)) {
    if (!process.env[k]) {
      console.warn(`[WARN] ${k} not set — ${label}`);
    }
  }

  const cap = parseFloat(process.env.DAILY_COST_CAP_USD || '2.00');
  const alert = parseFloat(process.env.ALERT_COST_THRESHOLD_USD || '1.50');
  if (alert >= cap) {
    throw new Error(`ALERT_COST_THRESHOLD_USD ($${alert}) must be less than DAILY_COST_CAP_USD ($${cap})`);
  }

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
