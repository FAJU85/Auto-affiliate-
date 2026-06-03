import { BskyAgent } from '@atproto/api';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

// Bluesky access JWTs expire after ~2 hours; we re-login every 90 min
const SESSION_TTL_MS = 90 * 60 * 1000;

let agent = null;
let sessionExpiry = 0;

export async function getBskyAgent(forceRefresh = false) {
  if (forceRefresh) {
    agent = null;
    sessionExpiry = 0;
  }

  if (agent && Date.now() < sessionExpiry) return agent;

  const { BSKY_HANDLE, BSKY_APP_PASSWORD } = process.env;
  if (!BSKY_HANDLE || !BSKY_APP_PASSWORD) {
    throw new Error('Missing BSKY_HANDLE or BSKY_APP_PASSWORD');
  }

  const freshAgent = new BskyAgent({ service: 'https://bsky.social' });

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      await freshAgent.login({ identifier: BSKY_HANDLE, password: BSKY_APP_PASSWORD });
      agent = freshAgent;
      sessionExpiry = Date.now() + SESSION_TTL_MS;
      logger.info(`Bluesky authenticated as ${BSKY_HANDLE}`);
      return agent;
    } catch (err) {
      logger.warn(`Bluesky login attempt ${attempt} failed: ${err.message}`);
      if (attempt < 3) await sleep(attempt * 2000);
      else throw err;
    }
  }
}

/**
 * Returns the current session DID and JWT after login.
 */
export async function getBskySession() {
  const a = await getBskyAgent();
  return {
    did: a.session?.did,
    jwt: a.session?.accessJwt,
  };
}
