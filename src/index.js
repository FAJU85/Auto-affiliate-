import 'dotenv/config';
import cron from 'node-cron';
import { runPipeline } from './pipeline/run.js';
import { logger } from './utils/logger.js';

const SCHEDULE = process.env.CRON_SCHEDULE || '0 * * * *'; // every hour by default

logger.info(`Auto-Affiliate pipeline starting. Schedule: "${SCHEDULE}"`);

let pipelineRunning = false;

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

process.on('SIGTERM', () => {
  logger.info('Received SIGTERM, shutting down');
  task.stop();
  process.exit(0);
});

process.on('SIGINT', () => {
  logger.info('Received SIGINT, shutting down');
  task.stop();
  process.exit(0);
});
