import fs from 'fs';
import path from 'path';
import { dataPath } from './datadir.js';

const METRICS_FILE  = dataPath('metrics.json');
const POSTED_FILE   = dataPath('posted-products.json');

const DEDUP_MS = 60 * 24 * 60 * 60 * 1000; // 60 days

// ── Run history ───────────────────────────────────────────────────────────────

function load() {
  try { return JSON.parse(fs.readFileSync(METRICS_FILE, 'utf8')); }
  catch { return { runs: [] }; }
}

function save(data) {
  fs.mkdirSync(path.dirname(METRICS_FILE), { recursive: true });
  const tmp = `${METRICS_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, METRICS_FILE);
}

export function recordRun(metrics) {
  const data = load();
  data.runs.push({ timestamp: new Date().toISOString(), ...metrics });
  if (data.runs.length > 500) data.runs = data.runs.slice(-500);
  save(data);

  // On success, write to the long-term deduplication store
  if (metrics.success && metrics.deeplink) {
    recordPosted(metrics.deeplink, metrics.product, metrics.productSource);
  }
}

export function getRecentRuns(n = 10) {
  return load().runs.slice(-n);
}

// ── 60-day posted-products store ──────────────────────────────────────────────

function loadPosted() {
  try { return JSON.parse(fs.readFileSync(POSTED_FILE, 'utf8')); }
  catch { return []; }
}

function savePosted(entries) {
  fs.mkdirSync(path.dirname(POSTED_FILE), { recursive: true });
  const tmp = `${POSTED_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(entries, null, 2));
  fs.renameSync(tmp, POSTED_FILE);
}

function recordPosted(deeplink, name, source) {
  const entries = loadPosted();
  const cutoff  = Date.now() - DEDUP_MS;
  const fresh   = entries.filter(e => new Date(e.postedAt).getTime() > cutoff);
  fresh.push({ deeplink, name: normalizeName(name), source: source || null, postedAt: new Date().toISOString() });
  savePosted(fresh);
}

function normalizeName(name) {
  if (!name) return '';
  return name.toLowerCase().replace(/[^a-z0-9]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);
}

/** Returns the source (network key) of the most recently posted product, or null. */
export function getLastPostedSource() {
  const entries = loadPosted();
  if (!entries.length) return null;
  const last = entries.reduce((a, b) =>
    new Date(a.postedAt) > new Date(b.postedAt) ? a : b
  );
  return last.source || null;
}

/** Returns the sources of the last N posted products (most recent first). */
export function getRecentPostedSources(n = 3) {
  const entries = loadPosted();
  if (!entries.length) return [];
  return entries
    .filter(e => e.source)
    .sort((a, b) => new Date(b.postedAt) - new Date(a.postedAt))
    .slice(0, n)
    .map(e => e.source);
}

/**
 * Returns true if this deeplink OR product name was posted in the last 60 days.
 * Catches duplicates even when the URL differs slightly between runs.
 */
export function wasRecentlyPosted(deeplink, name) {
  const entries  = loadPosted();
  const cutoff   = Date.now() - DEDUP_MS;
  const normName = normalizeName(name);

  return entries.some(e => {
    if (new Date(e.postedAt).getTime() <= cutoff) return false;
    if (e.deeplink && e.deeplink === deeplink) return true;
    if (normName && e.name && e.name === normName) return true;
    return false;
  });
}

/** Returns the count of active (non-expired) dedup entries and the last 5. */
export function getDedupStatus() {
  const entries = loadPosted();
  const cutoff  = Date.now() - DEDUP_MS;
  const active  = entries.filter(e => new Date(e.postedAt).getTime() > cutoff);
  return { total: active.length, recent: active.slice(-10).reverse() };
}

/** Clears the entire dedup store — use for testing or manual reset. */
export function clearPostedStore() {
  savePosted([]);
}

/** Returns active dedup entry counts grouped by source network. */
export function getDedupBySource() {
  const entries = loadPosted();
  const cutoff  = Date.now() - DEDUP_MS;
  const active  = entries.filter(e => new Date(e.postedAt).getTime() > cutoff);
  const bySource = {};
  for (const e of active) {
    const src = e.source || 'unknown';
    bySource[src] = (bySource[src] || 0) + 1;
  }
  return bySource;
}

/** Removes all dedup entries for a specific source network. */
export function purgePostedBySource(source) {
  const entries = loadPosted();
  const remaining = entries.filter(e => e.source !== source);
  savePosted(remaining);
  return entries.length - remaining.length;
}

/** Records engagement (likes, reposts) for a post URI. */
export function recordEngagement(uri, likes, reposts) {
  const data = load();
  const run = data.runs.find(r => r.postUri === uri);
  if (run) {
    run.likes    = likes;
    run.reposts  = reposts;
    run.engagedAt = new Date().toISOString();
    save(data);
  }
}

/** Returns top posts by likes, last N days. */
export function getTopPosts(days = 30, limit = 5) {
  const cutoff = new Date(Date.now() - days * 86400000).toISOString();
  return load().runs
    .filter(r => r.success && r.postUri && r.timestamp >= cutoff && (r.likes || 0) > 0)
    .sort((a, b) => (b.likes || 0) - (a.likes || 0))
    .slice(0, limit);
}

/**
 * Returns per-network success rate over the last N runs.
 * Result: { [source]: { attempts: N, successes: N, rate: 0-1 } }
 */
export function getNetworkHealth(runs = 100) {
  const recent = load().runs.slice(-runs);
  const health = {};
  for (const r of recent) {
    const src = r.productSource || null;
    if (!src) continue;
    if (!health[src]) health[src] = { attempts: 0, successes: 0 };
    health[src].attempts++;
    if (r.success) health[src].successes++;
  }
  for (const src of Object.keys(health)) {
    health[src].rate = health[src].attempts ? health[src].successes / health[src].attempts : 0;
  }
  return health;
}

/**
 * Returns daily post counts broken down by network for the last N days.
 * Result: { date: 'YYYY-MM-DD', totals: N, byNetwork: { source: N, ... } }[]
 */
export function getDailyNetworkStats(days = 7) {
  const runs = load().runs;
  const now = new Date();
  const result = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setUTCDate(d.getUTCDate() - i);
    const dateStr = d.toISOString().slice(0, 10);
    const dayRuns = runs.filter(r => r.timestamp && r.timestamp.startsWith(dateStr));
    const successRuns = dayRuns.filter(r => r.success);
    const byNetwork = {};
    for (const r of successRuns) {
      const src = r.productSource || 'unknown';
      byNetwork[src] = (byNetwork[src] || 0) + 1;
    }
    result.push({ date: dateStr, total: successRuns.length, failed: dayRuns.length - successRuns.length, byNetwork });
  }
  return result;
}
