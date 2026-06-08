import { getSettings } from '../config/settings.js';

/**
 * Returns true if the current UTC hour is inside the configured posting window.
 *
 * Source priority: POSTING_HOURS env var → settings.postingHours → default 8-22.
 * Format: "start-end" (inclusive, 24h UTC). Wrap-around supported: "22-6".
 */
export function isWithinPostingWindow() {
  const raw   = process.env.POSTING_HOURS || getSettings().postingHours || '8-22';
  const match = raw.trim().match(/^(\d{1,2})-(\d{1,2})$/);
  if (!match) return true; // malformed → fail-open, don't block posts

  const start = parseInt(match[1], 10);
  const end   = parseInt(match[2], 10);
  const hour  = new Date().getUTCHours();

  if (start <= end) return hour >= start && hour <= end;
  return hour >= start || hour <= end; // wrap-around e.g. 22-6
}
