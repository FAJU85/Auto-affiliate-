/**
 * Lightweight next-run calculator for 5-field cron expressions.
 * Supports: * /n N M-N, L not supported.
 * Returns the next Date after `from` (default: now).
 */
export function nextCronRun(expr, from = new Date()) {
  try {
    const fields = expr.trim().split(/\s+/);
    if (fields.length !== 5) return null;
    const [minF, hrF, domF, monF, dowF] = fields;

    // Start from the next minute
    const start = new Date(from);
    start.setSeconds(0, 0);
    start.setMinutes(start.getMinutes() + 1);

    // Scan up to 1 year ahead (minute-by-minute is too slow; do hourly then minute)
    const limit = new Date(start.getTime() + 366 * 24 * 60 * 60 * 1000);
    const candidate = new Date(start);

    while (candidate < limit) {
      if (!matchField(monF,  candidate.getUTCMonth() + 1, 1, 12)) { candidate.setUTCMonth(candidate.getUTCMonth() + 1, 1); candidate.setUTCHours(0, 0); continue; }
      if (!matchField(domF,  candidate.getUTCDate(),       1, 31)) { candidate.setUTCDate(candidate.getUTCDate() + 1); candidate.setUTCHours(0, 0); continue; }
      if (!matchField(dowF,  candidate.getUTCDay(),        0,  7)) { candidate.setUTCDate(candidate.getUTCDate() + 1); candidate.setUTCHours(0, 0); continue; }
      if (!matchField(hrF,   candidate.getUTCHours(),      0, 23)) { candidate.setUTCHours(candidate.getUTCHours() + 1, 0); continue; }
      if (!matchField(minF,  candidate.getUTCMinutes(),    0, 59)) { candidate.setUTCMinutes(candidate.getUTCMinutes() + 1); continue; }
      return new Date(candidate);
    }
    return null;
  } catch {
    return null;
  }
}

function matchField(field, value, min, max) {
  if (field === '*') return true;
  if (field.startsWith('*/')) {
    const step = parseInt(field.slice(2), 10);
    return value % step === 0;
  }
  for (const part of field.split(',')) {
    if (part.includes('-')) {
      const [lo, hi] = part.split('-').map(Number);
      if (value >= lo && value <= hi) return true;
    } else {
      const n = parseInt(part, 10);
      if (n === value || (max === 7 && n === 0 && value === 7)) return true;
    }
  }
  return false;
}
