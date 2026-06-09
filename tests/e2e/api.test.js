/**
 * E2E API Integration Tests
 *
 * Spins up the real HTTP server (without a live pipeline/cron),
 * exercises every public API route, verifies shape + status codes.
 *
 * Run: node --test tests/e2e/api.test.js
 */
import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startServer } from '../../src/server.js';

let server, base;

before(async () => {
  server = startServer(() => false, () => {}, () => []);
  await new Promise(r => server.on('listening', r));
  base = `http://localhost:${server.address().port}`;
});

after(() => new Promise(r => server.close(r)));

const get  = async path => { const r = await fetch(`${base}${path}`); return { status: r.status, body: await r.json().catch(() => ({})) }; };
const post = async (path, payload = {}) => {
  const r = await fetch(`${base}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  return { status: r.status, body: await r.json().catch(() => ({})) };
};
const del = async path => {
  const r = await fetch(`${base}${path}`, { method: 'DELETE' });
  return { status: r.status, body: await r.json().catch(() => ({})) };
};

// ── /health ──────────────────────────────────────────────────

describe('/health', () => {
  test('returns 200 or 503 with status field', async () => {
    const { status, body } = await get('/health');
    assert.ok([200, 503].includes(status));
    assert.ok(['ok', 'degraded'].includes(body.status));
    assert.ok(typeof body.ts === 'string');
  });

  test('has lastRun field (object or null)', async () => {
    const { body } = await get('/health');
    assert.ok(body.lastRun === null || typeof body.lastRun === 'object');
  });

  test('successRate is string or null', async () => {
    const { body } = await get('/health');
    assert.ok(body.successRate === null || typeof body.successRate === 'string');
  });
});

// ── /api/status ──────────────────────────────────────────────

describe('/api/status', () => {
  test('returns pipeline, budget, stats, runs fields', async () => {
    const { status, body } = await get('/api/status');
    assert.equal(status, 200);
    assert.ok(body.pipeline);
    assert.ok(body.budget);
    assert.ok(body.stats);
    assert.ok(Array.isArray(body.runs));
  });

  test('pipeline.running is boolean', async () => {
    const { body } = await get('/api/status');
    assert.equal(typeof body.pipeline.running, 'boolean');
  });

  test('pipeline.paused is boolean', async () => {
    const { body } = await get('/api/status');
    assert.equal(typeof body.pipeline.paused, 'boolean');
  });

  test('budget has spent, cap, pct fields', async () => {
    const { body } = await get('/api/status');
    assert.ok('spent' in body.budget);
    assert.ok('cap'   in body.budget);
    assert.ok('pct'   in body.budget);
  });

  test('missingVars is array', async () => {
    const { body } = await get('/api/status');
    assert.ok(Array.isArray(body.missingVars));
  });
});

// ── /api/settings ────────────────────────────────────────────

describe('/api/settings', () => {
  test('GET returns settings with expected keys', async () => {
    const { status, body } = await get('/api/settings');
    assert.equal(status, 200);
    assert.ok(typeof body.cronSchedule === 'string');
    assert.ok(typeof body.postingHours === 'string');
    assert.ok(typeof body.dailyCostCap === 'number');
    assert.ok(typeof body.postsPerDay  === 'number');
  });

  test('POST saves and echoes back updated values', async () => {
    const { status, body } = await post('/api/settings', {
      dailyCostCap: 3.00, alertThreshold: 2.00, postingHours: '9-21',
      cronSchedule: '30 * * * *', maxPostLength: 280,
      postSystemPrompt: 'test', postUserTemplate: 'tpl',
    });
    assert.equal(status, 200);
    assert.equal(body.ok, true);
    assert.equal(body.postingHours, '9-21');
  });

  test('POST rejects alertThreshold >= dailyCostCap', async () => {
    const { status, body } = await post('/api/settings', { dailyCostCap: 1.00, alertThreshold: 1.00 });
    assert.equal(status, 400);
    assert.equal(body.ok, false);
  });

  test('GET after POST reflects saved postingHours', async () => {
    await post('/api/settings', { dailyCostCap: 2, alertThreshold: 1, postingHours: '7-23' });
    const { body } = await get('/api/settings');
    assert.equal(body.postingHours, '7-23');
    // restore
    await post('/api/settings', { dailyCostCap: 2, alertThreshold: 1, postingHours: '8-22' });
  });
});

// ── /api/networks ────────────────────────────────────────────

describe('/api/networks', () => {
  test('returns array with key, label, enabled', async () => {
    const { status, body } = await get('/api/networks');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body));
    if (body.length) {
      assert.ok('key'     in body[0]);
      assert.ok('label'   in body[0]);
      assert.ok('enabled' in body[0]);
    }
  });

  test('each entry has successRate (number or null)', async () => {
    const { body } = await get('/api/networks');
    for (const n of body) {
      assert.ok(n.successRate === null || typeof n.successRate === 'number');
    }
  });

  test('each entry has totalAttempts (number)', async () => {
    const { body } = await get('/api/networks');
    for (const n of body) {
      assert.ok(typeof n.totalAttempts === 'number');
    }
  });
});

// ── /api/history ─────────────────────────────────────────────

describe('/api/history', () => {
  test('GET returns array', async () => {
    const { status, body } = await get('/api/history');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body));
  });

  test('respects ?n param (capped at 500)', async () => {
    const { body } = await get('/api/history?n=5');
    assert.ok(body.length <= 5);
  });

  test('GET /api/history/csv returns CSV content-type', async () => {
    const r = await fetch(`${base}/api/history/csv`);
    assert.equal(r.status, 200);
    assert.ok(r.headers.get('content-type')?.includes('text/csv'));
    const text = await r.text();
    assert.ok(text.startsWith('timestamp,success'), 'CSV header missing');
  });
});

// ── /api/stats ───────────────────────────────────────────────

describe('/api/stats', () => {
  test('returns N-day array with date, total, failed, byNetwork', async () => {
    const { status, body } = await get('/api/stats?days=3');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body));
    assert.equal(body.length, 3);
    assert.ok('date'      in body[0]);
    assert.ok('total'     in body[0]);
    assert.ok('failed'    in body[0]);
    assert.ok('byNetwork' in body[0]);
  });

  test('each day has ISO date string', async () => {
    const { body } = await get('/api/stats?days=2');
    assert.ok(/^\d{4}-\d{2}-\d{2}$/.test(body[0].date));
  });
});

// ── /api/clicks ──────────────────────────────────────────────

describe('/api/clicks', () => {
  test('returns total (number) and daily (array)', async () => {
    const { status, body } = await get('/api/clicks');
    assert.equal(status, 200);
    assert.ok(typeof body.total === 'number');
    assert.ok(Array.isArray(body.daily));
  });

  test('daily items have date, clicks, posts, ctr', async () => {
    const { body } = await get('/api/clicks?days=3');
    if (body.daily.length > 0) {
      const d = body.daily[0];
      assert.ok('date'   in d);
      assert.ok('clicks' in d);
      assert.ok('posts'  in d);
      assert.ok('ctr'    in d);
    }
  });

  test('respects ?days param (7 by default)', async () => {
    const { body } = await get('/api/clicks?days=5');
    assert.equal(body.daily.length, 5);
  });
});

// ── /api/logs ────────────────────────────────────────────────

describe('/api/logs', () => {
  test('returns object with logs array and logFile', async () => {
    const { status, body } = await get('/api/logs');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body.logs), 'logs should be array');
    assert.ok(typeof body.logFile === 'string', 'logFile missing');
  });

  test('log entries have ts, level, msg fields', async () => {
    const { body } = await get('/api/logs');
    if (body.logs.length > 0) {
      const entry = body.logs[0];
      assert.ok('ts'    in entry || 'timestamp' in entry, 'ts missing');
      assert.ok('level' in entry, 'level missing');
      assert.ok('msg'   in entry || 'message'   in entry, 'msg missing');
    }
  });

  test('respects ?n param', async () => {
    const { body } = await get('/api/logs?n=5');
    assert.ok(body.logs.length <= 5);
  });
});

// ── /api/dedup ───────────────────────────────────────────────

describe('/api/dedup', () => {
  test('GET returns total (number), bySource (object), recent (array)', async () => {
    const { status, body } = await get('/api/dedup');
    assert.equal(status, 200);
    assert.ok(typeof body.total    === 'number');
    assert.ok(typeof body.bySource === 'object');
    assert.ok(Array.isArray(body.recent));
  });

  test('POST /api/dedup/check returns boolean posted field', async () => {
    const { status, body } = await post('/api/dedup/check', { url: 'https://example.com/p/1', name: 'Test' });
    assert.equal(status, 200);
    assert.ok(typeof body.posted === 'boolean');
  });

  test('DELETE clears store (total becomes 0)', async () => {
    const { status, body } = await del('/api/dedup');
    assert.equal(status, 200);
    assert.equal(body.ok, true);
    const { body: after } = await get('/api/dedup');
    assert.equal(after.total, 0);
  });

  test('POST /api/dedup/purge-source removes entries for a source', async () => {
    const { status, body } = await post('/api/dedup/purge-source', { source: 'admitad' });
    assert.equal(status, 200);
    assert.equal(body.ok, true);
    assert.ok(typeof body.removed === 'number');
  });

  test('POST /api/dedup/purge-source rejects missing source', async () => {
    const { status, body } = await post('/api/dedup/purge-source', {});
    assert.equal(status, 400);
    assert.equal(body.ok, false);
  });
});

// ── /api/engagement/top ──────────────────────────────────────

describe('/api/engagement/top', () => {
  test('returns array', async () => {
    const { status, body } = await get('/api/engagement/top');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body));
  });
});

// ── /api/insights ────────────────────────────────────────────

describe('/api/insights', () => {
  test('returns object', async () => {
    const { status, body } = await get('/api/insights');
    assert.equal(status, 200);
    assert.ok(typeof body === 'object');
  });
});

// ── /api/schedule/config ─────────────────────────────────────

describe('/api/schedule/config', () => {
  test('GET returns postsPerDay, schedulerEnabled, postingHours, cronExpressions', async () => {
    const { status, body } = await get('/api/schedule/config');
    assert.equal(status, 200);
    assert.ok(typeof body.postsPerDay      === 'number');
    assert.ok(typeof body.schedulerEnabled === 'boolean');
    assert.ok(typeof body.postingHours     === 'string');
    assert.ok(Array.isArray(body.cronExpressions));
  });

  test('cronExpressions count matches postsPerDay', async () => {
    const { body } = await get('/api/schedule/config');
    assert.equal(body.cronExpressions.length, body.postsPerDay);
  });

  test('POST updates postsPerDay and returns ok:true', async () => {
    const { status, body } = await post('/api/schedule/config', {
      postsPerDay: 3, postingHours: '8-22', schedulerEnabled: true,
    });
    assert.equal(status, 200);
    assert.equal(body.ok, true);
    assert.equal(body.postsPerDay, 3);
  });

  test('POST clamps postsPerDay to max 24', async () => {
    const { body } = await post('/api/schedule/config', { postsPerDay: 999 });
    assert.equal(body.postsPerDay, 24);
  });

  test('POST clamps postsPerDay to min 1', async () => {
    const { body } = await post('/api/schedule/config', { postsPerDay: 0 });
    assert.equal(body.postsPerDay, 1);
  });

  test('POST schedulerEnabled:false saved as boolean', async () => {
    const { body } = await post('/api/schedule/config', { schedulerEnabled: false, postsPerDay: 1, postingHours: '8-22' });
    assert.equal(body.schedulerEnabled, false);
    // restore
    await post('/api/schedule/config', { schedulerEnabled: true });
  });
});

// ── /api/schedule/suggest ────────────────────────────────────

describe('/api/schedule/suggest', () => {
  test('returns suggestedTimes array of length n', async () => {
    const { status, body } = await get('/api/schedule/suggest?n=2');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body.suggestedTimes));
    assert.equal(body.suggestedTimes.length, 2);
  });

  test('each time has hour (0-23), label, cron', async () => {
    const { body } = await get('/api/schedule/suggest?n=1');
    const t = body.suggestedTimes[0];
    assert.ok(t.hour >= 0 && t.hour < 24);
    assert.ok(typeof t.label === 'string');
    assert.ok(typeof t.cron  === 'string');
  });

  test('hourlyData has exactly 24 entries', async () => {
    const { body } = await get('/api/schedule/suggest?n=1');
    assert.equal(body.hourlyData.length, 24);
  });

  test('basedOn is a known value', async () => {
    const { body } = await get('/api/schedule/suggest?n=1');
    assert.ok(['engagement-analysis', 'industry-defaults'].includes(body.basedOn));
  });

  test('message is a non-empty string', async () => {
    const { body } = await get('/api/schedule/suggest?n=1');
    assert.ok(typeof body.message === 'string' && body.message.length > 0);
  });

  test('dataPoints is a number', async () => {
    const { body } = await get('/api/schedule/suggest?n=1');
    assert.ok(typeof body.dataPoints === 'number');
  });
});

// ── /api/schedule/pause + resume ─────────────────────────────

describe('/api/schedule/pause + /resume', () => {
  test('pause returns ok:true (or 500 outside main process)', async () => {
    const { status, body } = await post('/api/schedule/pause');
    if (status === 200) assert.equal(body.ok, true);
    else assert.equal(status, 500);
  });

  test('resume returns ok:true (or 500 outside main process)', async () => {
    const { status, body } = await post('/api/schedule/resume');
    if (status === 200) assert.equal(body.ok, true);
    else assert.equal(status, 500);
  });
});

// ── /api/run ─────────────────────────────────────────────────

describe('/api/run', () => {
  test('returns 202, 409, or 503', async () => {
    const { status } = await post('/api/run');
    assert.ok([202, 409, 503].includes(status), `Unexpected status: ${status}`);
  });
});

// ── /api/dry-run ─────────────────────────────────────────────

describe('/api/dry-run', () => {
  test('returns 200 or error status', async () => {
    const { status } = await post('/api/dry-run');
    assert.ok([200, 500, 503].includes(status), `Unexpected: ${status}`);
  });
});

// ── /api/accounts ────────────────────────────────────────────

describe('/api/accounts', () => {
  test('returns bluesky object with connected boolean', async () => {
    const { status, body } = await get('/api/accounts');
    assert.equal(status, 200);
    assert.ok(typeof body.bluesky?.connected === 'boolean');
  });

  test('returns social field (object, may be empty)', async () => {
    const { body } = await get('/api/accounts');
    assert.ok(typeof body.social === 'object');
  });

  test('returns spaceConfigured boolean', async () => {
    const { body } = await get('/api/accounts');
    assert.ok(typeof body.spaceConfigured === 'boolean');
  });
});

// ── /api/accounts/bluesky/disconnect ─────────────────────────

describe('/api/accounts/bluesky/disconnect', () => {
  test('POST returns ok:true', async () => {
    const { status, body } = await post('/api/accounts/bluesky/disconnect');
    assert.equal(status, 200);
    assert.equal(body.ok, true);
  });
});

// ── /api/env-status ──────────────────────────────────────────

describe('/api/env-status', () => {
  test('returns object of env var booleans', async () => {
    const { status, body } = await get('/api/env-status');
    assert.equal(status, 200);
    assert.ok(typeof body === 'object');
    for (const val of Object.values(body)) {
      assert.ok(typeof val === 'boolean', `Expected boolean, got ${typeof val}`);
    }
  });
});

// ── /api/network/test ─────────────────────────────────────────

describe('/api/network/test', () => {
  test('returns 404 for unknown network', async () => {
    const { status, body } = await post('/api/network/test', { network: 'nonexistent' });
    assert.equal(status, 404);
    assert.equal(body.ok, false);
  });

  test('returns ok or error for known network (admitad)', async () => {
    const { status, body } = await post('/api/network/test', { network: 'admitad' });
    assert.ok([200, 500].includes(status));
    assert.ok('ok' in body);
  });
});

// ── Click tracking redirect ───────────────────────────────────

describe('/r/:trackingId', () => {
  test('unknown tracking ID returns 302 to /', async () => {
    const r = await fetch(`${base}/r/unknown000`, { redirect: 'manual' });
    assert.equal(r.status, 302);
    assert.ok(r.headers.get('location'));
  });

  test('tracking ID with Cache-Control no-store header', async () => {
    const r = await fetch(`${base}/r/unknown000`, { redirect: 'manual' });
    assert.ok(r.headers.get('cache-control')?.includes('no-store'));
  });
});

// ── /client-metadata.json ────────────────────────────────────

describe('/client-metadata.json', () => {
  test('returns 200 or 503', async () => {
    const { status } = await get('/client-metadata.json');
    assert.ok([200, 503].includes(status));
  });

  test('if 200, has client_id and redirect_uris', async () => {
    const { status, body } = await get('/client-metadata.json');
    if (status === 200) {
      assert.ok(typeof body.client_id   === 'string');
      assert.ok(Array.isArray(body.redirect_uris));
    }
  });
});

// ── OAuth start routes ────────────────────────────────────────

describe('Bluesky OAuth start', () => {
  test('/oauth/start without handle returns redirect (no crash)', async () => {
    const r = await fetch(`${base}/oauth/start`, { redirect: 'manual' });
    assert.ok([302, 400, 503].includes(r.status));
  });

  test('/oauth/bsky/start also responds without crash', async () => {
    const r = await fetch(`${base}/oauth/bsky/start`, { redirect: 'manual' });
    assert.ok([302, 400, 503].includes(r.status));
  });
});

// ── Dashboard HTML ────────────────────────────────────────────

describe('Dashboard HTML', () => {
  test('GET / returns 200 HTML with Auto-Affiliate', async () => {
    const r = await fetch(`${base}/`);
    assert.equal(r.status, 200);
    assert.ok(r.headers.get('content-type')?.includes('text/html'));
    const html = await r.text();
    assert.ok(html.includes('Auto-Affiliate'));
  });

  test('HTML contains all 10 nav page ids', async () => {
    const html = await (await fetch(`${base}/`)).text();
    const pages = ['overview','analytics','posts','seo','ai','networks','schedule','accounts','settings','logs'];
    for (const p of pages) {
      assert.ok(html.includes(`page-${p}`), `page-${p} missing from HTML`);
    }
  });

  test('HTML contains accounts grid and social platform cards', async () => {
    const html = await (await fetch(`${base}/`)).text();
    assert.ok(html.includes('card-bluesky'),   'Bluesky card missing');
    assert.ok(html.includes('card-mastodon'),  'Mastodon card missing');
    assert.ok(html.includes('card-threads'),   'Threads card missing');
    assert.ok(html.includes('card-nostr'),     'Nostr card missing');
  });

  test('HTML contains schedule elements', async () => {
    const html = await (await fetch(`${base}/`)).text();
    assert.ok(html.includes('sched-ppd'),       'posts-per-day slider missing');
    assert.ok(html.includes('ai-suggest-out'),  'AI suggest section missing');
    assert.ok(html.includes('heatmap-wrap'),    'heatmap missing');
  });
});
