import http from 'http';
import { getDailySpend } from './utils/budget.js';
import { getRecentRuns } from './utils/metrics.js';
import { logger } from './utils/logger.js';
import { getSettings, saveSettings, getSpaceHost } from './config/settings.js';
import { getOAuthClient, getConnectedDid, disconnectBluesky } from './auth/bluesky-oauth.js';

const PORT = parseInt(process.env.PORT || '7860', 10);

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
    pipeline:    { running: isRunning, schedule: settings.cronSchedule },
    budget:      { spent: spend, cap, alert, pct: spend / cap },
    stats:       {
      postsToday:   runs.filter(r => r.success && r.timestamp?.startsWith(today)).length,
      totalRuns:    runs.length,
      successRate:  runs.length ? Math.round(runs.filter(r=>r.success).length/runs.length*100) : null,
    },
    lastRun: runs.at(-1) ?? null,
    runs:    [...runs].reverse(),
  };
}

// ─── Dashboard HTML ──────────────────────────────────────────────────────────

const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="mitgo-verification" content="59e6a3e7-c3cf-4275-9389-f395e13df3a2" />
<script data-cfasync="false" data-no-defer="1">(function(){var s=document.createElement("script");s.async=1;s.src="https://emrldtp.cc/NTM2NzQw.js?t=536740";document.head.appendChild(s);})();</script>
<title>Auto-Affiliate · Dashboard</title>
<style>
:root{--bg:#0a0f1e;--surface:#111827;--border:#1f2937;--text:#f1f5f9;--muted:#64748b;--accent:#6366f1;--green:#22c55e;--yellow:#f59e0b;--red:#ef4444;--radius:12px}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
header{display:flex;align-items:center;justify-content:space-between;padding:1.25rem 2rem;border-bottom:1px solid var(--border)}
.logo{display:flex;align-items:center;gap:.6rem;font-size:1.1rem;font-weight:700}
.logo span{color:var(--accent)}
main{max-width:1200px;margin:0 auto;padding:2rem}

/* Tabs */
.tabs{display:flex;gap:.25rem;border-bottom:1px solid var(--border);margin-bottom:2rem}
.tab{padding:.6rem 1.25rem;border-radius:8px 8px 0 0;border:1px solid transparent;border-bottom:none;font-size:.875rem;font-weight:600;cursor:pointer;background:none;color:var(--muted);transition:.15s}
.tab.active{background:var(--surface);border-color:var(--border);color:var(--text)}
.tab:not(.active):hover{color:var(--text)}
.tab-panel{display:none}.tab-panel.active{display:block}

/* Pills */
.pill{display:inline-flex;align-items:center;gap:.4rem;padding:.3rem .85rem;border-radius:999px;font-size:.8rem;font-weight:600}
.pill.idle{background:#052e16;color:var(--green)}.pill.running{background:#422006;color:var(--yellow)}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.dot.pulse{animation:pulse 1.4s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* KPI cards */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1rem;margin-bottom:2rem}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem}
.card-label{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:.5rem}
.card-value{font-size:2rem;font-weight:700;line-height:1}
.card-sub{font-size:.78rem;color:var(--muted);margin-top:.35rem}
.budget-bar{background:#1f2937;border-radius:999px;height:6px;margin-top:.6rem;overflow:hidden}
.budget-fill{height:100%;border-radius:999px;transition:width .6s}

/* Sections */
.section{margin-bottom:2rem}
.section-title{font-size:.85rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:1rem}

/* Last run */
.last-run{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;display:flex;flex-wrap:wrap;gap:1.5rem}
.last-run-field{flex:1;min-width:140px}
.lrf-label{font-size:.72rem;color:var(--muted);margin-bottom:.25rem}
.lrf-value{font-size:.9rem;font-weight:500}

/* Table */
.table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
table{width:100%;border-collapse:collapse}
thead th{background:#0f172a;padding:.75rem 1rem;text-align:left;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);white-space:nowrap}
tbody td{padding:.7rem 1rem;border-top:1px solid var(--border);font-size:.85rem;white-space:nowrap}
tbody tr:hover td{background:#151e2e}
.badge{display:inline-flex;align-items:center;gap:.3rem;padding:.2rem .6rem;border-radius:6px;font-size:.75rem;font-weight:600}
.badge.ok{background:#052e16;color:var(--green)}.badge.err{background:#2d0e0e;color:var(--red)}
.badge.img{background:#1e1b4b;color:#a5b4fc}
.err-cell{color:var(--red);max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* Buttons */
.btn{display:inline-flex;align-items:center;gap:.5rem;padding:.55rem 1.25rem;border-radius:8px;border:none;font-size:.875rem;font-weight:600;cursor:pointer;transition:opacity .2s}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:not(:disabled):hover{opacity:.85}
.btn-success{background:#15803d;color:#fff}.btn-success:not(:disabled):hover{opacity:.85}
.btn-danger{background:#991b1b;color:#fff}.btn-danger:not(:disabled):hover{opacity:.85}
.btn-outline{background:none;border:1px solid var(--border);color:var(--text)}.btn-outline:hover{border-color:var(--accent);color:var(--accent)}

/* Account card */
.account-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.5rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem;margin-bottom:1rem}
.account-info{display:flex;align-items:center;gap:1rem}
.account-icon{width:44px;height:44px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.4rem}
.account-name{font-weight:700;margin-bottom:.2rem}
.account-status{font-size:.8rem;color:var(--muted)}
.account-status.connected{color:var(--green)}

/* Settings form */
.settings-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem;margin-bottom:2rem}
.field{display:flex;flex-direction:column;gap:.5rem}
.field label{font-size:.8rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.field input{background:#0f172a;border:1px solid var(--border);border-radius:8px;padding:.65rem .9rem;color:var(--text);font-size:.9rem;transition:.15s}
.field input:focus{outline:none;border-color:var(--accent)}
.field .hint{font-size:.75rem;color:var(--muted)}

/* OAuth connect form */
.connect-box{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.5rem;max-width:480px}
.connect-box h3{font-size:1rem;margin-bottom:.5rem}
.connect-box p{font-size:.875rem;color:var(--muted);margin-bottom:1rem}
.connect-row{display:flex;gap:.75rem;align-items:center}
.connect-row input{flex:1;background:#0f172a;border:1px solid var(--border);border-radius:8px;padding:.6rem .9rem;color:var(--text);font-size:.9rem}
.connect-row input:focus{outline:none;border-color:var(--accent)}

/* Alert */
.alert{padding:.9rem 1.1rem;border-radius:8px;font-size:.875rem;margin-bottom:1rem}
.alert-warn{background:#1c1408;border:1px solid #92400e;color:#fcd34d}
.alert-ok{background:#052e16;border:1px solid #166534;color:#86efac}

/* Footer */
footer{text-align:center;color:var(--muted);font-size:.75rem;padding:2rem;border-top:1px solid var(--border)}
#last-updated{color:var(--muted);font-size:.78rem}
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
  <!-- Tabs -->
  <div class="tabs">
    <button class="tab active" onclick="showTab('status')">📊 Status</button>
    <button class="tab" onclick="showTab('accounts')">🔗 Accounts</button>
    <button class="tab" onclick="showTab('config')">⚙️ Space Config</button>
  </div>

  <!-- ═══ STATUS TAB ═══ -->
  <div id="tab-status" class="tab-panel active">

    <div id="setup-banner" class="alert alert-warn" style="display:none">
      <strong>⚠ Setup required:</strong> <span id="missing-vars-text"></span> —
      go to the <button class="tab" style="display:inline;padding:.1rem .4rem" onclick="showTab('accounts')">Accounts tab</button> to connect.
    </div>

    <div class="cards">
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

    <div class="section">
      <div class="section-title">Last run</div>
      <div class="last-run">
        <div class="last-run-field"><div class="lrf-label">Time</div><div class="lrf-value" id="lr-time">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Product</div><div class="lrf-value" id="lr-product">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Trend</div><div class="lrf-value" id="lr-trend">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Image</div><div class="lrf-value" id="lr-img">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Duration</div><div class="lrf-value" id="lr-dur">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Post</div>
          <div class="lrf-value"><a id="lr-uri" href="#" target="_blank" style="color:#818cf8;word-break:break-all">—</a></div>
        </div>
      </div>
    </div>

    <div class="section" style="display:flex;align-items:center;gap:1rem">
      <button class="btn btn-primary" id="run-btn" onclick="triggerRun()">▶ Run now</button>
      <span id="run-msg" style="font-size:.85rem;color:var(--muted)"></span>
    </div>

    <div class="section">
      <div class="section-title">Run history</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Status</th><th>Time (UTC)</th><th>Product</th><th>Caption</th><th>Image</th><th>Duration</th><th>Error</th></tr></thead>
          <tbody id="runs-body"><tr><td colspan="7" style="text-align:center;color:var(--muted);padding:2rem">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ═══ ACCOUNTS TAB ═══ -->
  <div id="tab-accounts" class="tab-panel">

    <div class="section">
      <div class="section-title">Connected Accounts</div>

      <!-- Bluesky -->
      <div class="account-card" id="bsky-card">
        <div class="account-info">
          <div class="account-icon" style="background:#0a1628">🦋</div>
          <div>
            <div class="account-name">Bluesky</div>
            <div class="account-status" id="bsky-status">Checking…</div>
          </div>
        </div>
        <div id="bsky-actions"></div>
      </div>

      <!-- Future platforms -->
      <div class="account-card" style="opacity:.45">
        <div class="account-info">
          <div class="account-icon" style="background:#1a1a1a">𝕏</div>
          <div>
            <div class="account-name">X / Twitter</div>
            <div class="account-status">Coming soon</div>
          </div>
        </div>
        <button class="btn btn-outline" disabled>Connect</button>
      </div>

      <div class="account-card" style="opacity:.45">
        <div class="account-info">
          <div class="account-icon" style="background:#1a1235">🦣</div>
          <div>
            <div class="account-name">Mastodon</div>
            <div class="account-status">Coming soon</div>
          </div>
        </div>
        <button class="btn btn-outline" disabled>Connect</button>
      </div>
    </div>

    <!-- Connect Bluesky box (shown when not connected) -->
    <div id="bsky-connect-box" class="connect-box" style="display:none">
      <h3>Connect Bluesky via OAuth</h3>
      <p>Enter your Bluesky handle and click Connect. You'll be redirected to bsky.app to authorise — no passwords needed.</p>
      <div id="bsky-no-host" class="alert alert-warn" style="display:none">
        Space URL not configured. Go to <button onclick="showTab('config')" style="background:none;border:none;color:#fbbf24;cursor:pointer;text-decoration:underline">Space Config</button> and set your Space URL first.
      </div>
      <div class="connect-row" id="bsky-connect-row">
        <input id="bsky-handle-input" type="text" placeholder="you.bsky.social" />
        <button class="btn btn-success" onclick="connectBlueSky()">Connect →</button>
      </div>
      <p id="bsky-connect-msg" style="margin-top:.75rem;font-size:.8rem;color:var(--muted)"></p>
    </div>

  </div>

  <!-- ═══ SPACE CONFIG TAB ═══ -->
  <div id="tab-config" class="tab-panel">

    <div class="section">
      <div class="section-title">Space Configuration</div>
      <p style="font-size:.875rem;color:var(--muted);margin-bottom:1.5rem">
        Edit settings here — no code changes needed. Settings are saved to <code>data/settings.json</code>.
      </p>

      <div class="settings-grid" id="settings-form">
        <div class="field">
          <label>Space URL</label>
          <input id="cfg-spaceHost" type="url" placeholder="https://your-space.hf.space" />
          <span class="hint">Your HuggingFace Space public URL. Required for OAuth callbacks.</span>
        </div>
        <div class="field">
          <label>Cron Schedule</label>
          <input id="cfg-cronSchedule" type="text" placeholder="0 * * * *" />
          <span class="hint">How often to post. Default: every hour.</span>
        </div>
        <div class="field">
          <label>Max Post Length</label>
          <input id="cfg-maxPostLength" type="number" min="50" max="300" />
          <span class="hint">Characters per post. Bluesky max: 300.</span>
        </div>
        <div class="field">
          <label>Daily Cost Cap (USD)</label>
          <input id="cfg-dailyCostCap" type="number" step="0.01" min="0" />
          <span class="hint">Pipeline stops if AI spend exceeds this.</span>
        </div>
        <div class="field">
          <label>Alert Threshold (USD)</label>
          <input id="cfg-alertThreshold" type="number" step="0.01" min="0" />
          <span class="hint">Warn when spend crosses this amount.</span>
        </div>
      </div>

      <div style="display:flex;gap:1rem;align-items:center">
        <button class="btn btn-primary" onclick="saveConfig()">💾 Save Settings</button>
        <span id="cfg-msg" style="font-size:.85rem;color:var(--muted)"></span>
      </div>
    </div>

  </div>

</main>

<footer>Auto-Affiliate Pipeline · <a href="/health" style="color:var(--muted)">/health</a></footer>

<script>
// ── Tab switching ──
function showTab(name) {
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active', t.getAttribute('onclick').includes("'"+name+"'")));
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active', p.id==='tab-'+name));
}

// ── Status polling ──
let statusData = {};
async function fetchStatus() {
  try {
    statusData = await fetch('/api/status').then(r=>r.json());
    renderStatus(statusData);
  } catch(e) {}
}

function renderStatus(d) {
  const banner = document.getElementById('setup-banner');
  if (d.missingVars?.length) {
    banner.style.display='block';
    document.getElementById('missing-vars-text').textContent = d.missingVars.join(', ');
  } else banner.style.display='none';

  const pill = document.getElementById('status-pill');
  if (d.pipeline.running) {
    pill.className='pill running'; pill.innerHTML='<span class="dot pulse"></span> Running';
  } else {
    pill.className='pill idle'; pill.innerHTML='<span class="dot"></span> Idle';
  }

  document.getElementById('kpi-posts').textContent   = d.stats.postsToday;
  document.getElementById('kpi-success').textContent = d.stats.successRate!=null ? d.stats.successRate+'%' : '—';
  document.getElementById('kpi-success-sub').textContent = 'last '+d.stats.totalRuns+' runs';
  document.getElementById('kpi-schedule').textContent = d.pipeline.schedule;

  const {spent:sp,cap,pct,alert} = d.budget;
  document.getElementById('kpi-spend').textContent     = '$'+sp.toFixed(4);
  document.getElementById('kpi-spend-sub').textContent = 'of $'+cap.toFixed(2)+' cap';
  const fill = document.getElementById('budget-fill');
  fill.style.width = Math.min(pct*100,100)+'%';
  fill.style.background = pct>=1?'#ef4444':pct>=alert/cap?'#f59e0b':'#22c55e';

  const lr=d.lastRun;
  if (lr) {
    document.getElementById('lr-time').textContent    = (lr.timestamp||'').replace('T',' ').slice(0,19)||'—';
    document.getElementById('lr-product').textContent = lr.product||'—';
    document.getElementById('lr-trend').textContent   = lr.trend||'—';
    document.getElementById('lr-img').textContent     = lr.imageSource||'—';
    document.getElementById('lr-dur').textContent     = lr.durationMs?(lr.durationMs/1000).toFixed(1)+'s':'—';
    const ua=document.getElementById('lr-uri');
    if (lr.postUri){ua.href=lr.postUri;ua.textContent=lr.postUri.slice(0,40)+'…';}
    else{ua.href='#';ua.textContent='—';}
  }

  document.getElementById('run-btn').disabled = d.pipeline.running;

  const tbody=document.getElementById('runs-body');
  if (!d.runs?.length){tbody.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:2rem">No runs yet</td></tr>';return;}
  tbody.innerHTML=d.runs.map(r=>{
    const ok=r.success?'<span class="badge ok">✓ OK</span>':'<span class="badge err">✗ Fail</span>';
    const ts=(r.timestamp||'').replace('T',' ').slice(0,19);
    const img=r.imageGenerated?'<span class="badge img">🖼 '+(r.imageSource||'')+'</span>':'<span style="color:var(--muted)">—</span>';
    const err=r.error?'<span class="err-cell" title="'+esc(r.error)+'">'+esc(r.error.slice(0,50))+'</span>':'<span style="color:var(--muted)">—</span>';
    return '<tr><td>'+ok+'</td><td>'+ts+'</td><td>'+(r.product||'—')+'</td><td>'+(r.captionChars?r.captionChars+'c':'—')+'</td><td>'+img+'</td><td>'+(r.durationMs?(r.durationMs/1000).toFixed(1)+'s':'—')+'</td><td>'+err+'</td></tr>';
  }).join('');

  document.getElementById('last-updated').textContent='Updated '+new Date().toLocaleTimeString();
}

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

async function triggerRun() {
  const btn=document.getElementById('run-btn'),msg=document.getElementById('run-msg');
  btn.disabled=true; msg.textContent='Triggering…';
  try {
    const d=await fetch('/api/run',{method:'POST'}).then(r=>r.json());
    msg.textContent=d.ok?'Run started…':d.error||'Error'; if(d.ok)setTimeout(fetchStatus,1500);
    else btn.disabled=false;
  } catch{msg.textContent='Request failed';btn.disabled=false;}
}

fetchStatus();
setInterval(fetchStatus, 20000);

// ── Accounts ──
async function loadAccounts() {
  try {
    const d = await fetch('/api/accounts').then(r=>r.json());
    renderBskyStatus(d.bluesky);
  } catch {}
}

function renderBskyStatus(bsky) {
  const statusEl  = document.getElementById('bsky-status');
  const actionsEl = document.getElementById('bsky-actions');
  const connectBox = document.getElementById('bsky-connect-box');

  if (bsky?.connected) {
    statusEl.className = 'account-status connected';
    statusEl.textContent = 'Connected' + (bsky.did ? ' · '+bsky.did.slice(0,24)+'…' : '');
    actionsEl.innerHTML = '<button class="btn btn-danger" onclick="disconnectBsky()">Disconnect</button>';
    connectBox.style.display = 'none';
  } else {
    statusEl.className = 'account-status';
    statusEl.textContent = 'Not connected';
    actionsEl.innerHTML = '<button class="btn btn-success" onclick="showConnectBox()">Connect</button>';
    connectBox.style.display = 'none';
  }
}

function showConnectBox() {
  const box = document.getElementById('bsky-connect-box');
  box.style.display = 'block';
  fetch('/api/accounts').then(r=>r.json()).then(d=>{
    const noHost = document.getElementById('bsky-no-host');
    const row = document.getElementById('bsky-connect-row');
    if (!d.spaceConfigured) { noHost.style.display='block'; row.style.display='none'; }
    else { noHost.style.display='none'; row.style.display='flex'; }
  });
}

async function connectBlueSky() {
  const handle = document.getElementById('bsky-handle-input').value.trim();
  if (!handle) { document.getElementById('bsky-connect-msg').textContent='Enter your handle first.'; return; }
  document.getElementById('bsky-connect-msg').textContent = 'Redirecting to Bluesky…';
  try {
    const d = await fetch('/oauth/bsky/start?handle='+encodeURIComponent(handle)).then(r=>r.json());
    if (d.url) window.location.href = d.url;
    else document.getElementById('bsky-connect-msg').textContent = d.error || 'Failed to start OAuth';
  } catch(e) {
    document.getElementById('bsky-connect-msg').textContent = 'Error: '+e.message;
  }
}

async function disconnectBsky() {
  if (!confirm('Disconnect Bluesky?')) return;
  await fetch('/api/accounts/bluesky/disconnect', {method:'POST'});
  loadAccounts();
}

loadAccounts();

// ── Config ──
async function loadConfig() {
  try {
    const d = await fetch('/api/settings').then(r=>r.json());
    document.getElementById('cfg-spaceHost').value     = d.spaceHost     || '';
    document.getElementById('cfg-cronSchedule').value  = d.cronSchedule  || '0 * * * *';
    document.getElementById('cfg-maxPostLength').value = d.maxPostLength  || 300;
    document.getElementById('cfg-dailyCostCap').value  = d.dailyCostCap  || 2.00;
    document.getElementById('cfg-alertThreshold').value= d.alertThreshold|| 1.50;
  } catch {}
}

async function saveConfig() {
  const msg = document.getElementById('cfg-msg');
  const payload = {
    spaceHost:      document.getElementById('cfg-spaceHost').value.trim(),
    cronSchedule:   document.getElementById('cfg-cronSchedule').value.trim(),
    maxPostLength:  parseInt(document.getElementById('cfg-maxPostLength').value,10),
    dailyCostCap:   parseFloat(document.getElementById('cfg-dailyCostCap').value),
    alertThreshold: parseFloat(document.getElementById('cfg-alertThreshold').value),
  };
  try {
    const d = await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json());
    msg.textContent = d.ok ? '✓ Saved' : (d.error||'Error');
    msg.style.color = d.ok ? 'var(--green)' : 'var(--red)';
  } catch(e) { msg.textContent='Error: '+e.message; msg.style.color='var(--red)'; }
}

loadConfig();
</script>
</body>
</html>`;

// ─── Server ──────────────────────────────────────────────────────────────────

export function startServer(getIsRunning, triggerRun, getMissingVars = () => []) {

  const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');

    const url = new URL(req.url, `http://localhost`);
    const path = url.pathname;

    // ── Health ──
    if (path === '/health') {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      return res.end('ok');
    }

    // ── Client metadata (required by AT Protocol OAuth) ──
    if (path === '/client-metadata.json') {
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

    // ── Status API ──
    if (path === '/api/status') {
      const payload = getStatusPayload(getIsRunning());
      payload.missingVars = getMissingVars();
      return json(res, 200, payload);
    }

    // ── Settings GET ──
    if (path === '/api/settings' && req.method === 'GET') {
      return json(res, 200, getSettings());
    }

    // ── Settings POST ──
    if (path === '/api/settings' && req.method === 'POST') {
      try {
        const body = await readBody(req);
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

    // ── Accounts status ──
    if (path === '/api/accounts' && req.method === 'GET') {
      const did = await getConnectedDid().catch(() => null);
      return json(res, 200, {
        spaceConfigured: !!getSpaceHost(),
        bluesky: { connected: !!did, did },
      });
    }

    // ── Disconnect Bluesky ──
    if (path === '/api/accounts/bluesky/disconnect' && req.method === 'POST') {
      await disconnectBluesky();
      return json(res, 200, { ok: true });
    }

    // ── OAuth: start Bluesky flow ──
    if (path === '/oauth/bsky/start') {
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

    // ── OAuth: callback ──
    if (path === '/oauth/callback') {
      const client = getOAuthClient();
      if (!client) {
        res.writeHead(302, { Location: '/?error=no_client' });
        return res.end();
      }
      try {
        const params = Object.fromEntries(url.searchParams);
        const { session } = await client.callback(new URLSearchParams(params));
        logger.info(`Bluesky OAuth connected: ${session.did}`);
        res.writeHead(302, { Location: '/?tab=accounts&connected=1' });
        return res.end();
      } catch (err) {
        logger.warn(`Bluesky OAuth callback failed: ${err.message}`);
        res.writeHead(302, { Location: '/?tab=accounts&error=' + encodeURIComponent(err.message) });
        return res.end();
      }
    }

    // ── Run trigger ──
    if (path === '/api/run' && req.method === 'POST') {
      const missing = getMissingVars();
      if (missing.length) return json(res, 503, { ok: false, error: `Not ready: ${missing.join(', ')}` });
      if (getIsRunning()) return json(res, 409, { ok: false, error: 'Pipeline already running' });
      triggerRun('manual');
      return json(res, 202, { ok: true, message: 'Run triggered' });
    }

    // ── Dashboard ──
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(DASHBOARD_HTML);
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
