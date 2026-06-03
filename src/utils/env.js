const REQUIRED = [
  'ADMITAD_CLIENT_ID',
  'ADMITAD_CLIENT_SECRET',
  'BSKY_HANDLE',
  'BSKY_APP_PASSWORD',
];

const OPTIONAL_LABELS = {
  DEEPSEEK_API_KEY: 'DeepSeek text generation (will use template fallback)',
  HF_API_TOKEN: 'HuggingFace upscaling (images will not be upscaled)',
  LANGSEARCH_API_KEY: 'LangSearch image search (og:image scrape fallback only)',
  OPENAI_API_KEY: 'DALL-E image generation (unused in v2, kept for compatibility)',
};

export function validateEnv() {
  const missing = REQUIRED.filter(k => !process.env[k]);
  if (missing.length) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }

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
}

function isValidCron(expr) {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return false;
  // Permissive check: each field must be non-empty and composed of valid cron chars
  return parts.every(p => /^[\d\*\/,\-]+$/.test(p));
}
