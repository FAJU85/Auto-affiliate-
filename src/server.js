import http from 'http';
import { getDailySpend } from './utils/budget.js';
import { getRecentRuns, getDedupStatus, clearPostedStore, wasRecentlyPosted, getDailyNetworkStats, purgePostedBySource, getDedupBySource, getTopPosts, getNetworkHealth } from './utils/metrics.js';
import { logger, getRecentLogs } from './utils/logger.js';
import { getSettings, saveSettings, getSpaceHost } from './config/settings.js';
import { getOAuthClient, getConnectedDid, disconnectBluesky } from './auth/bluesky-oauth.js';
import { nextCronRun } from './utils/cron-next.js';

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
    <button class="tab" onclick="showTab('logs');fetchLogs()">🪵 Logs</button>
    <button class="tab" onclick="showTab('analytics');fetchStats()">📈 Analytics</button>
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
        <div class="card-sub" id="kpi-posts-sub">Limit: 24/day</div>
      </div>
      <div class="card">
        <div class="card-label">Success rate</div>
        <div class="card-value" id="kpi-success">—</div>
        <div class="card-sub" id="kpi-success-sub">last runs</div>
        <svg id="sparkline" viewBox="0 0 100 30" preserveAspectRatio="none" style="width:100%;height:30px;margin-top:.5rem;display:block"></svg>
      </div>
      <div class="card">
        <div class="card-label">Daily spend</div>
        <div class="card-value" id="kpi-spend">—</div>
        <div class="card-sub" id="kpi-spend-sub">of $— cap</div>
        <div class="budget-bar"><div class="budget-fill" id="budget-fill" style="width:0%"></div></div>
      </div>
      <div class="card">
        <div class="card-label">Avg quality</div>
        <div class="card-value" id="kpi-quality">—</div>
        <div class="card-sub">last 20 runs (0–100)</div>
      </div>
      <div class="card">
        <div class="card-label">Schedule</div>
        <div class="card-value" style="font-size:1rem;padding-top:.35rem" id="kpi-schedule">—</div>
        <div class="card-sub" id="kpi-posting-hours">posting hours: —</div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Last run</div>
      <div class="last-run">
        <div class="last-run-field"><div class="lrf-label">Time</div><div class="lrf-value" id="lr-time">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Product</div><div class="lrf-value" id="lr-product">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Network</div><div class="lrf-value" id="lr-source">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Trend</div><div class="lrf-value" id="lr-trend">—</div></div>
        <div class="last-run-field" style="grid-column:1/-1"><div class="lrf-label">Caption</div><div class="lrf-value" id="lr-caption" style="font-size:.82rem;color:var(--muted);white-space:pre-wrap">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Image</div><div class="lrf-value" id="lr-img">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Duration</div><div class="lrf-value" id="lr-dur">—</div></div>
        <div class="last-run-field"><div class="lrf-label">Post</div>
          <div class="lrf-value"><a id="lr-uri" href="#" target="_blank" style="color:#818cf8;word-break:break-all">—</a></div>
        </div>
      </div>
    </div>

    <div class="section" style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
      <button class="btn btn-primary" id="run-btn" onclick="triggerRun()">▶ Run now</button>
      <button class="btn btn-outline" id="dry-btn" onclick="dryRun()">🔍 Dry run</button>
      <button class="btn btn-outline" id="pause-btn" onclick="toggleScheduler()" style="font-size:.85rem">⏸ Pause scheduler</button>
      <span id="run-msg" style="font-size:.85rem;color:var(--muted)"></span>
    </div>
    <div id="dry-result" style="display:none;margin-top:1rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1.25rem;font-size:.875rem"></div>

    <div class="section">
      <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:.75rem">
        <div class="section-title" style="margin-bottom:0">Run history</div>
        <select id="run-filter-source" onchange="applyRunFilter()" style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:.25rem .5rem;font-size:.8rem;color:var(--text)">
          <option value="">All networks</option>
        </select>
        <select id="run-filter-status" onchange="applyRunFilter()" style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:.25rem .5rem;font-size:.8rem;color:var(--text)">
          <option value="">All statuses</option>
          <option value="ok">Success only</option>
          <option value="fail">Failures only</option>
        </select>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Status</th><th>Time (UTC)</th><th>Product</th><th>Network</th><th>Post</th><th>Image</th><th>Q</th><th>Duration</th><th>Error</th></tr></thead>
          <tbody id="runs-body"><tr><td colspan="8" style="text-align:center;color:var(--muted);padding:2rem">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Affiliate networks</div>
      <div id="networks-list" style="display:flex;flex-wrap:wrap;gap:.5rem;padding:.25rem 0">Loading…</div>
    </div>

    <div class="section">
      <div class="section-title">60-day dedup store</div>
      <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:.75rem">
        <span id="dedup-count" style="font-size:.9rem;color:var(--muted)">Loading…</span>
        <button id="dedup-clear-btn" onclick="clearDedup()" style="padding:.25rem .75rem;font-size:.8rem;background:#ef4444;color:#fff;border:none;border-radius:6px;cursor:pointer">Clear store</button>
        <span id="dedup-clear-msg" style="font-size:.8rem;color:var(--muted)"></span>
      </div>
      <div id="dedup-by-source" style="display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.5rem"></div>
      <div id="dedup-recent" style="display:flex;flex-wrap:wrap;gap:.4rem"></div>
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

    <!-- App-password alternative -->
    <div id="bsky-apppass-box" class="connect-box" style="display:none;margin-top:1rem">
      <h3>Or connect with App Password</h3>
      <p>Set <code>BSKY_HANDLE</code> and <code>BSKY_APP_PASSWORD</code> in your Space secrets — the pipeline will use them automatically on next run.</p>
      <p style="margin-top:.5rem;font-size:.8rem">Create an app password at <strong>bsky.app → Settings → App Passwords</strong>.</p>
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
          <label>Posting Hours (UTC)</label>
          <input id="cfg-postingHours" type="text" placeholder="8-22" />
          <span class="hint">UTC hour window, e.g. "8-22". Cron skips outside this window. Use "0-23" to always post.</span>
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

      <div class="section-title" style="margin-top:2rem">AI Post Prompt</div>
      <p style="font-size:.875rem;color:var(--muted);margin-bottom:1.25rem">
        Customise what the AI writes. Use <code>{name}</code>, <code>{category}</code>, <code>{description}</code>, <code>{trend}</code> as placeholders.
      </p>
      <div style="display:grid;gap:1.25rem;margin-bottom:1.5rem">
        <div class="field">
          <label>System Prompt</label>
          <textarea id="cfg-postSystemPrompt" rows="3"
            style="background:#0f172a;border:1px solid var(--border);border-radius:8px;padding:.65rem .9rem;color:var(--text);font-size:.875rem;resize:vertical;font-family:inherit;line-height:1.5"
          ></textarea>
          <span class="hint">Defines the AI's persona and constraints (tone, length, style).</span>
        </div>
        <div class="field">
          <label>User Message Template</label>
          <textarea id="cfg-postUserTemplate" rows="3"
            style="background:#0f172a;border:1px solid var(--border);border-radius:8px;padding:.65rem .9rem;color:var(--text);font-size:.875rem;resize:vertical;font-family:inherit;line-height:1.5"
          ></textarea>
          <span class="hint">The actual request sent per post. Placeholders: <code>{name}</code> <code>{category}</code> <code>{description}</code> <code>{price}</code> <code>{trend}</code> <code>{highlights}</code></span>
        </div>
      </div>

      <div style="display:flex;gap:1rem;align-items:center">
        <button class="btn btn-primary" onclick="saveConfig()">💾 Save Settings</button>
        <span id="cfg-msg" style="font-size:.85rem;color:var(--muted)"></span>
      </div>
    </div>

  </div>

  <!-- ═══ LOGS TAB ═══ -->
  <div id="tab-logs" class="tab-panel">
    <div class="section">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
        <div class="section-title" style="margin-bottom:0">Live Log Buffer (last 100)</div>
        <button class="btn btn-outline" onclick="fetchLogs()" style="font-size:.8rem;padding:.3rem .75rem">↻ Refresh</button>
      </div>
      <div id="log-output" style="background:#050b15;border:1px solid var(--border);border-radius:var(--radius);padding:1rem;font-family:monospace;font-size:.78rem;line-height:1.6;max-height:600px;overflow-y:auto;color:#94a3b8">Loading…</div>
    </div>
  </div>

  <!-- ═══ ANALYTICS TAB ═══ -->
  <div id="tab-analytics" class="tab-panel" style="display:none">
    <div class="section">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem;margin-bottom:1rem">
        <div class="section-title" style="margin:0">Daily Posts by Network</div>
        <div style="display:flex;gap:.5rem">
          <button onclick="fetchStats(7)" class="btn btn-outline" style="font-size:.75rem;padding:.25rem .6rem">7d</button>
          <button onclick="fetchStats(14)" class="btn btn-outline" style="font-size:.75rem;padding:.25rem .6rem">14d</button>
          <button onclick="fetchStats(30)" class="btn btn-outline" style="font-size:.75rem;padding:.25rem .6rem">30d</button>
        </div>
      </div>
      <div id="stats-chart" style="overflow-x:auto;min-height:220px">Loading…</div>
    </div>
    <div class="section">
      <div class="section-title" id="stats-totals-title">Post Totals (7 days)</div>
      <div id="stats-totals" style="display:flex;gap:1rem;flex-wrap:wrap"></div>
    </div>
    <div class="section">
      <div class="section-title">Network Health (last 100 runs)</div>
      <div id="network-health" style="display:flex;gap:.75rem;flex-wrap:wrap">Loading…</div>
    </div>
    <div class="section">
      <div class="section-title">Top Posts by Engagement (last 30 days)</div>
      <div id="top-posts" style="font-size:.85rem;color:var(--muted)">Loading…</div>
    </div>
  </div>

