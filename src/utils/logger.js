import fs from 'fs';
import path from 'path';

const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
const LOG_RING = [];
const LOG_RING_MAX = 200;

// ── File logger ───────────────────────────────────────────────────────────────

const LOG_DIR  = process.env.LOG_DIR || '/data';
const LOG_FILE = path.join(LOG_DIR, 'app.log');
const LOG_MAX_BYTES = 5 * 1024 * 1024; // 5 MB

let _fileLogEnabled = null; // null = unchecked

function isFileLogEnabled() {
  if (_fileLogEnabled !== null) return _fileLogEnabled;
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    _fileLogEnabled = true;
  } catch {
    _fileLogEnabled = false;
  }
  return _fileLogEnabled;
}

function rotateLogs() {
  try {
    const stat = fs.statSync(LOG_FILE);
    if (stat.size >= LOG_MAX_BYTES) {
      fs.renameSync(LOG_FILE, `${LOG_FILE}.1`);
    }
  } catch {
    // file doesn't exist yet — nothing to rotate
  }
}

function appendToFile(line) {
  if (!isFileLogEnabled()) return;
  try {
    rotateLogs();
    fs.appendFileSync(LOG_FILE, line + '\n');
  } catch {
    // best-effort — never throw from logger
  }
}

// ── Core log function ─────────────────────────────────────────────────────────

function log(level, ...args) {
  const minLevel = LEVELS[process.env.LOG_LEVEL] ?? LEVELS.info;
  if (LEVELS[level] < minLevel) return;
  const ts = new Date().toISOString();
  const prefix = `[${ts}] [${level.toUpperCase()}]`;
  const msg = args.map(a => (typeof a === 'string' ? a : String(a))).join(' ');
  LOG_RING.push({ ts, level, msg });
  if (LOG_RING.length > LOG_RING_MAX) LOG_RING.shift();
  if (level === 'error') console.error(prefix, ...args);
  else console.log(prefix, ...args);
  appendToFile(`${prefix} ${msg}`);
}

export function getRecentLogs(n = 50) {
  return LOG_RING.slice(-n);
}

export const logger = {
  debug: (...a) => log('debug', ...a),
  info: (...a) => log('info', ...a),
  warn: (...a) => log('warn', ...a),
  error: (...a) => log('error', ...a),
};
