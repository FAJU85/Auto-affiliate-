/**
 * Returns true if the current UTC hour falls inside the configured posting window.
 *
 * POSTING_HOURS env var format: "start-end" (24h UTC, inclusive)
 * Examples:
 *   "8-22"   → post between 08:00 and 22:59 UTC  (default)
 *   "0-23"   → always post
 *   "12-20"  → afternoon/evening only
 *
 * If the variable is absent or malformed the window defaults to 8–22 UTC.
 */
export function isWithinPostingWindow() {
  const raw   = process.env.POSTING_HOURS || '8-22';
  const match = raw.trim().match(/^(\d{1,2})-(\d{1,2})$/);
  if (!match) return true; // malformed → don't block

  const start  = parseInt(match[1], 10);
  const end    = parseInt(match[2], 10);
  const hour   = new Date().getUTCHours();

  if (start <= end) return hour >= start && hour <= end;
  // Wrap-around window e.g. 22-6 (overnight)
  return hour >= start || hour <= end;
}
