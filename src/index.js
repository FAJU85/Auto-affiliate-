import 'dotenv/config';
import cron from 'node-cron';
import { runPipeline } from './pipeline/run.js';
import { logger } from './utils/logger.js';
import { validateEnv } from './utils/env.js';
import { startServer, hasAnyNetworkEnabled } from './server.js';
import { restoreSessionFromSecrets } from './auth/bluesky-oauth.js';
import { isWithinPostingWindow } from './utils/schedule.js';
import { getRecentRuns } from './utils/metrics.js';
import { getSettings } from './config/settings.js';
import { buildCronExpressions } from './utils/schedule-manager.js';

let missingVars     = [];
let configured      = false;
let pipelineRunning = false;
let schedulerPaused = false;

// Active cron task handles — rebuilt when schedule config changes
let _cronTasks = [];

export function pauseScheduler()    { schedulerPaused = true;  logger.info('Scheduler paused by user'); }
export function resumeScheduler()   { schedulerPaused = false; logger.info('Scheduler resumed by user'); }
export function isSchedulerPaused() { return schedulerPaused; }

export function getScheduleInfo() {
  const s = getSettings();
  return {
    postsPerDay:      s.postsPerDay     ?? 1,
    schedulerEnabled: s.schedulerEnabled !== false,
    postingHours:     s.postingHours    || '8-22',
    cronExpressions:  buildCronExpressions(s.postsPerDay ?? 1, s.postingHours || '8-22'),
    paused:           schedulerPaused,
  };
}

/** Tears down current cron tasks and rebuilds from settings. */
export function rebuildSchedule() {
  for (const t of _cronTasks) { try { t.stop(); } catch {} }
  _cronTasks = [];

  const s = getSettings();
  if (s.schedulerEnabled === false) {
    logger.info('Scheduler disabled in settings');
    return;
  }

  const exprs = buildCronExpressions(s.postsPerDay ?? 1, s.postingHours || '8-22');
  for (const expr of exprs) {
    _cronTasks.push(cron.schedule(expr, () => safePipelineRun('cron')));
  }
  logger.info(`Schedule: ${exprs.length} slot(s) — ${exprs.join(', ')}`);
}

async function safePipelineRun(trigger) {
  if (!configured) {
    logger.warn(`[${trigger}] Skipped — Bluesky not connected`);
    return;
  }
  if (pipelineRunning) {
    logger.warn(`[${trigger}] Previous run still active — skipping`);
    return;
  }
  if (trigger === 'cron' && schedulerPaused) {
    logger.info('[cron] Paused — skipping');
    return;
  }
  const s = getSettings();
  if (trigger === 'cron' && s.schedulerEnabled === false) {
    logger.info('[cron] Scheduler disabled — skipping');
    return;
  }
  if (trigger === 'cron' && !isWithinPostingWindow()) {
    logger.info(`[${trigger}] Outside posting window — skipping`);
    return;
  }
  const maxDaily = s.postsPerDay ?? parseInt(process.env.MAX_POSTS_PER_DAY || '24', 10);
  const today    = new Date().toISOString().slice(0, 10);
  const todayOk  = getRecentRuns(100).filter(r => r.success && r.timestamp?.startsWith(today)).length;
  if (todayOk >= maxDaily) {
    logger.info(`[${trigger}] Daily limit reached (${todayOk}/${maxDaily}) — skipping`);
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

// Start server first — HF Spaces requires port 7860 to come up immediately
startServer(() => pipelineRunning, safePipelineRun, () => missingVars);

restoreSessionFromSecrets().catch(() => {});

validateEnv().then(missing => {
  if (!hasAnyNetworkEnabled()) {
    missing.push('affiliate network (set at least one: ADMITAD_FEED_URL, TEMU_AFFILIATE_URL_1, etc.)');
  }

  missingVars = missing;
  configured  = missing.length === 0;

  if (!configured) {
    logger.warn(`Not configured — ${missing.join(', ')}`);
    logger.warn('Dashboard running. Connect Bluesky + add a network to start posting.');
  }

  logger.info('Auto-Affiliate pipeline starting');
  rebuildSchedule();

  if (configured) safePipelineRun('startup');

  async function shutdown(signal) {
    logger.info(`Received ${signal}, stopping scheduler`);
    for (const t of _cronTasks) { try { t.stop(); } catch {} }
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
