import http from 'http';
import { getDailySpend } from './utils/budget.js';
import { getRecentRuns } from './utils/metrics.js';
import { logger } from './utils/logger.js';

const PORT = parseInt(process.env.PORT || '7860', 10);

// ─── API helpers ────────────────────────────────────────────────────────────

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function getStatusPayload(isRunning) {
  const cap   = parseFloat(process.env.DAILY_COST_CAP_USD || '2.00');
  const alert = parseFloat(process.env.ALERT_COST_THRESHOLD_USD || '1.50');
  const spend = getDailySpend();
  const runs  = getRecentRuns(20);
  const today = new Date().toISOString().slice(0, 10);

  const postsToday   = runs.filter(r => r.success && r.timestamp?.startsWith(today)).length;
  const lastRun      = runs.at(-1) ?? null;
  const successRate  = runs.length
    ? Math.round((runs.filter(r => r.success).length / runs.length) * 100)
    : null;

  return {
    pipeline: { running: isRunning, schedule: process.env.CRON_SCHEDULE || '0 * * * *' },
    budget:   { spent: spend, cap, alert, pct: spend / cap },
    stats:    { postsToday, totalRuns: runs.length, successRate },
    lastRun,
    runs: [...runs].reverse(),
  };
}

// ─── Dashboard HTML ──────────────────────────────────────────────────────────

