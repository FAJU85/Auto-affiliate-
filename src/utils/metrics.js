import fs from 'fs';
import path from 'path';
import { dataPath } from './datadir.js';

const METRICS_FILE = dataPath('metrics.json');

function load() {
  try {
    return JSON.parse(fs.readFileSync(METRICS_FILE, 'utf8'));
  } catch {
    return { runs: [] };
  }
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
  if (data.runs.length > 200) data.runs = data.runs.slice(-200);
  save(data);
}

export function getRecentRuns(n = 10) {
  return load().runs.slice(-n);
}

// Returns true if this deeplink was already successfully posted in the last windowMs
export function wasRecentlyPosted(deeplink, windowMs = 6 * 60 * 60 * 1000) {
  const cutoff = Date.now() - windowMs;
  return load().runs.some(r =>
    r.success &&
    r.deeplink === deeplink &&
    new Date(r.timestamp).getTime() > cutoff
  );
}
