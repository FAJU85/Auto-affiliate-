import { BskyAgent } from '@atproto/api';
import fs from 'fs';
import path from 'path';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';
import { getOAuthAgent } from '../auth/bluesky-oauth.js';

const SESSION_FILE  = path.resolve('data/bsky-session.json');
const SESSION_TTL_MS = 90 * 60 * 1000;

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

export async function getBskyAgent(forceRefresh = false) {
  if (forceRefresh) {
    agent = null;
    sessionExpiry = 0;
    try { fs.unlinkSync(SESSION_FILE); } catch {}
  }

  if (agent && Date.now() < sessionExpiry) return agent;

  // 1. Try OAuth session first (one-click connect)
  const oauthSession = await getOAuthAgent();
  if (oauthSession) {
    // OAuth session is an AtpAgent-compatible object
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

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      await freshAgent.login({ identifier: handle, password });
      saveSession(freshAgent.session);
      agent = freshAgent;
      sessionExpiry = Date.now() + SESSION_TTL_MS;
      logger.info(`Bluesky authenticated as ${handle}`);
      return agent;
    } catch (err) {
      const isRateLimit = /rate.limit/i.test(err.message);
      logger.warn(`Bluesky login attempt ${attempt} failed: ${err.message}`);
      if (isRateLimit || attempt === 3) throw err;
      await sleep(attempt * 2000);
    }
  }
}

export async function getBskySession() {
  const a = await getBskyAgent();
  return {
    did: a.session?.did,
    jwt: a.session?.accessJwt,
  };
}
