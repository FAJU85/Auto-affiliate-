import http from 'http';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { getDailySpend } from './utils/budget.js';
import { getRecentRuns, getDedupStatus, clearPostedStore, wasRecentlyPosted, getDailyNetworkStats, purgePostedBySource, getDedupBySource, getTopPosts, getNetworkHealth, recordClick, getTotalClicks, getDailyClicks } from './utils/metrics.js';
import { logger, getRecentLogs } from './utils/logger.js';
import { getSettings, saveSettings, getSpaceHost } from './config/settings.js';
import { getOAuthClient, getConnectedDid, disconnectBluesky } from './auth/bluesky-oauth.js';
import { nextCronRun } from './utils/cron-next.js';

const PORT = parseInt(process.env.PORT || '7860', 10);
const DASHBOARD_PATH = new URL('./dashboard.html', import.meta.url).pathname;

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function getStatusPayload(isRunning) {
  const settings = getSettings();
  const cap   = settings.dailyCostCap;
  const alert = settings.alertThreshold;
  const spend = getDailySpend();
  const runs  = getRecentRuns(20);
  const today = new Date().toISOString().slice(0, 10);
  return {
    pipeline:    { running: isRunning, schedule: settings.cronSchedule, postingHours: process.env.POSTING_HOURS || settings.postingHours || '8-22', nextRun: nextCronRun(settings.cronSchedule || '0 * * * *')?.toISOString() || null },
    budget:      { spent: spend, cap, alert, pct: spend / cap },
    stats:       {
      postsToday:   runs.filter(r => r.success && r.timestamp?.startsWith(today)).length,
      maxPostsPerDay: parseInt(process.env.MAX_POSTS_PER_DAY || '24', 10),
      totalRuns:    runs.length,
      successRate:  runs.length ? Math.round(runs.filter(r=>r.success).length/runs.length*100) : null,
    },
    lastRun:       runs.at(-1) ?? null,
    runs:          [...runs].reverse(),
    networkHealth: getNetworkHealth(100),
  };
}

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

// ─── Dashboard HTML ──────────────────────────────────────────────────────────

const _dashHtmlPath = new URL('./dashboard.html', import.meta.url);
const DASHBOARD_HTML = fs.readFileSync(fileURLToPath(_dashHtmlPath), 'utf8');

// ─── Server ──────────────────────────────────────────────────────────────────

function getNetworkStatus() {
  const e = process.env;
  const networks = [
    { key: 'admitad-feed',    label: 'Admitad XML Feed',     enabled: !!e.ADMITAD_FEED_URL },
    { key: 'admitad-api',     label: 'Admitad API',          enabled: !!(e.ADMITAD_CLIENT_ID && e.ADMITAD_CLIENT_SECRET && e.ADMITAD_WEBSITE_ID) },
    { key: 'admitad-catalog', label: 'Admitad Catalog',      enabled: [1,2,3,4,5].some(n => e[`ADMITAD_CATALOG_URL_${n}`]) },
    { key: 'temu',            label: 'Temu',                 enabled: !!(e.TEMU_AFFILIATE_URL_1 || e.TEMU_AFFILIATE_URL_2) },
    { key: 'takeads',         label: 'TakeAds',              enabled: !!e.TAKEADS_API_KEY },
    { key: 'travelpayouts',   label: 'Travelpayouts',        enabled: !!e.TRAVELPAYOUTS_TOKEN },
    { key: 'impact',          label: 'Impact.com',           enabled: !!(e.IMPACT_ACCOUNT_SID && e.IMPACT_AUTH_TOKEN) },
    { key: 'cj',              label: 'CJ Affiliate',         enabled: !!(e.CJ_API_KEY && e.CJ_WEBSITE_ID) },
    { key: 'shareasale',      label: 'ShareASale',           enabled: !!(e.SHAREASALE_TOKEN && e.SHAREASALE_SECRET && e.SHAREASALE_AFFILIATE_ID) },
  ];
  return networks;
}

export function hasAnyNetworkEnabled() {
  return getNetworkStatus().some(n => n.enabled);
}

function handleClientMetadata(res) {
  const host = getSpaceHost();
  if (!host) return json(res, 503, { error: 'Space URL not configured' });
  return json(res, 200, {
    client_id:                  `${host}/client-metadata.json`,
    client_name:                'Auto Affiliate Pipeline',
    client_uri:                 host,
    redirect_uris:              [`${host}/oauth/callback`],
    scope:                      'atproto transition:generic',
    grant_types:                ['authorization_code', 'refresh_token'],
    response_types:             ['code'],
    token_endpoint_auth_method: 'none',
    application_type:           'web',
    dpop_bound_access_tokens:   true,
  });
}

