import fs from 'fs';
import path from 'path';
import { dataPath } from '../utils/datadir.js';
import { writeSecret } from '../utils/hf-secrets.js';

const SETTINGS_FILE   = dataPath('settings.json');
const SETTINGS_SECRET = 'PIPELINE_SETTINGS';

const DEFAULTS = {
  spaceHost:        '',
  cronSchedule:     '0 * * * *',
  maxPostLength:    300,
  dailyCostCap:     2.00,
  alertThreshold:   1.50,
  rateLimitWaitMs:  120000,
  postingHours:     '8-22',
  postsPerDay:      1,
  schedulerEnabled: true,
  sloTarget:        90.0, // % success rate target; configurable from dashboard
  postSystemPrompt: 'Write a short, persuasive affiliate post for social media. Max 200 chars. Use power words (deal, save, exclusive, limited). Natural, conversational tone. Do not include URLs or hashtags — those are added automatically.',
  postUserTemplate: 'Product: "{name}" ({category}). Description: {description}. Price: {price}. Trending topic: {trend}. Extra context: {highlights}. Write a punchy post with a clear CTA. No URLs, no hashtags.',
};

let _cache = null;

export function getSettings() {
  if (_cache) return _cache;

  // 1. Try file (fast path, works when /data is persistent or file just written)
  try {
    const raw = JSON.parse(fs.readFileSync(SETTINGS_FILE, 'utf8'));
    _cache = { ...DEFAULTS, ...raw };
    return _cache;
  } catch {}

  // 2. Fall back to HF secret (survives any rebuild)
  try {
    const raw = process.env[SETTINGS_SECRET];
    if (raw) {
      const parsed = JSON.parse(raw);
      _cache = { ...DEFAULTS, ...parsed };
      // Re-write to disk so subsequent reads are fast
      _writeFile(_cache);
      return _cache;
    }
  } catch {}

  _cache = { ...DEFAULTS };
  return _cache;
}

export function saveSettings(updates) {
  const current = getSettings();
  _cache = { ...current, ...updates };
  _writeFile(_cache);
  // Persist to HF secret so rebuild doesn't lose settings
  writeSecret(SETTINGS_SECRET, JSON.stringify(_cache)).catch(() => {});
  return _cache;
}

function _writeFile(data) {
  try {
    fs.mkdirSync(path.dirname(SETTINGS_FILE), { recursive: true });
    const tmp = `${SETTINGS_FILE}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
    fs.renameSync(tmp, SETTINGS_FILE);
  } catch {}
}

export function getSpaceHost() {
  const s = getSettings();
  if (s.spaceHost) return s.spaceHost.replace(/\/$/, '');
  if (process.env.SPACE_HOST) return process.env.SPACE_HOST.replace(/\/$/, '');
  // SPACE_ID is "owner/space-name" — HF Spaces URL is https://owner-space-name.hf.space
  if (process.env.SPACE_ID) {
    const slug = process.env.SPACE_ID.replace('/', '-');
    return `https://${slug}.hf.space`;
  }
  return '';
}
