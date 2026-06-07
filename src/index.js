import 'dotenv/config';
import cron from 'node-cron';
import { runPipeline } from './pipeline/run.js';
import { logger } from './utils/logger.js';
import { validateEnv } from './utils/env.js';
import { startServer, hasAnyNetworkEnabled } from './server.js';
import { restoreSessionFromSecrets } from './auth/bluesky-oauth.js';
import { isWithinPostingWindow } from './utils/schedule.js';

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
  if (trigger === 'cron' && !isWithinPostingWindow()) {
    logger.info(`[${trigger}] Outside posting window (POSTING_HOURS=${process.env.POSTING_HOURS || '8-22'} UTC) — skipping`);
    return;
  }
  pipelineRunning = true;
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
  if (!hasAnyNetworkEnabled()) {
    missing.push('affiliate network (set at least one: ADMITAD_FEED_URL, TEMU_AFFILIATE_URL_1, IMPACT_ACCOUNT_SID+AUTH_TOKEN, etc.)');
  }

  missingVars = missing;
  configured  = missing.length === 0;

  if (!configured) {
    logger.warn(`Not configured — ${missing.join(', ')}`);
    logger.warn('Dashboard running. Connect Bluesky and add at least one affiliate network to start posting.');
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
