import { BskyAgent } from '@atproto/api';
import fs from 'fs';
import path from 'path';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';
import { getOAuthAgent } from '../auth/bluesky-oauth.js';
import { dataPath } from '../utils/datadir.js';

const SESSION_FILE    = dataPath('bsky-session.json');
const RATELIMIT_FILE  = dataPath('bsky-ratelimit.json');
const SESSION_TTL_MS  = 90 * 60 * 1000;
const RATELIMIT_COOLDOWN_MS = 15 * 60 * 1000; // wait 15 min after rate limit

let agent        = null;
let sessionExpiry = 0;

function saveSession(sess) {
  try {
    fs.mkdirSync(path.dirname(SESSION_FILE), { recursive: true });
    fs.writeFileSync(SESSION_FILE, JSON.stringify(sess));
  } catch {}
}

function loadSession() {
  try { return JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8')); }
  catch { return null; }
}

function setRateLimit() {
  try {
    fs.mkdirSync(path.dirname(RATELIMIT_FILE), { recursive: true });
    fs.writeFileSync(RATELIMIT_FILE, JSON.stringify({ until: Date.now() + RATELIMIT_COOLDOWN_MS }));
  } catch {}
}

function isRateLimited() {
  try {
    const { until } = JSON.parse(fs.readFileSync(RATELIMIT_FILE, 'utf8'));
    if (Date.now() < until) {
      logger.warn(`Bluesky login rate-limited — skipping until ${new Date(until).toISOString()}`);
      return true;
    }
    fs.unlinkSync(RATELIMIT_FILE);
  } catch {}
  return false;
}

export async function getBskyAgent(forceRefresh = false) {
  if (forceRefresh) {
    agent = null;
    sessionExpiry = 0;
    try { fs.unlinkSync(SESSION_FILE); } catch {}
  }

  if (agent && Date.now() < sessionExpiry) return agent;

  // 1. Try OAuth session first
  const oauthSession = await getOAuthAgent();
  if (oauthSession) {
    agent = oauthSession;
    sessionExpiry = Date.now() + SESSION_TTL_MS;
    logger.info('Bluesky authenticated via OAuth');
    return agent;
  }

  // 2. Fall back to app password
  const { BSKY_HANDLE, BSKY_APP_PASSWORD } = process.env;
  if (!BSKY_HANDLE || !BSKY_APP_PASSWORD) {
    throw new Error('Bluesky not connected — use the dashboard to connect via OAuth or set BSKY_HANDLE + BSKY_APP_PASSWORD');
  }

  // Skip if we're in rate limit cooldown
  if (isRateLimited()) {
    throw new Error('Bluesky login rate-limited — waiting for cooldown, will retry next run');
  }

  const handle   = BSKY_HANDLE.trim();
  const password = BSKY_APP_PASSWORD.trim();
  const freshAgent = new BskyAgent({ service: 'https://bsky.social' });

  // Try resuming a saved session first
  const saved = loadSession();
  if (saved) {
    try {
      await freshAgent.resumeSession(saved);
      agent = freshAgent;
      sessionExpiry = Date.now() + SESSION_TTL_MS;
      logger.info(`Bluesky session resumed for ${handle}`);
      return agent;
    } catch (err) {
      logger.warn(`Bluesky session resume failed: ${err.message} — falling back to login`);
    }
  }

  logger.info(`Bluesky login: identifier="${handle}" password_length=${password.length}`);

  try {
    await freshAgent.login({ identifier: handle, password });
    saveSession(freshAgent.session);
    agent = freshAgent;
    sessionExpiry = Date.now() + SESSION_TTL_MS;
    logger.info(`Bluesky authenticated as ${handle}`);
    return agent;
  } catch (err) {
    if (/rate.limit/i.test(err.message)) {
      setRateLimit();
      logger.warn(`Bluesky rate limited — cooldown set for ${RATELIMIT_COOLDOWN_MS / 60000} min`);
    }
    throw err;
  }
}

export async function getBskySession() {
  const a = await getBskyAgent();
  return {
    did: a.session?.did,
    jwt: a.session?.accessJwt,
  };
}
