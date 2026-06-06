import { NodeOAuthClient } from '@atproto/oauth-client-node';
import { Agent } from '@atproto/api';
import fs from 'fs';
import path from 'path';
import { getSpaceHost } from '../config/settings.js';
import { logger } from '../utils/logger.js';
import { dataPath } from '../utils/datadir.js';

const STATE_DIR   = dataPath('oauth/state');
const SESSION_DIR = dataPath('oauth/sessions');

function ensureDirs() {
  fs.mkdirSync(STATE_DIR,   { recursive: true });
  fs.mkdirSync(SESSION_DIR, { recursive: true });
}

// Simple file-backed state store
const stateStore = {
  set(key, val) { ensureDirs(); fs.writeFileSync(path.join(STATE_DIR, key), JSON.stringify(val)); },
  get(key) {
    try { return JSON.parse(fs.readFileSync(path.join(STATE_DIR, key), 'utf8')); }
    catch { return undefined; }
  },
  del(key) { try { fs.unlinkSync(path.join(STATE_DIR, key)); } catch {} },
};

// Simple file-backed session store (keyed by DID)
const sessionStore = {
  set(sub, val) { ensureDirs(); fs.writeFileSync(path.join(SESSION_DIR, encodeURIComponent(sub)), JSON.stringify(val)); },
  get(sub) {
    try { return JSON.parse(fs.readFileSync(path.join(SESSION_DIR, encodeURIComponent(sub)), 'utf8')); }
    catch { return undefined; }
  },
  del(sub) { try { fs.unlinkSync(path.join(SESSION_DIR, encodeURIComponent(sub))); } catch {} },
};

let _client = null;

export function getOAuthClient() {
  const host = getSpaceHost();
  if (!host) return null;

  if (_client) return _client;

  _client = new NodeOAuthClient({
    clientMetadata: {
      client_id:                    `${host}/client-metadata.json`,
      client_name:                  'Auto Affiliate Pipeline',
      client_uri:                   host,
      redirect_uris:                [`${host}/oauth/callback`],
      scope:                        'atproto transition:generic',
      grant_types:                  ['authorization_code', 'refresh_token'],
      response_types:               ['code'],
      token_endpoint_auth_method:   'none',
      application_type:             'web',
      dpop_bound_access_tokens:     true,
    },
    stateStore,
    sessionStore,
  });

  return _client;
}

export async function getConnectedDid() {
  ensureDirs();
  const files = fs.readdirSync(SESSION_DIR);
  return files.length > 0 ? decodeURIComponent(files[0]) : null;
}

export async function disconnectBluesky() {
  ensureDirs();
  const files = fs.readdirSync(SESSION_DIR);
  for (const f of files) fs.unlinkSync(path.join(SESSION_DIR, f));
  logger.info('Bluesky OAuth session disconnected');
}

export async function getOAuthAgent() {
  const client = getOAuthClient();
  if (!client) return null;
  const did = await getConnectedDid();
  if (!did) return null;
  try {
    const session = await client.restore(did);
    // Wrap the OAuth session in an Agent so .post() and .uploadBlob() work
    return new Agent(session);
  } catch (err) {
    logger.warn(`Bluesky OAuth restore failed: ${err.message}`);
    return null;
  }
}
