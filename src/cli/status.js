#!/usr/bin/env node
import 'dotenv/config';
import { getDailySpend } from '../utils/budget.js';
import { getRecentRuns } from '../utils/metrics.js';

const cap = parseFloat(process.env.DAILY_COST_CAP_USD || '2.00');
const alert = parseFloat(process.env.ALERT_COST_THRESHOLD_USD || '1.50');
const spend = getDailySpend();
const runs = getRecentRuns(5);

const budgetPct = ((spend / cap) * 100).toFixed(1);
const budgetStatus = spend >= cap ? '🔴 CAP REACHED' : spend >= alert ? '🟡 ALERT' : '🟢 OK';

console.log('\n=== Auto-Affiliate Status ===\n');
console.log(`Budget today:  $${spend.toFixed(4)} / $${cap.toFixed(2)}  (${budgetPct}%)  ${budgetStatus}`);
console.log(`Alert at:      $${alert.toFixed(2)}`);
console.log('');

if (runs.length === 0) {
  console.log('No runs recorded yet.');
} else {
  console.log(`Last ${runs.length} runs (newest last):`);
  for (const r of runs) {
    const ts = r.timestamp.replace('T', ' ').slice(0, 19);
    const ok = r.success ? '✓' : '✗';
    const img = r.imageGenerated ? '[img]' : '[no-img]';
    const filtered = r.productsFiltered != null ? `${r.productsFiltered}/${r.productsFetched} products` : '';
    const cost = r.dailySpendUsd != null ? `$${r.dailySpendUsd.toFixed(4)}` : '';
    const dur = r.durationMs ? `${(r.durationMs / 1000).toFixed(1)}s` : '';
    const src = r.productSource ? `[${r.productSource}]` : '';
    const err = r.error ? ` ERR: ${r.error.slice(0, 60)}` : '';
    console.log(`  ${ok} ${ts}  ${src}  ${r.product || '?'}  ${img}  ${filtered}  ${cost}  ${dur}${err}`);
  }
}
console.log('');
