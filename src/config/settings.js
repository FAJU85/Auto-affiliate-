import fs from 'fs';
import path from 'path';

const SETTINGS_FILE = path.resolve('data/settings.json');

const DEFAULTS = {
  spaceHost:       '',   // e.g. https://vooom-fast-growth.hf.space
  cronSchedule:    '0 * * * *',
  maxPostLength:   300,
  dailyCostCap:    2.00,
  alertThreshold:  1.50,
  rateLimitWaitMs: 120000,
};

let _cache = null;

export function getSettings() {
  if (_cache) return _cache;
  try {
    const raw = JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf8'));
    _cache = { ...DEFAULTS, ...raw };
  } catch {
    _cache = { ...DEFAULTS };
  }
  return _cache;
}

export function saveSettings(updates) {
  const current = getSettings();
  _cache = { ...current, ...updates };
  fs.mkdirSync(path.dirname(SETTINGS_FILE), { recursive: true });
  const tmp = `${SETTINGS_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(_cache, null, 2));
  fs.renameSync(tmp, SETTINGS_FILE);
  return _cache;
}

export function getSpaceHost() {
  const s = getSettings();
  if (s.spaceHost) return s.spaceHost.replace(/\/$/, '');
  // Fall back to env var (set automatically in HF Spaces)
  const host = process.env.SPACE_HOST || process.env.SPACE_ID;
  if (host) return `https://${host.replace('/', '-').replace(/^https?:\/\//, '')}`;
  return '';
}
