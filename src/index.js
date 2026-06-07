import 'dotenv/config';
import fs from 'fs';
import path from 'path';
import cron from 'node-cron';
import { runPipeline } from './pipeline/run.js';
import { logger } from './utils/logger.js';
import { validateEnv } from './utils/env.js';
import { startServer } from './server.js';
import { restoreSessionFromSecrets } from './auth/bluesky-oauth.js';
import { dataPath } from './utils/datadir.js';

// Minimum gap between pipeline runs (30 min). Persisted to disk so container
// restarts cannot bypass it and trigger a flood of startup runs.
const MIN_RUN_GAP_MS = 30 * 60 * 1000;
const LAST_RUN_FILE  = dataPath('last-run.json');

function getLastRunTime() {
  try { return JSON.parse(fs.readFileSync(LAST_RUN_FILE, 'utf8')).ts || 0; }
  catch { return 0; }
}

function saveLastRunTime() {
  try {
    fs.mkdirSync(path.dirname(LAST_RUN_FILE), { recursive: true });
    fs.writeFileSync(LAST_RUN_FILE, JSON.stringify({ ts: Date.now() }));
  } catch {}
}

// Dashboard always starts first (HF Spaces requires port 7860 to be up fast)
let missingVars = [];
let configured  = false;
let pipelineRunning = false;

async function safePipelineRun(trigger) {
  if (!configured) {
    logger.warn(`[${trigger}] Skipped — Bluesky not connected`);
    return;
  }
  if (pipelineRunning) {
    logger.warn(`[${trigger}] Previous run still active — skipping this cycle`);
    return;
  }
  const msSinceLast = Date.now() - getLastRunTime();
  if (msSinceLast < MIN_RUN_GAP_MS) {
    const waitMin = Math.ceil((MIN_RUN_GAP_MS - msSinceLast) / 60000);
    logger.warn(`[${trigger}] Cooldown active — last run was ${Math.floor(msSinceLast / 60000)}m ago, next in ~${waitMin}m`);
    return;
  }
  pipelineRunning = true;
  saveLastRunTime();
  try {
    logger.info(`[${trigger}] Pipeline starting`);
    await runPipeline();
  } catch (err) {
    logger.error(`[${trigger}] Run error: ${err.message}`);
  } finally {
    pipelineRunning = false;
  }
}

// Start server immediately so HF Spaces health check passes
startServer(() => pipelineRunning, safePipelineRun, () => missingVars);

// Restore OAuth session from HF secrets if data dir was wiped by a rebuild
restoreSessionFromSecrets().catch(() => {});

// Then validate env + start scheduler
validateEnv().then(missing => {
  missingVars = missing;
  configured  = missing.length === 0;

  if (!configured) {
    logger.warn(`Not configured — ${missing.join(', ')}`);
    logger.warn('Dashboard running. Connect Bluesky via the dashboard to start posting.');
  }

  const SCHEDULE = process.env.CRON_SCHEDULE || '0 * * * *';
  logger.info(`Auto-Affiliate pipeline starting. Schedule: "${SCHEDULE}"`);

  if (configured) safePipelineRun('startup');

  const task = cron.schedule(SCHEDULE, () => safePipelineRun('cron'));

  async function shutdown(signal) {
    logger.info(`Received ${signal}, stopping scheduler`);
    task.stop();
    if (pipelineRunning) {
      const deadline = Date.now() + 90_000;
      while (pipelineRunning && Date.now() < deadline) {
        await new Promise(r => setTimeout(r, 500));
      }
    }
    logger.info('Shutdown complete');
    process.exit(0);
  }

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT',  () => shutdown('SIGINT'));
}).catch(err => {
  logger.error(`Startup validation failed: ${err.message}`);
  process.exit(1);
});
