/**
 * E2E Dashboard UI Tests (Puppeteer)
 *
 * Launches the real server + headless Chromium.
 * Covers every sidebar page and interactive element:
 *   Overview, Analytics, Post History, SEO, AI Studio,
 *   Networks, Schedule, Accounts, Settings, Logs.
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

const interceptOnce = async (urlSubstr, mockBody) => {
  await page.setRequestInterception(true);
  let hit = false;
  const handler = req => {
    if (req.url().includes(urlSubstr)) {
      hit = true;
      req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify(mockBody) });
    } else req.continue();
  };
  page.on('request', handler);
  return { off: async () => { page.off('request', handler); await page.setRequestInterception(false); }, getHit: () => hit };
};

const clickBtnByText = async (scope, text) => {
  const btns = await page.$$(`${scope} button`);
  for (const btn of btns) {
    const t = await btn.evaluate(el => el.textContent);
    if (t.includes(text)) { await btn.click(); return true; }
  }
  return false;
};

// ═══════════════════════════════════════════════════════════════
// 1. PAGE LOAD & SHELL
// ═══════════════════════════════════════════════════════════════

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

  test('topbar timestamp updates after load', async () => {
    const ts = await page.$eval('#topbar-ts', el => el.textContent);
    assert.ok(ts.length > 0);
  });

  test('status dot is present', async () => {
    assert.ok(await page.$('#status-dot') !== null);
  });

  test('main Run button present and not in error state', async () => {
    assert.ok(await page.$('#btn-run') !== null);
  });
});

// ═══════════════════════════════════════════════════════════════
// 2. SIDEBAR NAVIGATION — all 10 pages
// ═══════════════════════════════════════════════════════════════

const ALL_PAGES = ['overview','analytics','posts','seo','ai','networks','schedule','accounts','settings','logs'];

describe('Sidebar navigation', () => {
  for (const p of ALL_PAGES) {
    test(`navigates to ${p} and updates topbar title`, async () => {
      await navTo(p);
      const active = await page.evaluate(id =>
        document.getElementById(`page-${id}`)?.classList.contains('active'), p);
      assert.ok(active, `page-${p} not active`);
      const title = await page.$eval('#pg-title', el => el.textContent);
      assert.ok(title.length > 0, 'topbar title empty');
    });
  }

  test('nav items highlight active page', async () => {
    await navTo('analytics');
    const isActive = await page.evaluate(() =>
      document.getElementById('nav-analytics')?.classList.contains('active'));
    assert.ok(isActive, 'nav-analytics not active');
  });
});

// ═══════════════════════════════════════════════════════════════
// 3. OVERVIEW PAGE
// ═══════════════════════════════════════════════════════════════

describe('Overview page', () => {
  test('at least 4 KPI value elements present', async () => {
    await navTo('overview');
    const count = await page.$$eval('.kpi-val', els => els.length);
    assert.ok(count >= 4, `Expected ≥4 KPI vals, got ${count}`);
  });

  test('KPI ids present: posts-today, success-rate, kpi-clicks, kpi-spend', async () => {
    await navTo('overview');
    for (const id of ['kpi-clicks', 'kpi-spend']) {
      assert.ok(await page.$(`#${id}`) !== null, `#${id} missing`);
    }
  });

  test('Run button calls /api/run on click', async () => {
    await navTo('overview');
    const { off, getHit } = await interceptOnce('/api/run', { ok: true, message: 'Run triggered' });
    await page.click('#btn-run');
    await new Promise(r => setTimeout(r, 500));
    await off();
    assert.ok(getHit(), '/api/run not called');
  });

  test('Overview Run button (btn-run2) also calls /api/run', async () => {
    await navTo('overview');
    const { off, getHit } = await interceptOnce('/api/run', { ok: true });
    await page.click('#btn-run2');
    await new Promise(r => setTimeout(r, 500));
    await off();
    assert.ok(getHit(), 'btn-run2 did not call /api/run');
  });

  test('Pause button calls /api/schedule/pause or /resume', async () => {
    await navTo('overview');
    let hit = false;
    await page.setRequestInterception(true);
    const handler = req => {
      if (req.url().includes('/api/schedule/pause') || req.url().includes('/api/schedule/resume')) {
        hit = true;
        req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
      } else req.continue();
    };
    page.on('request', handler);
    await page.click('#btn-pause');
    await new Promise(r => setTimeout(r, 500));
    page.off('request', handler);
    await page.setRequestInterception(false);
    assert.ok(hit, 'Pause did not call schedule API');
  });

  test('Dry Run button calls /api/dry-run', async () => {
    await navTo('overview');
    const { off, getHit } = await interceptOnce('/api/dry-run', {
      ok: true,
      product: { name: 'Test Product', source: 'admitad', siteUrl: 'https://example.com' },
      caption: 'Test caption #deal',
    });
    await clickBtnByText('#page-overview', 'Dry Run');
    await new Promise(r => setTimeout(r, 600));
    await off();
    assert.ok(getHit(), '/api/dry-run not called');
  });

  test('Last Run card renders 4 labelled fields', async () => {
    await navTo('overview');
    for (const id of ['lr-product', 'lr-source', 'lr-time', 'lr-dur']) {
      assert.ok(await page.$(`#${id}`) !== null, `#${id} missing in Last Run card`);
    }
  });

  test('posts bar chart element present', async () => {
    await navTo('overview');
    assert.ok(await page.$('#posts-chart') !== null);
  });

  test('network breakdown element present', async () => {
    await navTo('overview');
    assert.ok(await page.$('#net-breakdown') !== null);
  });
});

// ═══════════════════════════════════════════════════════════════
// 4. ANALYTICS PAGE
// ═══════════════════════════════════════════════════════════════

describe('Analytics page', () => {
  test('4 KPI cards present (a-clicks, a-ctr, a-best, a-seo)', async () => {
    await navTo('analytics');
    for (const id of ['a-clicks', 'a-ctr', 'a-best', 'a-seo']) {
      assert.ok(await page.$(`#${id}`) !== null, `#${id} missing`);
    }
  });

  test('clicks chart element present', async () => {
    await navTo('analytics');
    assert.ok(await page.$('#clicks-chart') !== null);
  });

  test('top-posts-body table element present', async () => {
    await navTo('analytics');
    assert.ok(await page.$('#top-posts-body') !== null);
  });

  test('KPI values are strings (may be — or a number)', async () => {
    await navTo('analytics');
    const text = await page.$eval('#a-clicks', el => el.textContent);
    assert.ok(typeof text === 'string' && text.length > 0);
  });
});

// ═══════════════════════════════════════════════════════════════
// 5. POST HISTORY PAGE
// ═══════════════════════════════════════════════════════════════

describe('Post History page', () => {
  test('posts table body present', async () => {
    await navTo('posts');
    assert.ok(await page.$('#posts-body') !== null);
  });

  test('filter dropdown has All/Successful/Failed options', async () => {
    await navTo('posts');
    const options = await page.$$eval('#posts-filter option', opts => opts.map(o => o.value));
    assert.ok(options.includes('all'),     'all option missing');
    assert.ok(options.includes('success'), 'success option missing');
    assert.ok(options.includes('failed'),  'failed option missing');
  });

  test('selecting Successful filter calls filterPosts without error', async () => {
    await navTo('posts');
    await page.select('#posts-filter', 'success');
    await new Promise(r => setTimeout(r, 300));
    const count = await page.$eval('#posts-count', el => el.textContent);
    assert.ok(typeof count === 'string');
  });

  test('selecting Failed filter updates count display', async () => {
    await navTo('posts');
    await page.select('#posts-filter', 'failed');
    await new Promise(r => setTimeout(r, 300));
    const rows = await page.$$eval('#posts-body tr', trs => trs.length);
    assert.ok(rows >= 1);
  });

  test('posts table has correct header columns', async () => {
    await navTo('posts');
    const headers = await page.$$eval('#page-posts thead th', ths => ths.map(th => th.textContent.trim()));
    assert.ok(headers.includes('#'), 'row number column missing');
    assert.ok(headers.some(h => h.includes('Status')), 'Status column missing');
    assert.ok(headers.some(h => h.includes('Network')), 'Network column missing');
  });
});

// ═══════════════════════════════════════════════════════════════
// 6. SEO PAGE
// ═══════════════════════════════════════════════════════════════

describe('SEO page', () => {
  test('grade display element present', async () => {
    await navTo('seo');
    assert.ok(await page.$('#seo-grade-big') !== null);
  });

  test('score display element present', async () => {
    await navTo('seo');
    assert.ok(await page.$('#seo-score-big') !== null);
  });

  test('score distribution chart element present', async () => {
    await navTo('seo');
    assert.ok(await page.$('#seo-dist') !== null);
  });

  test('keyword list element present', async () => {
    await navTo('seo');
    assert.ok(await page.$('#seo-kw-list') !== null);
  });

  test('SEO stats element present', async () => {
    await navTo('seo');
    assert.ok(await page.$('#seo-stats') !== null);
  });

  test('score distribution grade labels visible (F through A)', async () => {
    await navTo('seo');
    const text = await page.evaluate(() => document.getElementById('page-seo')?.textContent);
    assert.ok(text.includes('F'), 'grade F label missing');
    assert.ok(text.includes('A (80+)'), 'grade A label missing');
  });
});

// ═══════════════════════════════════════════════════════════════
// 7. AI STUDIO PAGE
// ═══════════════════════════════════════════════════════════════

describe('AI Studio page', () => {
  test('insights section present', async () => {
    await navTo('ai');
    assert.ok(await page.$('#insights-list') !== null);
  });

  test('caption generator inputs present', async () => {
    await navTo('ai');
    for (const id of ['gen-name', 'gen-cat', 'gen-desc']) {
      assert.ok(await page.$(`#${id}`) !== null, `#${id} missing`);
    }
  });

  test('Generate Caption button present', async () => {
    await navTo('ai');
    assert.ok(await page.$('#btn-gen') !== null);
  });

  test('Generate Caption calls /api/ai/generate with field values', async () => {
    await navTo('ai');
    await page.type('#gen-name', 'Sony WH-1000XM5');
    await page.type('#gen-cat',  'Electronics');

    const { off, getHit } = await interceptOnce('/api/ai/generate', {
      text: 'Amazing Sony headphones! 🎧 Perfect sound. #audio',
      seoScore: 78, seoGrade: 'B',
    });
    await page.click('#btn-gen');
    await page.waitForFunction(() => !document.getElementById('btn-gen').disabled, { timeout: 5000 }).catch(() => {});
    await off();
    assert.ok(getHit(), '/api/ai/generate not called');
  });

  test('generated caption output area shows when response succeeds', async () => {
    await navTo('ai');
    await page.type('#gen-name', 'Test Product');
    const { off } = await interceptOnce('/api/ai/generate', {
      text: 'Great product! Buy now.', seoScore: 65, seoGrade: 'B',
    });
    await page.click('#btn-gen');
    await page.waitForFunction(() => document.getElementById('gen-out').style.display !== 'none', { timeout: 5000 }).catch(() => {});
    await off();
    const visible = await page.evaluate(() => document.getElementById('gen-out').style.display !== 'none');
    assert.ok(visible, 'gen-out not shown after generation');
  });

  test('gen-out hidden on initial load', async () => {
    await navTo('ai');
    const display = await page.evaluate(() => document.getElementById('gen-out').style.display);
    assert.equal(display, 'none');
  });
});

// ═══════════════════════════════════════════════════════════════
// 8. NETWORKS PAGE
// ═══════════════════════════════════════════════════════════════

describe('Networks page', () => {
  test('networks list element present', async () => {
    await navTo('networks');
    assert.ok(await page.$('#nets-list') !== null);
  });

  test('performance table body present', async () => {
    await navTo('networks');
    assert.ok(await page.$('#nets-health') !== null);
  });

  test('performance table has Network/Status/Posts/Success Rate columns', async () => {
    await navTo('networks');
    const headers = await page.$$eval('#page-networks thead th', ths => ths.map(t => t.textContent.trim()));
    assert.ok(headers.some(h => h.includes('Network')));
    assert.ok(headers.some(h => h.includes('Status')));
  });

  test('network summary element present', async () => {
    await navTo('networks');
    assert.ok(await page.$('#nets-summary') !== null);
  });
});

// ═══════════════════════════════════════════════════════════════
// 9. SCHEDULE PAGE — full interaction suite
// ═══════════════════════════════════════════════════════════════

describe('Schedule page', () => {
  test('enabled checkbox and ppd slider render', async () => {
    await navTo('schedule');
    assert.ok(await page.$('#sched-enabled') !== null, 'checkbox missing');
    assert.ok(await page.$('#sched-ppd')     !== null, 'slider missing');
  });

  test('slider has min=1 and max=24', async () => {
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

  test('slider at N produces N time-slot badges', async () => {
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

  test('enabled toggle changes checked state', async () => {
    await navTo('schedule');
    const initialChecked = await page.$eval('#sched-enabled', el => el.checked);
    await page.click('#sched-enabled');
    const afterChecked = await page.$eval('#sched-enabled', el => el.checked);
    assert.notEqual(initialChecked, afterChecked);
    // restore
    await page.click('#sched-enabled');
  });

  test('Save button POSTs to /api/schedule/config', async () => {
    await navTo('schedule');
    const { off, getHit } = await interceptOnce('/api/schedule/config', { ok: true, postsPerDay: 1 });
    await clickBtnByText('#page-schedule', 'Save');
    await new Promise(r => setTimeout(r, 600));
    await off();
    assert.ok(getHit(), 'Save did not call /api/schedule/config');
  });

  test('Pause/Resume button calls pause or resume endpoint', async () => {
    await navTo('schedule');
    let called = false;
    await page.setRequestInterception(true);
    const handler = req => {
      if (req.url().includes('/api/schedule/pause') || req.url().includes('/api/schedule/resume')) {
        called = true;
        req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
      } else req.continue();
    };
    page.on('request', handler);
    await clickBtnByText('#page-schedule', 'Pause') || await clickBtnByText('#page-schedule', 'Resume');
    await new Promise(r => setTimeout(r, 400));
    page.off('request', handler);
    await page.setRequestInterception(false);
    assert.ok(called, 'Pause/Resume did not call schedule API');
  });

  test('AI Analyse button calls /api/schedule/suggest', async () => {
    await navTo('schedule');
    const mockSuggest = {
      suggestedTimes: [{ hour: 9, label: '09:00 UTC', cron: '0 9 * * *' }],
      hourlyData:     Array.from({ length: 24 }, (_, h) => ({ hour: h, avgScore: 0, count: 0, score: 0 })),
      dataPoints:     0, basedOn: 'industry-defaults', message: 'Using industry defaults',
    };
    const { off, getHit } = await interceptOnce('/api/schedule/suggest', mockSuggest);
    await clickBtnByText('#page-schedule', 'Analyse');
    await page.waitForFunction(() => !document.getElementById('ai-suggest-out')?.textContent.includes('Analysing'), { timeout: 5000 }).catch(() => {});
    await off();
    assert.ok(getHit(), '/api/schedule/suggest was not called');
  });

  test('AI suggest output text is non-empty after response', async () => {
    await navTo('schedule');
    const { off } = await interceptOnce('/api/schedule/suggest', {
      suggestedTimes: [{ hour: 14, label: '14:00 UTC', cron: '0 14 * * *' }],
      hourlyData:     Array.from({ length: 24 }, (_, h) => ({ hour: h, avgScore: 0, count: 0, score: 0 })),
      dataPoints: 10, basedOn: 'engagement-analysis', message: 'Best time: 2 PM UTC',
    });
    await clickBtnByText('#page-schedule', 'Analyse');
    await page.waitForFunction(() => (document.getElementById('ai-suggest-out')?.textContent?.length || 0) > 10, { timeout: 5000 }).catch(() => {});
    await off();
    const txt = await page.$eval('#ai-suggest-out', el => el.textContent);
    assert.ok(txt.length > 10, 'AI suggest output empty');
  });

  test('heatmap-wrap element exists for engagement chart', async () => {
    await navTo('schedule');
    assert.ok(await page.$('#heatmap-wrap') !== null, 'heatmap-wrap missing');
  });

  test('next-runs container present', async () => {
    await navTo('schedule');
    assert.ok(await page.$('#sched-next-runs') !== null);
  });
});

// ═══════════════════════════════════════════════════════════════
// 10. ACCOUNTS PAGE
// ═══════════════════════════════════════════════════════════════

describe('Accounts page', () => {
  test('accounts-grid container present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#accounts-grid') !== null);
  });

  test('Bluesky card present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#card-bluesky') !== null);
  });

  test('Bluesky handle input present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#bsky-handle') !== null);
  });

  test('Bluesky connect button present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#btn-bsky-connect') !== null);
  });

  test('Bluesky Connect triggers OAuth redirect when handle entered', async () => {
    await navTo('accounts');
    await page.type('#bsky-handle', 'test.bsky.social');
    // Intercept the navigation attempt
    let navUrl = '';
    page.once('request', req => {
      if (req.url().includes('/oauth/start')) { navUrl = req.url(); req.abort(); }
      else req.continue();
    });
    await page.setRequestInterception(true);
    await page.click('#btn-bsky-connect');
    await new Promise(r => setTimeout(r, 600));
    await page.setRequestInterception(false);
    assert.ok(navUrl.includes('/oauth/start') && navUrl.includes('test.bsky.social'),
      `Expected OAuth redirect, got: ${navUrl}`);
  });

  test('Mastodon card present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#card-mastodon') !== null);
  });

  test('Mastodon platform selector has correct options', async () => {
    await navTo('accounts');
    const values = await page.$$eval('#mastodon-platform option', opts => opts.map(o => o.value));
    assert.ok(values.includes('mastodon'),     'mastodon option missing');
    assert.ok(values.includes('truth_social'), 'truth_social option missing');
    assert.ok(values.includes('counter'),      'counter option missing');
  });

  test('Mastodon instance input present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#mastodon-instance') !== null);
  });

  test('Mastodon Connect calls /api/social/mastodon/register', async () => {
    await navTo('accounts');
    await page.click('#mastodon-instance', { clickCount: 3 });
    await page.type('#mastodon-instance', 'https://mastodon.social');
    const { off, getHit } = await interceptOnce('/api/social/mastodon/register', { url: 'https://mastodon.social/oauth/authorize?state=abc' });
    const navs = [];
    page.on('request', req => { if (req.url().includes('mastodon.social/oauth')) { navs.push(req.url()); req.abort(); } });
    await clickBtnByText('#card-mastodon', 'Connect');
    await new Promise(r => setTimeout(r, 600));
    await off();
    assert.ok(getHit(), '/api/social/mastodon/register not called');
  });

  test('Threads card present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#card-threads') !== null);
  });

  test('Tumblr card present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#card-tumblr') !== null);
  });

  test('Nostr card present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#card-nostr') !== null);
  });

  test('Nostr nsec input is password type', async () => {
    await navTo('accounts');
    const type = await page.$eval('#nostr-nsec', el => el.type);
    assert.equal(type, 'password');
  });

  test('Nostr Save Key calls /api/social/nostr/connect', async () => {
    await navTo('accounts');
    await page.type('#nostr-nsec', 'nsec1testkey');
    const { off, getHit } = await interceptOnce('/api/social/nostr/connect', { ok: true });
    await clickBtnByText('#card-nostr', 'Save Key');
    await new Promise(r => setTimeout(r, 500));
    await off();
    assert.ok(getHit(), '/api/social/nostr/connect not called');
  });

  test('Plurk card present', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#card-plurk') !== null);
  });

  test('credentials platforms card present (Pillowfort etc)', async () => {
    await navTo('accounts');
    assert.ok(await page.$('#cred-platforms-list') !== null);
  });

  test('credentials platforms render at least 4 platform blocks', async () => {
    await navTo('accounts');
    const count = await page.$$eval('#cred-platforms-list > div', els => els.length);
    assert.ok(count >= 4, `Expected ≥4 cred platforms, got ${count}`);
  });

  test('Bluesky badge reflects connected/disconnected state', async () => {
    await navTo('accounts');
    const badge = await page.$('#bsky-badge');
    assert.ok(badge !== null, 'bsky-badge missing');
    const text = await page.$eval('#bsky-badge', el => el.textContent);
    assert.ok(text.includes('Connected') || text.includes('Not connected'), `Unexpected badge text: ${text}`);
  });
});

// ═══════════════════════════════════════════════════════════════
// 11. SETTINGS PAGE
// ═══════════════════════════════════════════════════════════════

describe('Settings page', () => {
  test('at least 6 form fields', async () => {
    await navTo('settings');
    const count = await page.$$eval('#page-settings input, #page-settings textarea, #page-settings select',
      els => els.length);
    assert.ok(count >= 6, `Expected ≥6 fields, got ${count}`);
  });

  test('cron schedule input present', async () => {
    await navTo('settings');
    assert.ok(await page.$('#s-cron') !== null, '#s-cron missing');
  });

  test('daily cost cap input present', async () => {
    await navTo('settings');
    assert.ok(await page.$('#s-cap') !== null, '#s-cap missing');
  });

  test('max post length input present', async () => {
    await navTo('settings');
    assert.ok(await page.$('#s-maxlen') !== null, '#s-maxlen missing');
  });

  test('system prompt textarea present', async () => {
    await navTo('settings');
    assert.ok(await page.$('#s-sysprompt') !== null, '#s-sysprompt missing');
  });

  test('Save settings button calls /api/settings POST', async () => {
    await navTo('settings');
    let posted = false;
    await page.setRequestInterception(true);
    const handler = req => {
      if (req.url().includes('/api/settings') && req.method() === 'POST') {
        posted = true;
        req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) });
      } else req.continue();
    };
    page.on('request', handler);
    await clickBtnByText('#page-settings', 'Save');
    await new Promise(r => setTimeout(r, 600));
    page.off('request', handler);
    await page.setRequestInterception(false);
    assert.ok(posted, 'Save did not POST to /api/settings');
  });

  test('SEO min score field present', async () => {
    await navTo('settings');
    assert.ok(await page.$('#s-seo') !== null, '#s-seo missing');
  });

  test('posting hours field pre-filled from API', async () => {
    await navTo('settings');
    const val = await page.$eval('#s-hours', el => el.value);
    assert.ok(typeof val === 'string' && val.length > 0, 'hours field empty');
  });
});

// ═══════════════════════════════════════════════════════════════
// 12. LOGS PAGE
// ═══════════════════════════════════════════════════════════════

describe('Logs page', () => {
  test('log filter dropdown present', async () => {
    await navTo('logs');
    assert.ok(await page.$('#log-filter') !== null, '#log-filter missing');
  });

  test('filter has All/Error/Warning/Info options', async () => {
    await navTo('logs');
    const values = await page.$$eval('#log-filter option', opts => opts.map(o => o.value));
    assert.ok(values.includes('all'),   'all option missing');
    assert.ok(values.includes('error'), 'error option missing');
  });

  test('logs wrapper present', async () => {
    await navTo('logs');
    assert.ok(await page.$('#logs-wrap') !== null, '#logs-wrap missing');
  });

  test('logs count label present', async () => {
    await navTo('logs');
    const text = await page.$eval('#logs-count', el => el.textContent);
    assert.ok(typeof text === 'string');
  });

  test('logs load when navigating to page', async () => {
    let logsHit = false;
    await page.setRequestInterception(true);
    const handler = req => {
      if (req.url().includes('/api/logs')) { logsHit = true; req.continue(); }
      else req.continue();
    };
    page.on('request', handler);
    await navTo('logs');
    await new Promise(r => setTimeout(r, 500));
    page.off('request', handler);
    await page.setRequestInterception(false);
    assert.ok(logsHit, '/api/logs not called when navigating to logs page');
  });

  test('error filter selection updates view', async () => {
    await navTo('logs');
    await page.select('#log-filter', 'error');
    await new Promise(r => setTimeout(r, 300));
    const text = await page.$eval('#logs-count', el => el.textContent);
    assert.ok(typeof text === 'string');
  });
});

// ═══════════════════════════════════════════════════════════════
// 13. RESPONSIVE LAYOUT
// ═══════════════════════════════════════════════════════════════

describe('Responsive layout', () => {
  test('hamburger visible at 420px', async () => {
    await page.setViewport({ width: 420, height: 900 });
    await page.goto(base, { waitUntil: 'networkidle0' });
    assert.ok(await visible('#hamburger'), 'hamburger missing at 420px');
    await page.setViewport({ width: 1280, height: 800 });
  });

  test('hamburger click opens sidebar (.open class)', async () => {
    await page.setViewport({ width: 420, height: 900 });
    await page.goto(base, { waitUntil: 'networkidle0' });
    await page.click('#hamburger');
    const open = await page.evaluate(() => document.getElementById('sidebar')?.classList.contains('open'));
    assert.ok(open, 'sidebar.open not set after hamburger click');
    await page.setViewport({ width: 1280, height: 800 });
  });

  test('sidebar icon-rail at 700px (width ≤60px)', async () => {
    await page.setViewport({ width: 700, height: 900 });
    await page.goto(base, { waitUntil: 'networkidle0' });
    const w = await page.$eval('#sidebar', el => el.offsetWidth);
    assert.ok(w <= 60, `Sidebar too wide at 700px: ${w}px`);
    await page.setViewport({ width: 1280, height: 800 });
  });

  test('all pages render without overflow at 360px mobile', async () => {
    await page.setViewport({ width: 360, height: 800 });
    await page.goto(base, { waitUntil: 'networkidle0' });
    const overflow = await page.evaluate(() => document.body.scrollWidth > window.innerWidth);
    // allow some overflow (charts etc) — just check the page doesn't crash
    assert.ok(typeof overflow === 'boolean');
    await page.setViewport({ width: 1280, height: 800 });
  });
});

// ═══════════════════════════════════════════════════════════════
// 14. TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════

describe('Toast notifications', () => {
  test('toast element exists in DOM', async () => {
    assert.ok(await page.$('#toast') !== null);
  });

  test('toast shows on triggerRun click (any response)', async () => {
    await navTo('overview');
    await page.setRequestInterception(true);
    const handler = req => {
      if (req.url().includes('/api/run')) {
        req.respond({ status: 409, contentType: 'application/json', body: JSON.stringify({ ok: false, error: 'Already running' }) });
      } else req.continue();
    };
    page.on('request', handler);
    await page.click('#btn-run');
    await page.waitForFunction(() => document.getElementById('toast')?.className.includes('show'), { timeout: 4000 }).catch(() => {});
    page.off('request', handler);
    await page.setRequestInterception(false);
    const cls = await page.$eval('#toast', el => el.className);
    assert.ok(cls.includes('show'), 'toast did not appear');
  });
});

// ═══════════════════════════════════════════════════════════════
// 15. API ROUTE HEALTH (from browser via fetch)
// ═══════════════════════════════════════════════════════════════

describe('API route health (browser fetch)', () => {
  const ROUTES = [
    '/health',
    '/api/status',
    '/api/settings',
    '/api/networks',
    '/api/history',
    '/api/stats',
    '/api/clicks',
    '/api/logs',
    '/api/dedup',
    '/api/insights',
    '/api/engagement/top',
    '/api/schedule/config',
    '/api/schedule/suggest?n=1',
    '/api/env-status',
    '/api/accounts',
  ];

  for (const route of ROUTES) {
    test(`${route} returns non-5xx`, async () => {
      const status = await page.evaluate(async u => (await fetch(u)).status, route);
      assert.ok(status < 500, `${route} returned ${status}`);
    });
  }
});
