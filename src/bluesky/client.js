import { BskyAgent } from '@atproto/api';
import { logger } from '../utils/logger.js';

let agent = null;

export async function getBskyAgent() {
  if (agent) return agent;

  const { BSKY_HANDLE, BSKY_APP_PASSWORD } = process.env;
  if (!BSKY_HANDLE || !BSKY_APP_PASSWORD) {
    throw new Error('Missing BSKY_HANDLE or BSKY_APP_PASSWORD');
  }

  agent = new BskyAgent({ service: 'https://bsky.social' });

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      await agent.login({ identifier: BSKY_HANDLE, password: BSKY_APP_PASSWORD });
      logger.info(`Bluesky authenticated as ${BSKY_HANDLE}`);
      return agent;
    } catch (err) {
      logger.warn(`Bluesky login attempt ${attempt} failed: ${err.message}`);
      if (attempt < 3) await sleep(attempt * 2000);
      else throw err;
    }
  }
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
