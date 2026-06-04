import http from 'http';
import { getDailySpend } from './utils/budget.js';
import { getRecentRuns } from './utils/metrics.js';
import { logger } from './utils/logger.js';

const PORT = parseInt(process.env.PORT || '7860', 10);

function statusHTML(isRunning) {
  const cap    = parseFloat(process.env.DAILY_COST_CAP_USD || '2.00');
  const alert  = parseFloat(process.env.ALERT_COST_THRESHOLD_USD || '1.50');
  const spend  = getDailySpend();
  const pct    = ((spend / cap) * 100).toFixed(1);
  const runs   = getRecentRuns(10);

  const budgetColor = spend >= cap ? '#ef4444' : spend >= alert ? '#f59e0b' : '#22c55e';

  const runRows = runs.length === 0
    ? '<tr><td colspan="7" style="text-align:center;color:#6b7280">No runs yet</td></tr>'
    : [...runs].reverse().map(r => {
        const ts  = r.timestamp.replace('T', ' ').slice(0, 19);
        const ok  = r.success ? '✅' : '❌';
        const img = r.imageGenerated ? '🖼️' : '—';
        const src = r.imageSource || '—';
        const dur = r.durationMs ? `${(r.durationMs / 1000).toFixed(1)}s` : '—';
        const err = r.error ? `<span style="color:#ef4444" title="${r.error}">${r.error.slice(0, 40)}…</span>` : '—';
        return `<tr>
          <td>${ok}</td>
          <td>${ts}</td>
          <td>${r.product || '—'}</td>
          <td>${img} ${src}</td>
          <td>${dur}</td>
          <td>${err}</td>
        </tr>`;
      }).join('');

  const pipelineStatus = isRunning
    ? '<span style="color:#f59e0b">⚙️ Running</span>'
    : '<span style="color:#22c55e">✅ Idle</span>';

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="60">
  <title>Auto-Affiliate Pipeline</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:2rem}
    h1{font-size:1.5rem;margin-bottom:0.25rem}
    .sub{color:#94a3b8;font-size:0.875rem;margin-bottom:2rem}
    .cards{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:2rem}
    .card{background:#1e293b;border-radius:0.75rem;padding:1.25rem;min-width:180px;flex:1}
    .card-label{font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}
    .card-value{font-size:1.75rem;font-weight:700;margin-top:0.25rem}
    table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:0.75rem;overflow:hidden}
    th{background:#334155;padding:0.75rem 1rem;text-align:left;font-size:0.75rem;color:#94a3b8;text-transform:uppercase}
    td{padding:0.75rem 1rem;border-top:1px solid #334155;font-size:0.875rem}
    tr:hover td{background:#273549}
    .refresh{color:#475569;font-size:0.75rem;margin-top:1rem}
  </style>
</head>
<body>
  <h1>🤖 Auto-Affiliate Pipeline</h1>
  <p class="sub">Autonomous Bluesky affiliate posts · Admitad → Groq → HuggingFace → Bluesky</p>

  <div class="cards">
    <div class="card">
      <div class="card-label">Pipeline</div>
      <div class="card-value" style="font-size:1.25rem">${pipelineStatus}</div>
    </div>
    <div class="card">
      <div class="card-label">Daily spend</div>
      <div class="card-value" style="color:${budgetColor}">$${spend.toFixed(4)}</div>
    </div>
    <div class="card">
      <div class="card-label">Budget cap</div>
      <div class="card-value">$${cap.toFixed(2)}</div>
    </div>
    <div class="card">
      <div class="card-label">Budget used</div>
      <div class="card-value" style="color:${budgetColor}">${pct}%</div>
    </div>
    <div class="card">
      <div class="card-label">Posts today</div>
      <div class="card-value">${runs.filter(r => r.success && r.timestamp?.startsWith(new Date().toISOString().slice(0,10))).length}</div>
    </div>
  </div>

  <table>
    <thead>
      <tr><th>Status</th><th>Time (UTC)</th><th>Product</th><th>Image</th><th>Duration</th><th>Error</th></tr>
    </thead>
    <tbody>${runRows}</tbody>
  </table>

  <p class="refresh">Auto-refreshes every 60s</p>
</body>
</html>`;
}

export function startServer(getIsRunning) {
  const server = http.createServer((req, res) => {
    if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end('ok');
      return;
    }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(statusHTML(getIsRunning()));
  });

  server.listen(PORT, () => logger.info(`Status server listening on port ${PORT}`));
  return server;
}