const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Auto-Affiliate · Dashboard</title>
<style>
  :root {
    --bg: #0a0f1e; --surface: #111827; --border: #1f2937;
    --text: #f1f5f9; --muted: #64748b; --accent: #6366f1;
    --green: #22c55e; --yellow: #f59e0b; --red: #ef4444;
    --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

  /* ── Layout ── */
  header { display: flex; align-items: center; justify-content: space-between;
           padding: 1.25rem 2rem; border-bottom: 1px solid var(--border); }
  .logo  { display: flex; align-items: center; gap: 0.6rem; font-size: 1.1rem; font-weight: 700; }
  .logo span { color: var(--accent); }
  main   { max-width: 1200px; margin: 0 auto; padding: 2rem; }

  /* ── Status pill ── */
  .pill { display: inline-flex; align-items: center; gap: 0.4rem;
          padding: 0.3rem 0.85rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
  .pill.idle    { background: #052e16; color: var(--green); }
  .pill.running { background: #422006; color: var(--yellow); }
  .pill.error   { background: #2d0e0e; color: var(--red); }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
  .dot.pulse { animation: pulse 1.4s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* ── KPI cards ── */
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
           gap: 1rem; margin-bottom: 2rem; }
  .card  { background: var(--surface); border: 1px solid var(--border);
           border-radius: var(--radius); padding: 1.25rem; }
  .card-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: .06em;
                color: var(--muted); margin-bottom: 0.5rem; }
  .card-value { font-size: 2rem; font-weight: 700; line-height: 1; }
  .card-sub   { font-size: 0.78rem; color: var(--muted); margin-top: 0.35rem; }

  /* ── Budget bar ── */
  .budget-bar { background: #1f2937; border-radius: 999px; height: 6px;
                margin-top: 0.6rem; overflow: hidden; }
  .budget-fill { height: 100%; border-radius: 999px; transition: width .6s; }

  /* ── Section ── */
  .section       { margin-bottom: 2rem; }
  .section-title { font-size: 0.85rem; font-weight: 600; color: var(--muted);
                   text-transform: uppercase; letter-spacing: .06em; margin-bottom: 1rem; }

  /* ── Last run card ── */
  .last-run { background: var(--surface); border: 1px solid var(--border);
              border-radius: var(--radius); padding: 1.25rem;
              display: flex; flex-wrap: wrap; gap: 1.5rem; align-items: flex-start; }
  .last-run-field { flex: 1; min-width: 140px; }
  .lrf-label { font-size: 0.72rem; color: var(--muted); margin-bottom: 0.25rem; }
  .lrf-value { font-size: 0.9rem; font-weight: 500; }

  /* ── Table ── */
  .table-wrap { background: var(--surface); border: 1px solid var(--border);
                border-radius: var(--radius); overflow: hidden; }
  table  { width: 100%; border-collapse: collapse; }
  thead th { background: #0f172a; padding: 0.75rem 1rem; text-align: left;
             font-size: 0.72rem; text-transform: uppercase; letter-spacing: .06em;
             color: var(--muted); white-space: nowrap; }
  tbody td { padding: 0.7rem 1rem; border-top: 1px solid var(--border);
             font-size: 0.85rem; white-space: nowrap; }
  tbody tr:hover td { background: #151e2e; }
  .badge { display: inline-flex; align-items: center; gap: 0.3rem;
           padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }
  .badge.ok  { background: #052e16; color: var(--green); }
  .badge.err { background: #2d0e0e; color: var(--red); }
  .img-badge { background: #1e1b4b; color: #a5b4fc; }
  .err-cell  { color: var(--red); max-width: 240px; overflow: hidden;
               text-overflow: ellipsis; white-space: nowrap; }

  /* ── Setup banner ── */
  .setup-banner { background: #1c1408; border: 1px solid #92400e; border-radius: var(--radius);
                  padding: 1.25rem 1.5rem; margin-bottom: 2rem; }
  .setup-banner h2 { color: #fbbf24; font-size: 1rem; margin-bottom: 0.5rem; }
  .setup-banner p  { color: #d97706; font-size: 0.875rem; margin-bottom: 0.75rem; }
  .setup-banner ul { color: #fcd34d; font-size: 0.875rem; padding-left: 1.25rem; }
  .setup-banner li { margin-bottom: 0.2rem; font-family: monospace; }

  /* ── Trigger button ── */
  .btn { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.55rem 1.25rem;
         border-radius: 8px; border: none; font-size: 0.875rem; font-weight: 600;
         cursor: pointer; transition: opacity .2s; }
  .btn:disabled { opacity: .45; cursor: not-allowed; }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:not(:disabled):hover { opacity: .85; }

  /* ── Footer ── */
  footer { text-align: center; color: var(--muted); font-size: 0.75rem;
           padding: 2rem; border-top: 1px solid var(--border); }
  #last-updated { color: var(--muted); font-size: 0.78rem; }
</style>
</head>
<body>

<header>
  <div class="logo">🤖 <span>Auto-Affiliate</span> Pipeline</div>
  <div style="display:flex;align-items:center;gap:1rem">
    <span id="status-pill" class="pill idle"><span class="dot"></span> Idle</span>
    <span id="last-updated"></span>
  </div>
</header>

<main>

  <!-- Setup banner (hidden when configured) -->
  <div id="setup-banner" class="setup-banner" style="display:none">
    <h2>⚠️ Configuration required</h2>
    <p>Add the following secrets in your HuggingFace Space → Settings → Variables and secrets:</p>
    <ul id="missing-vars-list"></ul>
  </div>

  <!-- KPI cards -->
  <div class="cards" id="kpi-cards">
    <div class="card">
      <div class="card-label">Posts today</div>
      <div class="card-value" id="kpi-posts">—</div>
      <div class="card-sub">Target: 24/day</div>
    </div>
    <div class="card">
      <div class="card-label">Success rate</div>
      <div class="card-value" id="kpi-success">—</div>
      <div class="card-sub" id="kpi-success-sub">last runs</div>
    </div>
    <div class="card">
      <div class="card-label">Daily spend</div>
      <div class="card-value" id="kpi-spend">—</div>
      <div class="card-sub" id="kpi-spend-sub">of $— cap</div>
      <div class="budget-bar"><div class="budget-fill" id="budget-fill" style="width:0%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Schedule</div>
      <div class="card-value" style="font-size:1rem;padding-top:.35rem" id="kpi-schedule">—</div>
      <div class="card-sub">cron expression</div>
    </div>
  </div>

  <!-- Last run -->
  <div class="section">
    <div class="section-title">Last run</div>
    <div class="last-run" id="last-run-card">
      <div class="last-run-field"><div class="lrf-label">Time</div><div class="lrf-value" id="lr-time">—</div></div>
      <div class="last-run-field"><div class="lrf-label">Product</div><div class="lrf-value" id="lr-product">—</div></div>
      <div class="last-run-field"><div class="lrf-label">Trend</div><div class="lrf-value" id="lr-trend">—</div></div>
      <div class="last-run-field"><div class="lrf-label">Image source</div><div class="lrf-value" id="lr-img">—</div></div>
      <div class="last-run-field"><div class="lrf-label">Duration</div><div class="lrf-value" id="lr-dur">—</div></div>
      <div class="last-run-field"><div class="lrf-label">Post</div>
        <div class="lrf-value"><a id="lr-uri" href="#" target="_blank" style="color:#818cf8;word-break:break-all">—</a></div>
      </div>
    </div>
  </div>

  <!-- Controls -->
  <div class="section" style="display:flex;align-items:center;gap:1rem">
    <button class="btn btn-primary" id="run-btn" onclick="triggerRun()">
      ▶ Run now
    </button>
    <span id="run-msg" style="font-size:0.85rem;color:var(--muted)"></span>
  </div>

  <!-- Run history -->
  <div class="section">
    <div class="section-title">Run history</div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Status</th><th>Time (UTC)</th><th>Product</th>
            <th>Caption</th><th>Image</th><th>Duration</th><th>Error</th>
          </tr>
        </thead>
        <tbody id="runs-body">
          <tr><td colspan="7" style="text-align:center;color:var(--muted);padding:2rem">Loading…</td></tr>
        </tbody>
      </table>
    </div>
  </div>

</main>

<footer>Auto-Affiliate Pipeline · Admitad → Groq → HuggingFace → Bluesky · <a href="/health" style="color:var(--muted)">/health</a></footer>

<script>
let polling = null;

async function fetchStatus() {
  try {
    const d = await fetch('/api/status').then(r => r.json());
    render(d);
  } catch(e) {
    document.getElementById('run-msg').textContent = 'Could not reach API';
  }
}

function render(d) {
  // Setup banner
  const banner = document.getElementById('setup-banner');
  if (d.missingVars && d.missingVars.length) {
    banner.style.display = 'block';
    document.getElementById('missing-vars-list').innerHTML =
      d.missingVars.map(v => '<li>' + v + '</li>').join('');
  } else {
    banner.style.display = 'none';
  }

  // Status pill
  const pill = document.getElementById('status-pill');
  if (d.pipeline.running) {
    pill.className = 'pill running';
    pill.innerHTML = '<span class="dot pulse"></span> Running';
  } else {
    pill.className = 'pill idle';
    pill.innerHTML = '<span class="dot"></span> Idle';
  }

  // KPIs
  document.getElementById('kpi-posts').textContent    = d.stats.postsToday;
  document.getElementById('kpi-success').textContent  = d.stats.successRate != null ? d.stats.successRate + '%' : '—';
  document.getElementById('kpi-success-sub').textContent = 'last ' + d.stats.totalRuns + ' runs';
  document.getElementById('kpi-schedule').textContent  = d.pipeline.schedule;

  // Budget
  const spend = d.budget.spent, cap = d.budget.cap, pct = d.budget.pct;
  document.getElementById('kpi-spend').textContent = '$' + spend.toFixed(4);
  document.getElementById('kpi-spend-sub').textContent = 'of $' + cap.toFixed(2) + ' cap';
  const fill = document.getElementById('budget-fill');
  fill.style.width = Math.min(pct * 100, 100) + '%';
  fill.style.background = pct >= 1 ? '#ef4444' : pct >= d.budget.alert/cap ? '#f59e0b' : '#22c55e';

  // Last run
  const lr = d.lastRun;
  if (lr) {
    document.getElementById('lr-time').textContent    = lr.timestamp?.replace('T',' ').slice(0,19) || '—';
    document.getElementById('lr-product').textContent = lr.product || '—';
    document.getElementById('lr-trend').textContent   = lr.trend || '—';
    document.getElementById('lr-img').textContent     = lr.imageSource || '—';
    document.getElementById('lr-dur').textContent     = lr.durationMs ? (lr.durationMs/1000).toFixed(1)+'s' : '—';
    const uriEl = document.getElementById('lr-uri');
    if (lr.postUri) { uriEl.href = lr.postUri; uriEl.textContent = lr.postUri.slice(0,40)+'…'; }
    else            { uriEl.href = '#'; uriEl.textContent = '—'; }
  }

  // Run trigger button
  document.getElementById('run-btn').disabled = d.pipeline.running;

  // Table
  const tbody = document.getElementById('runs-body');
  if (!d.runs || d.runs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:2rem">No runs yet</td></tr>';
    return;
  }
  tbody.innerHTML = d.runs.map(r => {
    const ok  = r.success
      ? '<span class="badge ok">✓ OK</span>'
      : '<span class="badge err">✗ Fail</span>';
    const ts  = (r.timestamp||'').replace('T',' ').slice(0,19);
    const cap = r.captionChars ? r.captionChars+'c' : '—';
    const img = r.imageGenerated
      ? '<span class="badge img-badge">🖼 '+(r.imageSource||'')+'</span>'
      : '<span style="color:var(--muted)">—</span>';
    const dur = r.durationMs ? (r.durationMs/1000).toFixed(1)+'s' : '—';
    const err = r.error
      ? '<span class="err-cell" title="'+esc(r.error)+'">'+esc(r.error.slice(0,50))+'</span>'
      : '<span style="color:var(--muted)">—</span>';
    return '<tr><td>'+ok+'</td><td>'+ts+'</td><td>'+(r.product||'—')+'</td><td>'+cap+'</td><td>'+img+'</td><td>'+dur+'</td><td>'+err+'</td></tr>';
  }).join('');

  document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function triggerRun() {
  const btn = document.getElementById('run-btn');
  const msg = document.getElementById('run-msg');
  btn.disabled = true;
  msg.textContent = 'Triggering…';
  try {
    const res = await fetch('/api/run', { method: 'POST' });
    const d   = await res.json();
    if (d.ok) {
      msg.textContent = 'Run started — refreshing…';
      setTimeout(fetchStatus, 1500);
    } else {
      msg.textContent = d.error || 'Could not start run';
      btn.disabled = false;
    }
  } catch(e) {
    msg.textContent = 'Request failed';
    btn.disabled = false;
  }
}

// Poll every 20s
fetchStatus();
polling = setInterval(fetchStatus, 20_000);
</script>
</body>
</html>`;

// ─── Server ──────────────────────────────────────────────────────────────────

export function startServer(getIsRunning, triggerRun, missingVars = []) {
  const server = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');

    if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      return res.end('ok');
    }

    if (req.url === '/api/status') {
      const payload = getStatusPayload(getIsRunning());
      payload.missingVars = missingVars;
      return json(res, 200, payload);
    }

    if (req.url === '/api/run' && req.method === 'POST') {
      if (missingVars.length) {
        return json(res, 503, { ok: false, error: `Not configured — set: ${missingVars.join(', ')}` });
      }
      if (getIsRunning()) {
        return json(res, 409, { ok: false, error: 'Pipeline already running' });
      }
      triggerRun('manual');
      return json(res, 202, { ok: true, message: 'Run triggered' });
    }

    // Dashboard
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(DASHBOARD_HTML);
  });

  server.listen(PORT, () => {
    logger.info(`Dashboard listening on http://localhost:${PORT}`);
    startKeepAlive(PORT);
  });
  return server;
}

// ─── Keep-alive self-ping ────────────────────────────────────────────────────
// HF Spaces free tier sleeps after ~48h of no external traffic.
// We ping our own /health every 25 minutes so the Space stays awake indefinitely.

const PING_INTERVAL_MS = 25 * 60 * 1000; // 25 minutes

function startKeepAlive(port) {
  // HF injects SPACE_HOST; fall back to localhost for other environments
  const host = process.env.SPACE_HOST
    ? `https://${process.env.SPACE_HOST}`
    : `http://localhost:${port}`;
  const url = `${host}/health`;

  setInterval(async () => {
    try {
      const { default: fetch } = await import('node-fetch');
      const res = await fetch(url, { signal: AbortSignal.timeout(10_000) });
      logger.debug(`Keep-alive ping → ${url} [${res.status}]`);
    } catch (err) {
      logger.warn(`Keep-alive ping failed: ${err.message}`);
    }
  }, PING_INTERVAL_MS);

  logger.info(`Keep-alive self-ping active (every ${PING_INTERVAL_MS / 60000}min → ${url})`);
}
