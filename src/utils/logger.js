const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };

function log(level, ...args) {
  const minLevel = LEVELS[process.env.LOG_LEVEL] ?? LEVELS.info;
  if (LEVELS[level] < minLevel) return;
  const ts = new Date().toISOString();
  const prefix = `[${ts}] [${level.toUpperCase()}]`;
  if (level === 'error') console.error(prefix, ...args);
  else console.log(prefix, ...args);
}

export const logger = {
  debug: (...a) => log('debug', ...a),
  info: (...a) => log('info', ...a),
  warn: (...a) => log('warn', ...a),
  error: (...a) => log('error', ...a),
};
