import 'dotenv/config';
import cron from 'node-cron';
import { runPipeline } from './pipeline/run.js';
import { logger } from './utils/logger.js';
import { validateEnv } from './utils/env.js';
import { startServer } from './server.js';

validateEnv();

const SCHEDULE = process.env.CRON_SCHEDULE || '0 * * * *';

logger.info(`Auto-Affiliate pipeline starting. Schedule: "${SCHEDULE}"`);

let pipelineRunning = false;

// HTTP status server — required by HuggingFace Spaces (port 7860)
startServer(() => pipelineRunning);

async function safePipelineRun(trigger) {
  if (pipelineRunning) {
    logger.warn(`[${trigger}] Previous run still active — skipping this cycle`);
    return;
  }
  pipelineRunning = true;
  try {
    await runPipeline();
  } catch (err) {
    logger.error(`[${trigger}] Run error: ${err.message}`);
  } finally {
    pipelineRunning = false;
  }
}

// Run immediately on startup, then on schedule
safePipelineRun('startup');

const task = cron.schedule(SCHEDULE, () => {
  safePipelineRun('cron');
});

async function shutdown(signal) {
  logger.info(`Received ${signal}, stopping scheduler`);
  task.stop();
  if (pipelineRunning) {
    logger.info('Waiting for active pipeline run to finish (max 90s)...');
    const deadline = Date.now() + 90_000;
    while (pipelineRunning && Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 500));
    }
    if (pipelineRunning) logger.warn('Timeout waiting for pipeline — forcing exit');
  }
  logger.info('Shutdown complete');
  process.exit(0);
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
