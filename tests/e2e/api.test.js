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

// ── /health ──────────────────────────────────────────────────

describe('/health', () => {
  test('returns 200 or 503 with status field', async () => {
    const { status, body } = await get('/health');
    assert.ok([200, 503].includes(status));
    assert.ok(['ok', 'degraded'].includes(body.status));
    assert.ok(typeof body.ts === 'string');
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

  test('pipeline.paused is boolean', async () => {
    const { body } = await get('/api/status');
    assert.equal(typeof body.pipeline.paused, 'boolean');
  });

  test('budget has spent, cap, pct', async () => {
    const { body } = await get('/api/status');
    assert.ok('spent' in body.budget);
    assert.ok('cap'   in body.budget);
    assert.ok('pct'   in body.budget);
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
});

// ── /api/networks ────────────────────────────────────────────

describe('/api/networks', () => {
  test('returns array with key, label, enabled fields', async () => {
    const { status, body } = await get('/api/networks');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body));
    if (body.length) {
      assert.ok('key'     in body[0]);
      assert.ok('label'   in body[0]);
      assert.ok('enabled' in body[0]);
    }
  });
});

// ── /api/history ─────────────────────────────────────────────

describe('/api/history', () => {
  test('returns array', async () => {
    const { status, body } = await get('/api/history');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body));
  });

  test('respects n param (capped at 500)', async () => {
    const { body } = await get('/api/history?n=5');
    assert.ok(body.length <= 5);
  });
});

// ── /api/stats ───────────────────────────────────────────────

describe('/api/stats', () => {
  test('returns N-day array with date, total fields', async () => {
    const { status, body } = await get('/api/stats?days=3');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body));
    assert.equal(body.length, 3);
    assert.ok('date'  in body[0]);
    assert.ok('total' in body[0]);
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
});

// ── /api/logs ────────────────────────────────────────────────

describe('/api/logs', () => {
  test('returns array', async () => {
    const { status, body } = await get('/api/logs');
    assert.equal(status, 200);
    assert.ok(Array.isArray(body));
  });
});

// ── /api/dedup ───────────────────────────────────────────────

describe('/api/dedup', () => {
  test('GET returns total (number) and bySource (object)', async () => {
    const { status, body } = await get('/api/dedup');
    assert.equal(status, 200);
    assert.ok(typeof body.total    === 'number');
    assert.ok(typeof body.bySource === 'object');
  });

  test('POST /api/dedup/check returns boolean posted field', async () => {
    const { status, body } = await post('/api/dedup/check', { url: 'https://example.com/p/1', name: 'Test' });
    assert.equal(status, 200);
    assert.ok(typeof body.posted === 'boolean');
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

  test('each time has hour (0-23), label (string), cron (string)', async () => {
    const { body } = await get('/api/schedule/suggest?n=1');
    const t = body.suggestedTimes[0];
    assert.ok(t.hour >= 0 && t.hour < 24);
    assert.ok(typeof t.label === 'string');
    assert.ok(typeof t.cron  === 'string');
  });

  test('hourlyData has exactly 24 elements', async () => {
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
  test('returns 202 (trigger accepted) or 503 (not configured) or 409 (already running)', async () => {
    const { status } = await post('/api/run');
    assert.ok([202, 409, 503].includes(status), `Unexpected status: ${status}`);
  });
});

// ── Click tracking redirect ───────────────────────────────────

describe('/r/:trackingId', () => {
  test('unknown tracking ID redirects (302) to /', async () => {
    const r = await fetch(`${base}/r/unknown000`, { redirect: 'manual' });
    assert.equal(r.status, 302);
    assert.ok(r.headers.get('location'));
  });
});

// ── /client-metadata.json ────────────────────────────────────

describe('/client-metadata.json', () => {
  test('returns 200 or 503', async () => {
    const { status } = await get('/client-metadata.json');
    assert.ok([200, 503].includes(status));
  });
});

// ── Dashboard HTML ────────────────────────────────────────────

describe('Dashboard HTML', () => {
  test('GET / serves HTML with expected elements', async () => {
    const r = await fetch(`${base}/`);
    assert.equal(r.status, 200);
    assert.ok(r.headers.get('content-type')?.includes('text/html'));
    const html = await r.text();
    assert.ok(html.includes('Auto-Affiliate'),  'title missing');
    assert.ok(html.includes('id="app"'),        'app shell missing');
    assert.ok(html.includes('page-schedule'),   'schedule page missing');
    assert.ok(html.includes('nav-schedule'),    'schedule nav item missing');
    assert.ok(html.includes('sched-ppd'),       'posts-per-day slider missing');
    assert.ok(html.includes('ai-suggest-out'),  'AI suggest section missing');
    assert.ok(html.includes('heatmap-wrap'),    'heatmap missing');
  });

  test('HTML includes all 10 nav pages', async () => {
    const r    = await fetch(`${base}/`);
    const html = await r.text();
    const pages = ['overview','analytics','posts','seo','ai','networks','schedule','accounts','settings','logs'];
    for (const p of pages) {
      assert.ok(html.includes(`page-${p}`), `page-${p} missing from HTML`);
    }
  });
});
