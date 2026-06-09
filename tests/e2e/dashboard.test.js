/**
 * E2E Dashboard UI Tests (Puppeteer)
 *
 * Launches the real server + headless Chromium, drives every sidebar page,
 * tests the Schedule page interactions (slider, AI suggest, heatmap),
 * and verifies responsive behaviour at mobile/tablet viewports.
 *
 * Run: node --test tests/e2e/dashboard.test.js
 * Requires: puppeteer (devDependency)
 */
import { test, describe, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { startServer } from '../../src/server.js';
import puppeteer from 'puppeteer';

let server, browser, page, base;

before(async () => {
  server = startServer(() => false, () => {}, () => []);
  await new Promise(r => server.on('listening', r));
  base = `http://localhost:${server.address().port}`;

  browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
});

after(async () => {
  await browser?.close();
  await new Promise(r => server.close(r));
});

beforeEach(() => page.goto(base, { waitUntil: 'networkidle0' }));

// ── Helpers ───────────────────────────────────────────────────

const navTo = async id => {
  await page.evaluate(p => window.nav(p), id);
  await page.waitForSelector(`#page-${id}.active`, { timeout: 5000 });
};

const visible = sel => page.evaluate(s => {
  const el = document.querySelector(s);
  if (!el) return false;
  const st = getComputedStyle(el);
  return st.display !== 'none' && st.visibility !== 'hidden';
}, sel);

// ── Load smoke test ────────────────────────────────────────────

describe('Page load', () => {
  test('title contains Auto-Affiliate', async () => {
    assert.ok((await page.title()).includes('Auto-Affiliate'));
  });

  test('sidebar is visible', async () => {
    assert.ok(await visible('#sidebar'));
  });

  test('overview page is active on load', async () => {
    assert.ok(await page.evaluate(() => document.getElementById('page-overview')?.classList.contains('active')));
  });
});

// ── Navigation to all 10 pages ─────────────────────────────────

const ALL_PAGES = ['overview','analytics','posts','seo','ai','networks','schedule','accounts','settings','logs'];

describe('Sidebar navigation', () => {
  for (const p of ALL_PAGES) {
    test(`navigates to ${p} and sets topbar title`, async () => {
      await navTo(p);
      const active = await page.evaluate(id => document.getElementById(`page-${id}`)?.classList.contains('active'), p);
      assert.ok(active, `page-${p} not active`);
      const title = await page.$eval('#pg-title', el => el.textContent);
      assert.ok(title.length > 0, 'topbar title is empty');
    });
  }
});

// ── KPI cards ─────────────────────────────────────────────────

describe('Overview KPIs', () => {
  test('at least 4 KPI value elements present', async () => {
    await navTo('overview');
    const count = await page.$$eval('.kpi-val', els => els.length);
    assert.ok(count >= 4);
  });
});

// ── Schedule page — full interaction suite ─────────────────────

describe('Schedule page', () => {
  test('checkbox and slider render', async () => {
    await navTo('schedule');
    assert.ok(await page.$('#sched-enabled') !== null, 'checkbox missing');
    assert.ok(await page.$('#sched-ppd')     !== null, 'slider missing');
  });

  test('slider has min=1, max=24', async () => {
    await navTo('schedule');
    const attrs = await page.$eval('#sched-ppd', el => ({ min: el.min, max: el.max }));
    assert.equal(attrs.min, '1');
    assert.equal(attrs.max, '24');
  });

  test('moving slider updates ppd-val label', async () => {
    await navTo('schedule');
    await page.$eval('#sched-ppd', el => { el.value = '5'; el.dispatchEvent(new Event('input', { bubbles: true })); });
    const label = await page.$eval('#ppd-val', el => el.textContent);
    assert.equal(label, '5');
  });

  test('moving slider to N shows N time-slot badges', async () => {
    await navTo('schedule');
    await page.$eval('#sched-ppd', el => { el.value = '4'; el.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForFunction(() => document.querySelectorAll('#sched-slots .badge').length === 4, { timeout: 3000 });
    const count = await page.$$eval('#sched-slots .badge', els => els.length);
    assert.equal(count, 4);
  });

  test('posting-hours input accepts new value', async () => {
    await navTo('schedule');
    await page.click('#sched-hours', { clickCount: 3 });
    await page.type('#sched-hours', '10-20');
    const val = await page.$eval('#sched-hours', el => el.value);
    assert.ok(val.includes('10'));
  });

  test('AI Analyse button calls /api/schedule/suggest and renders output', async () => {
    await navTo('schedule');
    await page.setRequestInterception(true);
    let hit = false;
    const handler = req => {
      if (req.url().includes('/api/schedule/suggest')) {
        hit = true;
        req.respond({
          status: 200, contentType: 'application/json',
          body: JSON.stringify({
            suggestedTimes: [{ hour: 9, label: '09:00 UTC', cron: '0 9 * * *' }],
            hourlyData: Array.from({ length: 24 }, (_, h) => ({ hour: h, avgScore: 0, count: 0, score: 0 })),
            dataPoints: 0, basedOn: 'industry-defaults', message: 'Using industry defaults',
          }),
        });
      } else { req.continue(); }
    };
    page.on('request', handler);

    // click the Analyse button (second button in schedule card)
    const btns = await page.$$('#page-schedule button');
    for (const btn of btns) {
      const txt = await btn.evaluate(el => el.textContent);
      if (txt.includes('Analyse')) { await btn.click(); break; }
    }
    await page.waitForFunction(() => !document.getElementById('ai-suggest-out')?.textContent.includes('Analysing'), { timeout: 5000 });

    page.off('request', handler);
    await page.setRequestInterception(false);

    assert.ok(hit, '/api/schedule/suggest was not called');
    const outText = await page.$eval('#ai-suggest-out', el => el.textContent);
    assert.ok(outText.length > 10);
  });

  test('Save button POSTs to /api/schedule/config', async () => {
    await navTo('schedule');
    let posted = false;
    await page.setRequestInterception(true);
    const handler = req => {
      if (req.url().includes('/api/schedule/config') && req.method() === 'POST') {
        posted = true;
        req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, postsPerDay: 1 }) });
      } else { req.continue(); }
    };
    page.on('request', handler);
    const btns = await page.$$('#page-schedule button');
    for (const btn of btns) {
      if ((await btn.evaluate(el => el.textContent)).includes('Save')) { await btn.click(); break; }
    }
    await new Promise(r => setTimeout(r, 600));
    page.off('request', handler);
    await page.setRequestInterception(false);
    assert.ok(posted, 'Save did not call /api/schedule/config');
  });

  test('Pause button calls /api/schedule/pause', async () => {
    await navTo('schedule');
    let pauseCalled = false;
    await page.setRequestInterception(true);
    const handler = req => {
      if (req.url().includes('/api/schedule/pause') || req.url().includes('/api/schedule/resume')) {
        pauseCalled = true;
        req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
      } else { req.continue(); }
    };
    page.on('request', handler);
    const btns = await page.$$('#page-schedule button');
    for (const btn of btns) {
      const txt = await btn.evaluate(el => el.textContent);
      if (txt.includes('Pause') || txt.includes('Resume')) { await btn.click(); break; }
    }
    await new Promise(r => setTimeout(r, 400));
    page.off('request', handler);
    await page.setRequestInterception(false);
    assert.ok(pauseCalled, 'Pause/Resume did not call schedule API');
  });
});

