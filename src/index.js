import 'dotenv/config';
import cron from 'node-cron';
import { runPipeline } from './pipeline/run.js';
import { logger } from './utils/logger.js';

const SCHEDULE = process.env.CRON_SCHEDULE || '0 * * * *'; // every hour by default

logger.info(`Auto-Affiliate pipeline starting. Schedule: "${SCHEDULE}"`);

// Run immediately on startup, then on schedule
runPipeline().catch(err => logger.error(`Startup run error: ${err.message}`));

const task = cron.schedule(SCHEDULE, () => {
  logger.info('Cron triggered pipeline run');
  runPipeline().catch(err => logger.error(`Scheduled run error: ${err.message}`));
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
