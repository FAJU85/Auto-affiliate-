import { NodeOAuthClient } from '@atproto/oauth-client-node';
import { Agent } from '@atproto/api';
import fs from 'fs';
import path from 'path';
import { getSpaceHost } from '../config/settings.js';
import { logger } from '../utils/logger.js';
import { dataPath } from '../utils/datadir.js';
import { writeSecret, deleteSecret } from '../utils/hf-secrets.js';

const STATE_DIR   = dataPath('oauth/state');
const SESSION_DIR = dataPath('oauth/sessions');

// HF secret key names — session and DID are backed up here after every connect
const SECRET_SESSION_KEY = 'BSKY_OAUTH_SESSION';
const SECRET_DID_KEY     = 'BSKY_OAUTH_DID';

function ensureDirs() {
  fs.mkdirSync(STATE_DIR,   { recursive: true });
  fs.mkdirSync(SESSION_DIR, { recursive: true });
}

// Restore session files from HF secrets if the data dir was wiped (Space rebuild)
export async function restoreSessionFromSecrets() {
  const did     = process.env[SECRET_DID_KEY];
  const session = process.env[SECRET_SESSION_KEY];
  if (!did || !session) return;

  ensureDirs();
  const sessionFile = path.join(SESSION_DIR, encodeURIComponent(did));
  if (fs.existsSync(sessionFile)) return; // already on disk, nothing to do

  try {
    const parsed = JSON.parse(session);
    fs.writeFileSync(sessionFile, JSON.stringify(parsed));
    logger.info(`Bluesky OAuth session restored from HF secret for ${did}`);
  } catch (err) {
    logger.warn(`Failed to restore Bluesky session from secret: ${err.message}`);
  }
}

// File-backed state store
const stateStore = {
  set(key, val) { ensureDirs(); fs.writeFileSync(path.join(STATE_DIR, key), JSON.stringify(val)); },
  get(key) {
    try { return JSON.parse(fs.readFileSync(path.join(STATE_DIR, key), 'utf8')); }
    catch { return undefined; }
  },
  del(key) { try { fs.unlinkSync(path.join(STATE_DIR, key)); } catch {} },
};

// File-backed session store — backs up to HF secret on every write
const sessionStore = {
  set(sub, val) {
    ensureDirs();
    fs.writeFileSync(path.join(SESSION_DIR, encodeURIComponent(sub)), JSON.stringify(val));
    // Persist to HF secrets so rebuild doesn't lose it
    writeSecret(SECRET_SESSION_KEY, JSON.stringify(val)).catch(() => {});
    writeSecret(SECRET_DID_KEY, sub).catch(() => {});
  },
  get(sub) {
    try { return JSON.parse(fs.readFileSync(path.join(SESSION_DIR, encodeURIComponent(sub)), 'utf8')); }
    catch { return undefined; }
  },
  del(sub) {
    try { fs.unlinkSync(path.join(SESSION_DIR, encodeURIComponent(sub))); } catch {}
    deleteSecret(SECRET_SESSION_KEY).catch(() => {});
    deleteSecret(SECRET_DID_KEY).catch(() => {});
  },
};

let _client = null;

export function getOAuthClient() {
  const host = getSpaceHost();
  if (!host) return null;
  if (_client) return _client;

  _client = new NodeOAuthClient({
    clientMetadata: {
      client_id:                  `${host}/client-metadata.json`,
      client_name:                'Auto Affiliate Pipeline',
      client_uri:                 host,
      redirect_uris:              [`${host}/oauth/callback`],
      scope:                      'atproto transition:generic',
      grant_types:                ['authorization_code', 'refresh_token'],
      response_types:             ['code'],
      token_endpoint_auth_method: 'none',
      application_type:           'web',
      dpop_bound_access_tokens:   true,
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
  for (const f of files) {
    const did = decodeURIComponent(f);
    sessionStore.del(did);
  }
  logger.info('Bluesky OAuth session disconnected');
}

export async function getOAuthAgent() {
  const client = getOAuthClient();
  if (!client) return null;
  const did = await getConnectedDid();
  if (!did) return null;
  try {
    const session = await client.restore(did);
    return new Agent(session);
  } catch (err) {
    logger.warn(`Bluesky OAuth restore failed: ${err.message}`);
    return null;
  }
}
