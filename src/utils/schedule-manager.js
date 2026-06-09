/**
 * Schedule Manager
 *
 * Distributes N posts evenly across a posting window,
 * generates cron expressions, and suggests optimal times
 * based on historical engagement data.
 */

import { getRecentRuns } from './metrics.js';

/**
 * Given postsPerDay and a posting window string like '8-22',
 * returns an array of { hour, minute } objects evenly spread
 * across the window.
 */
export function buildScheduleTimes(postsPerDay, postingHours = '8-22') {
  const n = Math.max(1, Math.min(postsPerDay, 24));
  const [startStr, endStr] = String(postingHours).split('-');
  const start = parseInt(startStr, 10);
  const end   = parseInt(endStr,   10);

  if (isNaN(start) || isNaN(end)) {
    return [{ hour: 9, minute: 0 }];
  }

  const windowMins = ((end > start ? end : end + 24) - start) * 60;
  const interval   = Math.floor(windowMins / n);

  return Array.from({ length: n }, (_, i) => {
    const totalMins = start * 60 + interval * i;
    return { hour: Math.floor(totalMins / 60) % 24, minute: totalMins % 60 };
  });
}

/** Returns an array of cron expressions (one per post slot). */
export function buildCronExpressions(postsPerDay, postingHours = '8-22') {
  return buildScheduleTimes(postsPerDay, postingHours)
    .map(({ hour, minute }) => `${minute} ${hour} * * *`);
}

/** Aggregates run history into a 24-element hourly engagement array. */
export function analyzeEngagementByHour(runs) {
  const hourly = Array.from({ length: 24 }, (_, h) => ({
    hour: h, score: 0, count: 0, avgScore: 0,
  }));

  for (const r of runs) {
    if (!r.success || !r.timestamp) continue;
    const h = new Date(r.timestamp).getUTCHours();
    hourly[h].score += (r.likes || 0) * 2 + (r.reposts || 0) * 3 + (r.clicks || 0) * 5;
    hourly[h].count++;
  }

  for (const h of hourly) {
    h.avgScore = h.count ? +(h.score / h.count).toFixed(2) : 0;
  }

  return hourly;
}

/**
 * Returns best posting times for postsPerDay slots.
 * Uses engagement data when available; falls back to industry defaults.
 */
export function suggestBestTimes(postsPerDay = 1) {
  const runs   = getRecentRuns(200);
  const hourly = analyzeEngagementByHour(runs);

  const engagedPosts = runs.filter(
    r => r.success && ((r.likes || 0) + (r.reposts || 0) + (r.clicks || 0)) > 0,
  ).length;

  const hasSufficientData = engagedPosts >= 5;

  let suggestedHours;
  if (hasSufficientData) {
    const sorted = [...hourly].sort((a, b) => b.avgScore - a.avgScore).map(h => h.hour);
    suggestedHours = pickSpacedHours(sorted, postsPerDay);
  } else {
    // Industry best-practice defaults (UTC) for social media engagement
    const defaults = [9, 12, 18, 20, 15, 8, 17, 21];
    suggestedHours = defaults.slice(0, postsPerDay);
  }

  suggestedHours.sort((a, b) => a - b);

  return {
    suggestedTimes: suggestedHours.map(h => ({
      hour:  h,
      label: `${String(h).padStart(2, '0')}:00 UTC`,
      cron:  `0 ${h} * * *`,
    })),
    hourlyData:  hourly,
    dataPoints:  runs.filter(r => r.success).length,
    basedOn:     hasSufficientData ? 'engagement-analysis' : 'industry-defaults',
    message:     hasSufficientData
      ? `Based on ${engagedPosts} engaged posts in the last 200 runs`
      : `Using industry best practices (${engagedPosts}/5 engaged posts collected so far)`,
  };
}

/** Picks N hours from a ranked list, ensuring min 2-hour spacing. */
function pickSpacedHours(rankedHours, n, minSpacing = 2) {
  const picked = [];
  for (const h of rankedHours) {
    if (picked.length >= n) break;
    const tooClose = picked.some(
      p => Math.min(Math.abs(p - h), 24 - Math.abs(p - h)) < minSpacing,
    );
    if (!tooClose) picked.push(h);
  }
  // Loosen spacing if still short
  for (const h of rankedHours) {
    if (picked.length >= n) break;
    if (!picked.includes(h)) picked.push(h);
  }
  return picked;
}
