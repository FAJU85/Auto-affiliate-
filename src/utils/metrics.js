import fs from 'fs';
import path from 'path';

const METRICS_FILE = path.resolve('data/metrics.json');

function load() {
  try {
    return JSON.parse(fs.readFileSync(METRICS_FILE, 'utf8'));
  } catch {
    return { runs: [] };
  }
}

function save(data) {
  const dir = path.dirname(METRICS_FILE);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = `${METRICS_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, METRICS_FILE);
}

export function recordRun(metrics) {
  const data = load();
  data.runs.push({ timestamp: new Date().toISOString(), ...metrics });
  // Keep last 200 runs
  if (data.runs.length > 200) data.runs = data.runs.slice(-200);
  save(data);
}

export function getRecentRuns(n = 10) {
  return load().runs.slice(-n);
}
