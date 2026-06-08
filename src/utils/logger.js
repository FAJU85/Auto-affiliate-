const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
const LOG_RING = [];
const LOG_RING_MAX = 200;

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