async function handleSettingsPost(req, res) {
  try {
    const body    = await readBody(req);
    const updates = JSON.parse(body);
    if (updates.alertThreshold >= updates.dailyCostCap) {
      return json(res, 400, { ok: false, error: 'Alert threshold must be less than daily cost cap' });
    }
    const saved = saveSettings(updates);
    logger.info('Settings updated via dashboard');
    return json(res, 200, { ok: true, ...saved });
  } catch (err) {
    return json(res, 400, { ok: false, error: err.message });
  }
}

async function handleOAuthStart(url, res) {
  const handle = url.searchParams.get('handle');
  if (!handle) return json(res, 400, { error: 'handle param required' });
  const client = getOAuthClient();
  if (!client) return json(res, 503, { error: 'Space URL not configured — set it in Space Config tab' });
  try {
    const authUrl = await client.authorize(handle, { scope: 'atproto transition:generic' });
    return json(res, 200, { url: authUrl.toString() });
  } catch (err) {
    logger.warn(`Bluesky OAuth start failed: ${err.message}`);
    return json(res, 500, { error: err.message });
  }
}

async function handleOAuthCallback(url, res) {
  const client = getOAuthClient();
  if (!client) { res.writeHead(302, { Location: '/?error=no_client' }); return res.end(); }
  try {
    const { session } = await client.callback(new URLSearchParams(Object.fromEntries(url.searchParams)));
    logger.info(`Bluesky OAuth connected: ${session.did}`);
    res.writeHead(302, { Location: '/?tab=accounts&connected=1' });
    return res.end();
  } catch (err) {
    logger.warn(`Bluesky OAuth callback failed: ${err.message}`);
    res.writeHead(302, { Location: '/?tab=accounts&error=' + encodeURIComponent(err.message) });
    return res.end();
  }
}