</main>

<footer>Auto-Affiliate Pipeline · <a href="/health" style="color:var(--muted)">/health</a> · <a href="/api/history/csv" style="color:var(--muted)">Export CSV</a></footer>

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
    const [status, networks] = await Promise.all([
      fetch('/api/status').then(r=>r.json()),
      fetch('/api/networks').then(r=>r.json()),
    ]);
    statusData = status;
    renderStatus(statusData);
    renderNetworks(networks);
  } catch(e) {
    const pill = document.getElementById('status-pill');
    if (pill && !pill.classList.contains('running')) {
      pill.className = 'pill'; pill.innerHTML = '<span class="dot" style="background:#ef4444"></span> Offline';
    }
  }
}

function renderLastRun(lr) {
  if (!lr) return;
  document.getElementById('lr-time').textContent    = (lr.timestamp||'').replace('T',' ').slice(0,19)||'—';
  document.getElementById('lr-product').textContent = lr.product||'—';
  document.getElementById('lr-source').textContent  = lr.productSource||'—';
  document.getElementById('lr-trend').textContent   = lr.trend||'—';
  const captionEl = document.getElementById('lr-caption');
  if (captionEl) captionEl.textContent = lr.caption ? lr.caption.slice(0, 200) + (lr.caption.length > 200 ? '…' : '') : '—';
  document.getElementById('lr-img').textContent     = lr.imageSource||'—';
  document.getElementById('lr-dur').textContent     = lr.durationMs?(lr.durationMs/1000).toFixed(1)+'s':'—';
  const ua=document.getElementById('lr-uri');
  if (lr.postUri){ua.href=lr.postUri;ua.textContent=lr.postUri.slice(0,40)+'…';}
  else{ua.href='#';ua.textContent='—';}
}

