const REQUIRED = [
  'ADMITAD_CLIENT_ID',
  'ADMITAD_CLIENT_SECRET',
  'BSKY_HANDLE',
  'BSKY_APP_PASSWORD',
];

const OPTIONAL_WITH_COST = [
  'OPENAI_API_KEY',
  'HF_API_TOKEN',
];

export function validateEnv() {
  const missing = REQUIRED.filter(k => !process.env[k]);
  if (missing.length) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }

  for (const k of OPTIONAL_WITH_COST) {
    if (!process.env[k]) {
      const label = k === 'OPENAI_API_KEY' ? 'DALL-E image generation' : 'Hugging Face text generation';
      console.warn(`[WARN] ${k} not set — ${label} will use fallback mode`);
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
