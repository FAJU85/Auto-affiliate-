import { BskyAgent } from '@atproto/api';
import fs from 'fs';
import path from 'path';
import { logger } from '../utils/logger.js';
import { getOAuthAgent } from '../auth/bluesky-oauth.js';
import { dataPath } from '../utils/datadir.js';

const SESSION_FILE          = dataPath('bsky-session.json');
const RATELIMIT_FILE        = dataPath('bsky-ratelimit.json');
const SESSION_TTL_MS        = 90 * 60 * 1000;
const RATELIMIT_COOLDOWN_MS = 15 * 60 * 1000;

let agent         = null;
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

export function invalidateAgent() {
  agent = null;
  sessionExpiry = 0;
}

async function tryResumeSession(freshAgent, handle) {
  const saved = loadSession();
  if (!saved) return false;
  try {
    await freshAgent.resumeSession(saved);
    logger.info(`Bluesky session resumed for ${handle}`);
    return true;
  } catch (err) {
    logger.warn(`Bluesky session resume failed: ${err.message} — falling back to login`);
    return false;
  }
}

async function tryAppPasswordLogin(freshAgent, handle, password) {
  if (isRateLimited()) throw new Error('Bluesky login rate-limited — waiting for cooldown, will retry next run');
  logger.info(`Bluesky login: identifier="${handle}" password_length=${password.length}`);
  try {
    await freshAgent.login({ identifier: handle, password });
    saveSession(freshAgent.session);
    logger.info(`Bluesky authenticated as ${handle}`);
  } catch (err) {
    if (/rate.limit/i.test(err.message)) {
      setRateLimit();
      logger.warn(`Bluesky rate limited — cooldown set for ${RATELIMIT_COOLDOWN_MS / 60000} min`);
    }
    throw err;
  }
}

export async function getBskyAgent(forceRefresh = false) {
  if (forceRefresh) {
    invalidateAgent();
    try { fs.unlinkSync(SESSION_FILE); } catch {}
  }

  if (agent && Date.now() < sessionExpiry) return agent;

  const oauthSession = await getOAuthAgent();
  if (oauthSession) {
    agent = oauthSession;
    sessionExpiry = Date.now() + SESSION_TTL_MS;
    logger.info('Bluesky authenticated via OAuth');
    return agent;
  }

  const { BSKY_HANDLE, BSKY_APP_PASSWORD } = process.env;
  if (!BSKY_HANDLE || !BSKY_APP_PASSWORD) {
    throw new Error('Bluesky not connected — use the dashboard to connect via OAuth or set BSKY_HANDLE + BSKY_APP_PASSWORD');
  }

  const handle      = BSKY_HANDLE.trim();
  const password    = BSKY_APP_PASSWORD.trim();
  const freshAgent  = new BskyAgent({ service: 'https://bsky.social' });

  const resumed = await tryResumeSession(freshAgent, handle);
  if (!resumed) await tryAppPasswordLogin(freshAgent, handle, password);

  agent = freshAgent;
  sessionExpiry = Date.now() + SESSION_TTL_MS;
  return agent;
}

export async function getBskySession() {
  const a = await getBskyAgent();
  return { did: a.session?.did, jwt: a.session?.accessJwt };
}