let _allRuns = [];
function applyRunFilter() {
  const src = document.getElementById('run-filter-source')?.value || '';
  const status = document.getElementById('run-filter-status')?.value || '';
  let filtered = _allRuns;
  if (src) filtered = filtered.filter(r => r.productSource === src);
  if (status === 'ok') filtered = filtered.filter(r => r.success);
  if (status === 'fail') filtered = filtered.filter(r => !r.success);
  renderRunHistoryRows(filtered);
}

function renderRunHistory(runs) {
  _allRuns = runs || [];
  // Populate source filter
  const sel = document.getElementById('run-filter-source');
  if (sel) {
    const sources = [...new Set(runs.map(r => r.productSource).filter(Boolean))].sort();
    const current = sel.value;
    sel.innerHTML = '<option value="">All networks</option>' + sources.map(s => \`<option value="${esc(s)}"${s===current?' selected':''}>${esc(s)}</option>\`).join('');
  }
  applyRunFilter();
}

function renderRunHistoryRows(runs) {
  const tbody=document.getElementById('runs-body');
  if (!runs?.length){tbody.innerHTML='<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:2rem">No runs match filter</td></tr>';return;}
  tbody.innerHTML=runs.map(r=>{
    const ok=r.success?'<span class="badge ok">✓ OK</span>':'<span class="badge err">✗ Fail</span>';
    const ts=(r.timestamp||'').replace('T',' ').slice(0,19);
    const src=r.productSource?'<span class="badge img">'+esc(r.productSource)+'</span>':'<span style="color:var(--muted)">—</span>';
    const img=r.imageGenerated?'<span class="badge img">🖼 '+(r.imageSource||'')+'</span>':'<span style="color:var(--muted)">—</span>';
    const qs=typeof r.qualityScore==='number'?'<span style="font-weight:600;color:'+(r.qualityScore>=70?'var(--green)':r.qualityScore>=40?'var(--yellow)':'var(--red)')+'">'+r.qualityScore+'</span>':'<span style="color:var(--muted)">—</span>';
    const err=r.error?'<span class="err-cell" title="'+esc(r.error)+'">'+esc(r.error.slice(0,50))+'</span>':'<span style="color:var(--muted)">—</span>';
    const postLink=r.postUri?'<a href="'+esc(r.postUri)+'" target="_blank" rel="noopener" style="font-size:.75rem;color:var(--accent)" title="'+esc(r.caption||'')+'">view</a>':'<span style="color:var(--muted)">—</span>';
    return '<tr><td>'+ok+'</td><td>'+ts+'</td><td title="'+esc(r.caption||'')+'">'+(r.product||'—')+'</td><td>'+src+'</td><td>'+postLink+'</td><td>'+img+'</td><td>'+qs+'</td><td>'+(r.durationMs?(r.durationMs/1000).toFixed(1)+'s':'—')+'</td><td>'+err+'</td></tr>';
  }).join('');
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
  const maxPosts = d.stats.maxPostsPerDay || 24;
  const postsSub = document.getElementById('kpi-posts-sub');
  if (postsSub) postsSub.textContent = 'Limit: ' + maxPosts + '/day';
  document.getElementById('kpi-success').textContent = d.stats.successRate!=null ? d.stats.successRate+'%' : '—';
  document.getElementById('kpi-success-sub').textContent = 'last '+d.stats.totalRuns+' runs';
  document.getElementById('kpi-schedule').textContent = d.pipeline.schedule;
  document.getElementById('kpi-posting-hours').textContent = 'posting hours (UTC): ' + (d.pipeline.postingHours || '8-22');
  if (d.pipeline.nextRun) {
    const nr = new Date(d.pipeline.nextRun);
    const diffMs = nr - Date.now();
    const diffMin = Math.max(0, Math.floor(diffMs / 60000));
    const countdown = diffMin < 60 ? \`${diffMin}m\` : \`${Math.floor(diffMin/60)}h${diffMin%60 ? diffMin%60+'m' : ''}\`;
    document.getElementById('kpi-posting-hours').textContent = \`next run in ${countdown} · hours (UTC): ${d.pipeline.postingHours || '8-22'}\`;
  } else {
    document.getElementById('kpi-posting-hours').textContent = 'posting hours (UTC): ' + (d.pipeline.postingHours || '8-22');
  }

  const {spent:sp,cap,pct,alert} = d.budget;
  document.getElementById('kpi-spend').textContent     = '$'+sp.toFixed(4);
  document.getElementById('kpi-spend-sub').textContent = 'of $'+cap.toFixed(2)+' cap';
  const fill = document.getElementById('budget-fill');
  fill.style.width = Math.min(pct*100,100)+'%';
  fill.style.background = pct>=1?'#ef4444':pct>=alert/cap?'#f59e0b':'#22c55e';

  // Average quality score KPI
  const qualEl = document.getElementById('kpi-quality');
  if (qualEl && d.runs?.length) {
    const scored = d.runs.filter(r => r.success && typeof r.qualityScore === 'number');
    if (scored.length > 0) {
      const avg = Math.round(scored.reduce((a, r) => a + r.qualityScore, 0) / scored.length);
      qualEl.textContent = avg + '/100';
      qualEl.style.color = avg >= 70 ? 'var(--green)' : avg >= 40 ? 'var(--yellow)' : 'var(--red)';
    } else {
      qualEl.textContent = '—';
    }
  }

  renderLastRun(d.lastRun);
  document.getElementById('run-btn').disabled = d.pipeline.running;
  adjustPollRate(d.pipeline.running);
  if (typeof d.pipeline.paused === 'boolean' && d.pipeline.paused !== _schedulerPaused) {
    _schedulerPaused = d.pipeline.paused;
    const pb = document.getElementById('pause-btn');
    if (pb) pb.textContent = _schedulerPaused ? '▶ Resume scheduler' : '⏸ Pause scheduler';
  }
  renderSparkline(d.runs);
  renderRunHistory(d.runs);
  document.getElementById('last-updated').textContent='Updated '+new Date().toLocaleTimeString();
}

function renderNetworks(networks) {
  const el = document.getElementById('networks-list');
  if (!el || !Array.isArray(networks)) return;
  el.innerHTML = networks.map(function(n) {
    const color = n.enabled ? (n.lastError ? '#f59e0b' : '#22c55e') : '#6b7280';
    const icon  = n.enabled ? (n.lastError ? '&#9888;' : '&#10003;') : '&#10007;';
    const tip   = n.lastError ? ' title="Last error: '+esc(n.lastError)+'"' : '';
    const cnt   = n.selectCount > 0 ? ' <span style="opacity:.6;font-size:.7rem">×'+n.selectCount+'</span>' : '';
    const testBtn = n.enabled ? ' <button onclick="testNetwork(\''+esc(n.key)+'\')" style="padding:0 .4rem;font-size:.7rem;background:#1e293b;border:1px solid #334155;border-radius:4px;color:#94a3b8;cursor:pointer;line-height:1.5">test</button>' : '';
    return '<span'+tip+' style="display:inline-flex;align-items:center;gap:.3rem;background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:.25rem .75rem;font-size:.8rem;color:'+color+';cursor:'+(n.lastError?'help':'default')+'">'+icon+' '+esc(n.label)+cnt+testBtn+'</span>';
  }).join('');
}

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

function renderSparkline(runs) {
  const svg = document.getElementById('sparkline');
  if (!svg || !runs?.length) return;
  const pts = runs.slice(-20).map(r => r.success ? 1 : 0);
  if (pts.length < 2) return;
  const w = 100, h = 30, step = w / (pts.length - 1);
  const points = pts.map((v,i) => \`${(i*step).toFixed(1)},${v ? 4 : h-4}\`).join(' ');
  svg.innerHTML = '<polyline points="'+points+'" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    + pts.map((v,i)=>'<circle cx="'+(i*step).toFixed(1)+'" cy="'+(v?4:h-4)+'" r="2.5" fill="'+(v?'#22c55e':'#ef4444')+'"/>').join('');
}

async function triggerRun() {
  const btn=document.getElementById('run-btn'),msg=document.getElementById('run-msg');
  btn.disabled=true; msg.textContent='Triggering…';
  try {
    const d=await fetch('/api/run',{method:'POST'}).then(r=>r.json());
    msg.textContent=d.ok?'Run started…':d.error||'Error'; if(d.ok)setTimeout(fetchStatus,1500);
    else btn.disabled=false;
  } catch{msg.textContent='Request failed';btn.disabled=false;}
}

let _schedulerPaused = false;
async function toggleScheduler() {
  const btn = document.getElementById('pause-btn');
  const msg = document.getElementById('run-msg');
  const endpoint = _schedulerPaused ? '/api/schedule/resume' : '/api/schedule/pause';
  try {
    const d = await fetch(endpoint, { method: 'POST' }).then(r => r.json());
    if (d.ok) {
      _schedulerPaused = d.paused;
      btn.textContent = _schedulerPaused ? '▶ Resume scheduler' : '⏸ Pause scheduler';
      msg.textContent = _schedulerPaused ? 'Scheduler paused' : 'Scheduler resumed';
      setTimeout(() => { msg.textContent = ''; }, 4000);
    }
  } catch { msg.textContent = 'Request failed'; }
}

async function dryRun() {
  const btn=document.getElementById('dry-btn'), msg=document.getElementById('run-msg');
  const box=document.getElementById('dry-result');
  btn.disabled=true; msg.textContent='Running dry test…'; box.style.display='none';
  try {
    const d=await fetch('/api/dry-run',{method:'POST'}).then(r=>r.json());
    if (d.ok) {
      box.style.display='block';
      const priceStr = d.product.price ? ' · '+(d.product.currency==='USD'?'$':d.product.currency||'')+d.product.price : '';
      const imgHtml = d.product.imageUrl
        ? '<br><img src="'+esc(d.product.imageUrl)+'" alt="" style="max-width:200px;max-height:140px;border-radius:8px;margin-top:.5rem;object-fit:cover">'
        : '';
      box.innerHTML='<strong>Product:</strong> '+esc(d.product.name)+priceStr+' <span class="badge img">'+esc(d.product.source)+'</span>'
        +'<br><strong>URL:</strong> <a href="'+esc(d.product.siteUrl)+'" target="_blank" rel="noopener" style="color:var(--accent);font-size:.8rem">'+esc(d.product.siteUrl.slice(0,60))+'…</a>'
        +imgHtml
        +'<br><br><strong>Caption preview:</strong><br><em style="color:var(--muted)">'+esc(d.caption)+'</em>'
        +'<br><button onclick="navigator.clipboard.writeText('+JSON.stringify(d.caption+'\n\n'+d.product.siteUrl)+')" style="margin-top:.5rem;padding:.2rem .6rem;font-size:.75rem;background:#1e293b;border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer">Copy text</button>';
      msg.textContent='Dry run complete ✓';
    } else {
      msg.textContent='Dry run error: '+(d.error||'unknown');
    }
  } catch(e) { msg.textContent='Request failed'; }
  btn.disabled=false;
}

async function fetchDedup() {
  try {
    const d = await fetch('/api/dedup').then(r=>r.json());
    const el = document.getElementById('dedup-count');
    if (el) el.textContent = d.total + ' active entries (60-day window)';
    const bsEl = document.getElementById('dedup-by-source');
    if (bsEl && d.bySource && Object.keys(d.bySource).length) {
      bsEl.innerHTML = Object.entries(d.bySource).sort((a,b)=>b[1]-a[1])
        .map(([src, cnt]) => \`<span style="background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:.2rem .6rem;font-size:.78rem;color:var(--muted)"><b style="color:var(--text)">${cnt}</b> ${esc(src)}</span>\`).join('');
    } else if (bsEl) { bsEl.innerHTML = ''; }
    const rEl = document.getElementById('dedup-recent');
    if (rEl && d.recent?.length) {
      rEl.innerHTML = d.recent.map(e =>
        '<span title="'+esc(e.postedAt.replace('T',' ').slice(0,16))+' UTC" style="display:inline-flex;align-items:center;gap:.3rem;background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:.2rem .6rem;font-size:.75rem;color:var(--muted)">'
        +(e.source?'<span class="badge img" style="padding:.1rem .4rem;font-size:.7rem">'+esc(e.source)+'</span>':'')+esc((e.name||'').slice(0,30))+'</span>'
      ).join('');
    } else if (rEl) { rEl.innerHTML = ''; }
  } catch(e) {
    const el = document.getElementById('dedup-count');
    if (el) el.textContent = 'Dedup data unavailable';
  }
}

async function clearDedup() {
  const btn=document.getElementById('dedup-clear-btn'), msg=document.getElementById('dedup-clear-msg');
  if (!confirm('Clear the entire 60-day dedup store? All products will be eligible to post again.')) return;
  btn.disabled=true; msg.textContent='Clearing…';
  try {
    await fetch('/api/dedup',{method:'DELETE'});
    msg.textContent='Cleared!'; fetchDedup();
  } catch(e){msg.textContent='Error';}
  setTimeout(()=>{ btn.disabled=false; msg.textContent=''; }, 3000);
}

fetchStatus();
fetchDedup();
// Poll faster (5s) while pipeline is running, slow (20s) when idle
let _statusInterval = setInterval(fetchStatus, 20000);
function adjustPollRate(running) {
  clearInterval(_statusInterval);
  _statusInterval = setInterval(fetchStatus, running ? 5000 : 20000);
}
setInterval(fetchDedup, 60000);

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
    statusEl.textContent = 'Connected · ' + (bsky.did || '').slice(0,28) + '…';
    actionsEl.innerHTML = '<button class="btn btn-danger" onclick="disconnectBsky()">Disconnect</button>';
    connectBox.style.display = 'none';
  } else {
    statusEl.className = 'account-status';
    statusEl.textContent = bsky?.wasConnected
      ? '⚠ Session expired — Space was rebuilt. Reconnect below.'
      : 'Not connected';
    actionsEl.innerHTML = '<button class="btn btn-success" onclick="showConnectBox()">Connect</button>';
    connectBox.style.display = 'none';
  }
}

function showConnectBox() {
  const box = document.getElementById('bsky-connect-box');
  box.style.display = 'block';
  document.getElementById('bsky-apppass-box').style.display = 'block';
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
  const msg = document.getElementById('bsky-connect-msg');
  msg.textContent = 'Opening Bluesky authorisation…';
  try {
    const d = await fetch('/oauth/bsky/start?handle='+encodeURIComponent(handle)).then(r=>r.json());
    if (d.url) {
      window.open(d.url, '_blank', 'noopener');
      msg.textContent = 'A new tab opened — authorise there, then come back and the page will refresh automatically.';
      // Poll for connection every 3 s for up to 2 min
      const poll = setInterval(async () => {
        try {
          const s = await fetch('/api/accounts').then(r=>r.json());
          if (s?.bluesky?.connected) { clearInterval(poll); loadAccounts(); }
        } catch {}
      }, 3000);
      setTimeout(() => clearInterval(poll), 120_000);
    } else {
      msg.textContent = d.error || 'Failed to start OAuth';
    }
  } catch(e) {
    msg.textContent = 'Error: '+e.message;
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
    document.getElementById('cfg-spaceHost').value          = d.spaceHost          || '';
    document.getElementById('cfg-cronSchedule').value       = d.cronSchedule       || '0 * * * *';
    document.getElementById('cfg-maxPostLength').value      = d.maxPostLength       || 300;
    document.getElementById('cfg-postingHours').value       = d.postingHours        || '8-22';
    document.getElementById('cfg-dailyCostCap').value       = d.dailyCostCap       || 2.00;
    document.getElementById('cfg-alertThreshold').value     = d.alertThreshold     || 1.50;
    document.getElementById('cfg-postSystemPrompt').value   = d.postSystemPrompt   || '';
    document.getElementById('cfg-postUserTemplate').value   = d.postUserTemplate   || '';
  } catch {}
}

async function saveConfig() {
  const msg = document.getElementById('cfg-msg');
  const payload = {
    spaceHost:        document.getElementById('cfg-spaceHost').value.trim(),
    cronSchedule:     document.getElementById('cfg-cronSchedule').value.trim(),
    maxPostLength:    parseInt(document.getElementById('cfg-maxPostLength').value,10),
    postingHours:     document.getElementById('cfg-postingHours').value.trim() || '8-22',
    dailyCostCap:     parseFloat(document.getElementById('cfg-dailyCostCap').value),
    alertThreshold:   parseFloat(document.getElementById('cfg-alertThreshold').value),
    postSystemPrompt: document.getElementById('cfg-postSystemPrompt').value.trim(),
    postUserTemplate: document.getElementById('cfg-postUserTemplate').value.trim(),
  };
  try {
    const d = await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json());
    msg.textContent = d.ok ? '✓ Saved' : (d.error||'Error');
    msg.style.color = d.ok ? 'var(--green)' : 'var(--red)';
  } catch(e) { msg.textContent='Error: '+e.message; msg.style.color='var(--red)'; }
}

loadConfig();

// ── Network test ──
async function testNetwork(key) {
  const msg = document.getElementById('run-msg');
  msg.textContent = 'Testing '+key+'…';
  try {
    const d = await fetch('/api/network/test', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({network:key})}).then(r=>r.json());
    if (d.ok) {
      msg.textContent = '✓ '+key+': "'+d.product.name+'"'+(d.product.price?' $'+d.product.price:'');
    } else {
      msg.textContent = '✗ '+key+': '+(d.error||'failed');
    }
  } catch(e) { msg.textContent = '✗ '+key+': request error'; }
  setTimeout(()=>{ msg.textContent=''; }, 8000);
}

// ── Logs ──
const LEVEL_COLOR = { error:'#ef4444', warn:'#f59e0b', info:'#94a3b8', debug:'#4b5563' };
async function fetchLogs() {
  try {
    const logs = await fetch('/api/logs').then(r=>r.json());
    const el = document.getElementById('log-output');
    if (!el) return;
    if (!logs?.length) { el.textContent = 'No logs yet.'; return; }
    el.innerHTML = logs.slice().reverse().map(l => {
      const color = LEVEL_COLOR[l.level] || '#94a3b8';
      return '<div><span style="color:#4b5563">'+esc(l.ts.replace('T',' ').slice(0,19))+'</span> <span style="color:'+color+';font-weight:600">['+l.level.toUpperCase()+']</span> '+esc(l.msg)+'</div>';
    }).join('');
    el.scrollTop = 0;
  } catch(e) { const el=document.getElementById('log-output'); if(el)el.textContent='Failed to load logs.'; }
}

// ── Analytics ──
const NET_COLORS = {
  'admitad-feed':'#6366f1','admitad-api':'#8b5cf6','admitad-catalog':'#a78bfa',
  temu:'#f59e0b', cj:'#10b981', shareasale:'#ec4899', impact:'#3b82f6',
  takeads:'#f97316', travelpayouts:'#06b6d4', unknown:'#64748b'
};
async function fetchStats(days = 7) {
  try {
    const data = await fetch('/api/stats?days='+days).then(r=>r.json());
    const titleEl = document.getElementById('stats-totals-title');
    if (titleEl) titleEl.textContent = 'Post Totals ('+days+' days)';
    const chartEl = document.getElementById('stats-chart');
    const totalsEl = document.getElementById('stats-totals');
    if (!chartEl || !totalsEl) return;

    // Gather all networks present
    const allNets = [...new Set(data.flatMap(d => Object.keys(d.byNetwork)))].sort();
    const maxVal = Math.max(1, ...data.map(d => d.total));

    // Build SVG bar chart
    const barW = 40, gap = 12, padL = 32, padB = 30, padT = 10, h = 180;
    const totalW = padL + data.length * (barW + gap);
    let svg = \`<svg viewBox="0 0 ${totalW} ${h+padB+padT}" style="width:100%;max-width:700px;display:block">\`;
    // Grid lines
    for (let v of [0, Math.ceil(maxVal/2), maxVal]) {
      const y = padT + h - Math.round(v / maxVal * h);
      svg += \`<line x1="${padL}" y1="${y}" x2="${totalW}" y2="${y}" stroke="#1e293b" stroke-width="1"/>\`;
      svg += \`<text x="${padL-4}" y="${y+4}" text-anchor="end" font-size="10" fill="#64748b">${v}</text>\`;
    }
    data.forEach((day, i) => {
      const x = padL + i * (barW + gap);
      let yOff = h;
      allNets.forEach(net => {
        const cnt = day.byNetwork[net] || 0;
        if (!cnt) return;
        const barH = Math.round(cnt / maxVal * h);
        yOff -= barH;
        svg += \`<rect x="${x}" y="${padT+yOff}" width="${barW}" height="${barH}" fill="${NET_COLORS[net]||'#64748b'}" rx="2"><title>${net}: ${cnt}</title></rect>\`;
      });
      // X label
      svg += \`<text x="${x+barW/2}" y="${padT+h+16}" text-anchor="middle" font-size="10" fill="#94a3b8">${day.date.slice(5)}</text>\`;
      // Total on top
      if (day.total > 0)
        svg += \`<text x="${x+barW/2}" y="${padT+h-yOff-4}" text-anchor="middle" font-size="10" fill="#e2e8f0">${day.total}</text>\`;
    });
    svg += '</svg>';
    // Legend
    svg += '<div style="display:flex;gap:.75rem;flex-wrap:wrap;margin-top:.5rem">' +
      allNets.map(n => \`<span style="display:flex;align-items:center;gap:.3rem;font-size:.8rem"><span style="width:10px;height:10px;border-radius:2px;background:${NET_COLORS[n]||'#64748b'};display:inline-block"></span>${n}</span>\`).join('') +
      '</div>';
    chartEl.innerHTML = svg;

    // Totals chips
    const grandTotals = {};
    data.forEach(d => { Object.entries(d.byNetwork).forEach(([k,v]) => { grandTotals[k] = (grandTotals[k]||0)+v; }); });
    totalsEl.innerHTML = Object.entries(grandTotals).sort((a,b)=>b[1]-a[1])
      .map(([k,v]) => \`<div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:.5rem 1rem;text-align:center"><div style="font-size:.75rem;color:var(--muted)">${k}</div><div style="font-size:1.5rem;font-weight:700;color:${NET_COLORS[k]||'#94a3b8'}">${v}</div></div>\`).join('');

    // Network health
    const healthEl = document.getElementById('network-health');
    if (healthEl && statusData.networkHealth) {
      const health = statusData.networkHealth;
      const entries = Object.entries(health).sort((a,b) => b[1].attempts - a[1].attempts);
      if (entries.length === 0) {
        healthEl.textContent = 'No data yet.';
      } else {
        healthEl.innerHTML = entries.map(([net, h]) => {
          const pct = Math.round(h.rate * 100);
          const color = pct >= 80 ? 'var(--green)' : pct >= 50 ? 'var(--yellow)' : 'var(--red)';
          return \`<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:.6rem 1rem;min-width:130px">\` +
            \`<div style="font-size:.75rem;color:var(--muted);margin-bottom:.25rem">${esc(net)}</div>\` +
            \`<div style="font-size:1.4rem;font-weight:700;color:${color}">${pct}%</div>\` +
            \`<div style="font-size:.72rem;color:var(--muted)">${h.successes}/${h.attempts} runs</div>\` +
            \`</div>\`;
        }).join('');
      }
    }

    // Top posts
    const topEl = document.getElementById('top-posts');
    if (topEl) {
      try {
        const top = await fetch('/api/engagement/top').then(r => r.json());
        if (top.length === 0) {
          topEl.textContent = 'No engagement data yet — likes/reposts tracked 30min after each post.';
        } else {
          topEl.innerHTML = '<table style="width:100%;border-collapse:collapse">' +
            '<thead><tr><th style="text-align:left;padding:.3rem .5rem;color:var(--muted);font-weight:400">Product</th><th style="text-align:left;padding:.3rem .5rem;color:var(--muted);font-weight:400">Network</th><th style="padding:.3rem .5rem;color:var(--muted);font-weight:400">❤️</th><th style="padding:.3rem .5rem;color:var(--muted);font-weight:400">🔁</th><th style="padding:.3rem .5rem;color:var(--muted);font-weight:400">Link</th></tr></thead>' +
            '<tbody>' + top.map(r =>
              \`<tr style="border-top:1px solid var(--border)">\` +
              \`<td style="padding:.3rem .5rem">${esc(r.product||'—')}</td>\` +
              \`<td style="padding:.3rem .5rem"><span class="badge img">${esc(r.productSource||'—')}</span></td>\` +
              \`<td style="padding:.3rem .5rem;text-align:center;font-weight:700">${r.likes||0}</td>\` +
              \`<td style="padding:.3rem .5rem;text-align:center">${r.reposts||0}</td>\` +
              \`<td style="padding:.3rem .5rem">${r.postUri?'<a href="https://bsky.app/profile/post/'+esc(r.postUri.split('/').at(-1))+'" target="_blank" style="color:var(--accent)">view</a>':'—'}</td>\` +
              \`</tr>\`
            ).join('') + '</tbody></table>';
        }
      } catch { topEl.textContent = 'Engagement data unavailable.'; }
    }
  } catch(e) {
    const el = document.getElementById('stats-chart');
    if (el) el.textContent = 'Failed to load stats.';
  }
}
</script>
</body>
</html>`;

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