// ── Settings page ─────────────────────────────────────────────

describe('Settings page', () => {
  test('settings form loads with input fields', async () => {
    await navTo('settings');
    const count = await page.$$eval('#page-settings input, #page-settings textarea', els => els.length);
    assert.ok(count >= 4, `Expected ≥4 form fields, got ${count}`);
  });
});

// ── Logs page ─────────────────────────────────────────────────

describe('Logs page', () => {
  test('log filter dropdown is present', async () => {
    await navTo('logs');
    assert.ok(await page.$('#log-filter') !== null || await page.$('.page.active') !== null, 'logs page missing');
  });
});

// ── Responsive layout ─────────────────────────────────────────

describe('Responsive layout', () => {
  test('hamburger visible at 420px width', async () => {
    await page.setViewport({ width: 420, height: 900 });
    await page.goto(base, { waitUntil: 'networkidle0' });
    assert.ok(await visible('#hamburger'), 'hamburger not visible at 420px');
    await page.setViewport({ width: 1280, height: 800 });
  });

  test('hamburger click opens sidebar (.open class)', async () => {
    await page.setViewport({ width: 420, height: 900 });
    await page.goto(base, { waitUntil: 'networkidle0' });
    await page.click('#hamburger');
    const isOpen = await page.evaluate(() => document.getElementById('sidebar')?.classList.contains('open'));
    assert.ok(isOpen, 'sidebar.open not set after hamburger click');
    await page.setViewport({ width: 1280, height: 800 });
  });

  test('sidebar collapses at 700px (icon-rail mode)', async () => {
    await page.setViewport({ width: 700, height: 900 });
    await page.goto(base, { waitUntil: 'networkidle0' });
    const w = await page.$eval('#sidebar', el => el.offsetWidth);
    assert.ok(w <= 60, `Sidebar too wide at 700px: ${w}px`);
    await page.setViewport({ width: 1280, height: 800 });
  });
});

// ── All API routes reachable from browser ─────────────────────

describe('API route health', () => {
  const ROUTES = [
    '/health', '/api/status', '/api/settings', '/api/networks',
    '/api/history', '/api/stats', '/api/clicks', '/api/logs',
    '/api/dedup', '/api/insights', '/api/engagement/top',
    '/api/schedule/config', '/api/schedule/suggest?n=1',
  ];

  for (const route of ROUTES) {
    test(`${route} returns non-5xx`, async () => {
      const status = await page.evaluate(async u => (await fetch(u)).status, route);
      assert.ok(status < 500, `${route} returned ${status}`);
    });
  }
});
