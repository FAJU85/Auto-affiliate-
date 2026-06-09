import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

const TOKEN_URL = 'https://api.admitad.com/token/';

let cachedToken = null;
let tokenExpiry  = 0;
let refreshPromise = null;

export function invalidateAdmitadToken() {
  cachedToken = null;
  tokenExpiry  = 0;
}

export function getAdmitadToken() {
  if (cachedToken && Date.now() < tokenExpiry - 60_000) return Promise.resolve(cachedToken);
  if (refreshPromise) return refreshPromise;
  refreshPromise = _fetchToken().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function _fetchToken() {
  const { ADMITAD_CLIENT_ID, ADMITAD_CLIENT_SECRET } = process.env;
  if (!ADMITAD_CLIENT_ID || !ADMITAD_CLIENT_SECRET) {
    throw new Error('Missing ADMITAD_CLIENT_ID or ADMITAD_CLIENT_SECRET');
  }

  // Admitad OAuth2 requires client_id:client_secret as Basic Auth header.
  // deeplink_generator scope needs explicit approval — fall back to core scopes if denied.
  const basicAuth = 'Basic ' + Buffer.from(`${ADMITAD_CLIENT_ID}:${ADMITAD_CLIENT_SECRET}`).toString('base64');
  const scopes = [
    process.env.ADMITAD_SCOPE || 'public_data advcampaigns deeplink_generator',
    'public_data advcampaigns',
  ];

  let lastError;
  for (const scope of scopes) {
    const body = new URLSearchParams({ grant_type: 'client_credentials', client_id: ADMITAD_CLIENT_ID, scope });
    logger.info(`Admitad OAuth: requesting token with scope="${scope}"`);
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const res = await fetch(TOKEN_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': basicAuth,
          },
          body,
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`Admitad auth failed ${res.status}: ${text}`);
        }

        const data = await res.json();
        cachedToken = data.access_token;
        tokenExpiry  = Date.now() + (parseInt(data.expires_in, 10) || 3600) * 1000;
        logger.info(`Admitad OAuth token obtained (scope="${scope}"), expires in ${data.expires_in}s`);
        return cachedToken;
      } catch (err) {
        lastError = err;
        logger.warn(`Admitad OAuth attempt ${attempt} (scope=${scope}) failed: ${err.message}`);
        if (attempt < 3) await sleep(attempt * 2000);
      }
    }
    logger.warn(`Admitad OAuth: scope "${scope}" failed, trying fallback scope`);
  }
  throw lastError;
}
