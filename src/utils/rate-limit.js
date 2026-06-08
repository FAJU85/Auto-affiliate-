import { logger } from './logger.js';
import { sleep } from './sleep.js';

/**
 * Parses the Retry-After header and returns milliseconds to wait.
 * Supports both "seconds" integer and HTTP-date formats.
 */
export function parseRetryAfter(header) {
  if (!header) return null;
  const secs = parseInt(header, 10);
  if (!isNaN(secs) && secs >= 0) return secs * 1000;
  const date = new Date(header);
  if (!isNaN(date.getTime())) return Math.max(0, date.getTime() - Date.now());
  return null;
}

/**
 * Sleep for the duration specified in a Retry-After header, capped at maxMs.
 * Falls back to fallbackMs if the header is absent or unparseable.
 */
export async function sleepRetryAfter(header, { fallbackMs = 10_000, maxMs = 60_000, name = 'API' } = {}) {
  const waitMs = parseRetryAfter(header);
  const ms = Math.min(waitMs ?? fallbackMs, maxMs);
  logger.warn(`${name} rate limited — waiting ${(ms / 1000).toFixed(1)}s`);
  await sleep(ms);
}