async function routeRequest(req, res, url, getIsRunning, triggerRunFn, getMissingVars) {
  const path = url.pathname;
  if (path === '/health') {
    const runs = getRecentRuns(20);
    const last = runs.at(-1);
    const successRate = runs.length ? (runs.filter(r => r.success).length / runs.length * 100).toFixed(0) : null;
    const lastSuccess = runs.slice().reverse().find(r => r.success);
    const hoursSinceSuccess = lastSuccess ? (Date.now() - new Date(lastSuccess.timestamp).getTime()) / 3600000 : null;
    const healthy = runs.length === 0 || (successRate >= 50 && (hoursSinceSuccess === null || hoursSinceSuccess < 26));
    res.writeHead(healthy ? 200 : 503, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({
      status: healthy ? 'ok' : 'degraded',
      ts: new Date().toISOString(),
      successRate: successRate !== null ? `${successRate}%` : null,
      hoursSinceLastSuccess: hoursSinceSuccess !== null ? Math.round(hoursSinceSuccess) : null,
      lastRun: last ? { success: last.success, ts: last.timestamp, source: last.productSource } : null,
    }));
  }
  if (path === '/client-metadata.json') return handleClientMetadata(res);
  if (path === '/api/status') {
    const payload = getStatusPayload(getIsRunning());
    payload.missingVars = getMissingVars();
    try {
      const { isSchedulerPaused } = await import('./index.js');
      payload.pipeline.paused = isSchedulerPaused();
    } catch { payload.pipeline.paused = false; }
    return json(res, 200, payload);
  }
  if (path === '/api/settings' && req.method === 'GET')  return json(res, 200, getSettings());
  if (path === '/api/settings' && req.method === 'POST') return handleSettingsPost(req, res);
  if (path === '/api/accounts' && req.method === 'GET') {
    const did = await getConnectedDid().catch(() => null);
    return json(res, 200, { spaceConfigured: !!getSpaceHost(), bluesky: { connected: !!did, did } });
  }
  if (path === '/api/accounts/bluesky/disconnect' && req.method === 'POST') {
    await disconnectBluesky();
    return json(res, 200, { ok: true });
  }
  if (path === '/api/env-status' && req.method === 'GET') {
    const { OPTIONAL_LABELS } = await import('./utils/env.js');
    const vars = [...Object.keys(OPTIONAL_LABELS), 'BSKY_HANDLE', 'BSKY_APP_PASSWORD'];
    const status = Object.fromEntries(vars.map(k => [k, !!process.env[k]]));
    return json(res, 200, status);
  }
  if (path === '/api/networks' && req.method === 'GET') {
    const { getNetworkErrors, getNetworkSelectCounts } = await import('./feeds/index.js');
    const errors = getNetworkErrors();
    const counts = getNetworkSelectCounts();
    const networks = getNetworkStatus().map(n => ({
      ...n,
      lastError: errors[n.key]?.error || null,
      lastErrorAt: errors[n.key]?.at || null,
      selectCount: counts[n.key] || 0,
    }));
    return json(res, 200, networks);
  }
  if (path === '/api/history' && req.method === 'GET') {
    const n = Math.min(parseInt(url.searchParams.get('n') || '50', 10), 500);
    return json(res, 200, getRecentRuns(n));
  }
  if (path === '/api/history/csv' && req.method === 'GET') {
    const runs = getRecentRuns(500);
    const header = 'timestamp,success,product,source,imageSource,qualityScore,captionChars,likes,reposts,durationMs,postUri,error\n';
    const rows = runs.map(r => [
      r.timestamp||'', r.success?'1':'0',
      '"'+(r.product||'').replace(/"/g,'""')+'"', r.productSource||'',
      r.imageSource||'', r.qualityScore||0, r.captionChars||0,
      r.likes||0, r.reposts||0, r.durationMs||0,
      r.postUri||'', '"'+(r.error||'').replace(/"/g,'""').replace(/\n/g,' ')+'"',
    ].join(',')).join('\n');
    res.writeHead(200, { 'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename="pipeline-history.csv"' });
    return res.end(header + rows);
  }
  if (path === '/api/logs' && req.method === 'GET') return json(res, 200, getRecentLogs(100));
  if (path === '/api/stats' && req.method === 'GET') {
    const days = Math.min(parseInt(url.searchParams.get('days') || '7', 10), 90);
    return json(res, 200, getDailyNetworkStats(days));
  }
  if (path === '/api/engagement/top' && req.method === 'GET') return json(res, 200, getTopPosts(30, 10));
  if (path === '/api/clicks' && req.method === 'GET') {
    const days = Math.min(parseInt(url.searchParams.get('days') || '7', 10), 90);
    return json(res, 200, { total: getTotalClicks(), daily: getDailyClicks(days) });
  }
  if (path === '/api/insights' && req.method === 'GET') {
    const { loadInsights } = await import('./ai/optimizer.js');
    return json(res, 200, loadInsights());
  }
  // Click tracking redirect: /r/<trackingId>
  const trackMatch = path.match(/^\/r\/([a-z0-9]+)$/i);
  if (trackMatch) {
    const run = recordClick(trackMatch[1]);
    const dest = run?.deeplink || '/';
    res.writeHead(302, { Location: dest, 'Cache-Control': 'no-store' });
    return res.end();
  }
  if (path === '/api/dedup' && req.method === 'GET') {
    const status = getDedupStatus();
    return json(res, 200, { ...status, bySource: getDedupBySource() });
  }
  if (path === '/api/dedup' && req.method === 'DELETE') { clearPostedStore(); return json(res, 200, { ok: true }); }
  if (path === '/api/dedup/purge-source' && req.method === 'POST') {
    try {
      const body = JSON.parse(await readBody(req));
      if (!body.source) return json(res, 400, { ok: false, error: 'source required' });
      const removed = purgePostedBySource(body.source);
      logger.info(`Dedup: purged ${removed} entries for source "${body.source}"`);
      return json(res, 200, { ok: true, removed });
    } catch (err) { return json(res, 500, { ok: false, error: err.message }); }
  }
  if (path === '/api/dedup/check' && req.method === 'POST') {
    try {
      const body = await readBody(req);
      const { url, name } = JSON.parse(body);
      return json(res, 200, { posted: wasRecentlyPosted(url, name) });
    } catch (err) { return json(res, 400, { ok: false, error: err.message }); }
  }
  if (path === '/oauth/bsky/start')  return handleOAuthStart(url, res);
  if (path === '/oauth/callback')    return handleOAuthCallback(url, res);
  if (path === '/api/run' && req.method === 'POST') {
    const missing = getMissingVars();
    if (missing.length) return json(res, 503, { ok: false, error: `Not ready: ${missing.join(', ')}` });
    if (getIsRunning()) return json(res, 409, { ok: false, error: 'Pipeline already running' });
    triggerRunFn('manual');
    return json(res, 202, { ok: true, message: 'Run triggered' });
  }

  if (path === '/api/schedule/pause' && req.method === 'POST') {
    try {
      const { pauseScheduler } = await import('./index.js');
      pauseScheduler();
      return json(res, 200, { ok: true, paused: true });
    } catch (err) {
      return json(res, 500, { ok: false, error: err.message });
    }
  }

  if (path === '/api/schedule/resume' && req.method === 'POST') {
    try {
      const { resumeScheduler } = await import('./index.js');
      resumeScheduler();
      return json(res, 200, { ok: true, paused: false });
    } catch (err) {
      return json(res, 500, { ok: false, error: err.message });
    }
  }

  if (path === '/api/schedule/config' && req.method === 'GET') {
    try {
      const { getScheduleInfo } = await import('./index.js');
      return json(res, 200, getScheduleInfo());
    } catch {
      const s = getSettings();
      const { buildCronExpressions } = await import('./utils/schedule-manager.js');
      return json(res, 200, {
        postsPerDay:      s.postsPerDay ?? 1,
        schedulerEnabled: s.schedulerEnabled !== false,
        postingHours:     s.postingHours || '8-22',
        cronExpressions:  buildCronExpressions(s.postsPerDay ?? 1, s.postingHours || '8-22'),
        paused:           false,
      });
    }
  }

  if (path === '/api/schedule/config' && req.method === 'POST') {
    try {
      const body    = JSON.parse(await readBody(req));
      const updates = {};
      if (body.postsPerDay      != null) updates.postsPerDay      = Math.max(1, Math.min(24, parseInt(body.postsPerDay, 10)));
      if (body.postingHours     != null) updates.postingHours     = String(body.postingHours);
      if (body.schedulerEnabled != null) updates.schedulerEnabled = !!body.schedulerEnabled;
      saveSettings(updates);
      try { const { rebuildSchedule } = await import('./index.js'); rebuildSchedule(); } catch {}
      logger.info(`Schedule updated: ${JSON.stringify(updates)}`);
      return json(res, 200, { ok: true, ...updates });
    } catch (err) {
      return json(res, 400, { ok: false, error: err.message });
    }
  }

  if (path === '/api/schedule/suggest' && req.method === 'GET') {
    try {
      const n = Math.max(1, Math.min(24, parseInt(url.searchParams.get('n') || '1', 10)));
      const { suggestBestTimes } = await import('./utils/schedule-manager.js');
      return json(res, 200, suggestBestTimes(n));
    } catch (err) {
      return json(res, 500, { ok: false, error: err.message });
    }
  }

  if (path === '/api/network/test' && req.method === 'POST') {
    try {
      const body = await readBody(req);
      const { network } = JSON.parse(body);
      const { TASKS } = await import('./feeds/index.js');
      const task = TASKS.find(t => t.key === network);
      if (!task) return json(res, 404, { ok: false, error: `Unknown network: ${network}` });
      if (!task.env()) return json(res, 200, { ok: false, error: `${network} not configured (missing env vars)` });
      const product = await task.fn();
      if (!product) return json(res, 200, { ok: false, error: `${network} returned null (no product available)` });
      return json(res, 200, { ok: true, product: { name: product.name, source: product.source, siteUrl: product.siteUrl, price: product.price || null } });
    } catch (err) {
      return json(res, 500, { ok: false, error: err.message });
    }
  }

  if (path === '/api/caption/regenerate' && req.method === 'POST') {
    try {
      const body = JSON.parse(await readBody(req));
      if (!body.productId) return json(res, 400, { ok: false, error: 'productId required' });
      const { clearCaptionCache } = await import('./ai/text.js');
      const cleared = clearCaptionCache(body.productId);
      return json(res, 200, { ok: true, cleared });
    } catch (err) {
      return json(res, 500, { ok: false, error: err.message });
    }
  }

  if (path === '/api/dry-run' && req.method === 'POST') {
    try {
      const { getProduct } = await import('./feeds/index.js');
      const { generatePostText } = await import('./ai/text.js');
      const { getTopTrends } = await import('./admitad/trends.js');
      const [product, trends] = await Promise.all([getProduct(wasRecentlyPosted), getTopTrends(3)]);
      const caption = await generatePostText(product, trends);
      return json(res, 200, {
        ok: true,
        product: { name: product.name, source: product.source, siteUrl: product.siteUrl, imageUrl: product.imageUrl || null, price: product.price || null, currency: product.currency || null },
        caption,
      });
    } catch (err) {
      return json(res, 500, { ok: false, error: err.message });
    }
  }
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(DASHBOARD_HTML);
}

export function startServer(getIsRunning, triggerRun, getMissingVars = () => []) {
  const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    const url = new URL(req.url, 'http://localhost');
    await routeRequest(req, res, url, getIsRunning, triggerRun, getMissingVars);
  });
  server.listen(PORT, () => {
    logger.info(`Dashboard listening on http://localhost:${PORT}`);
    startKeepAlive(PORT);
  });
  return server;
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', c => { data += c; if (data.length > 1e5) reject(new Error('Body too large')); });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

// ─── Keep-alive ──────────────────────────────────────────────────────────────

function startKeepAlive(port) {
  const host = process.env.SPACE_HOST
    ? `https://${process.env.SPACE_HOST}`
    : `http://localhost:${port}`;
  const url = `${host}/health`;
  setInterval(async () => {
    try {
      const { default: fetch } = await import('node-fetch');
      await fetch(url, { signal: AbortSignal.timeout(10_000) });
    } catch (err) {
      logger.warn(`Keep-alive ping failed: ${err.message}`);
    }
  }, 25 * 60 * 1000);
  logger.info(`Keep-alive self-ping active (every 25min → ${url})`);
}
