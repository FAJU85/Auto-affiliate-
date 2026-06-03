import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const TOKEN_URL = 'https://api.admitad.com/token/';

let cachedToken = null;
let tokenExpiry = 0;
let refreshPromise = null;

export function getAdmitadToken() {
  if (cachedToken && Date.now() < tokenExpiry - 60_000) return Promise.resolve(cachedToken);
  if (refreshPromise) return refreshPromise;

  refreshPromise = _fetchToken().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function _fetchToken() {
  const { ADMITAD_CLIENT_ID, ADMITAD_CLIENT_SECRET, ADMITAD_SCOPE } = process.env;
  if (!ADMITAD_CLIENT_ID || !ADMITAD_CLIENT_SECRET) {
    throw new Error('Missing ADMITAD_CLIENT_ID or ADMITAD_CLIENT_SECRET');
  }

  const body = new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: ADMITAD_CLIENT_ID,
    client_secret: ADMITAD_CLIENT_SECRET,
    scope: ADMITAD_SCOPE || 'advcampaigns banners deeplink',
  });

  let lastError;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(TOKEN_URL, { method: 'POST', body });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Admitad auth failed ${res.status}`);
      }
      const data = await res.json();
      cachedToken = data.access_token;
      tokenExpiry = Date.now() + data.expires_in * 1000;
      logger.info(`Admitad token obtained, expires in ${data.expires_in}s`);
      return cachedToken;
    } catch (err) {
      lastError = err;
      logger.warn(`Admitad auth attempt ${attempt} failed: ${err.message}`);
      if (attempt < 3) await sleep(attempt * 2000);
    }
  }
  throw lastError;
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
