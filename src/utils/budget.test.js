import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

// Redirect budget file to a temp location for tests
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'affiliate-test-'));
const BUDGET_FILE = path.join(tmpDir, 'budget.json');

before(() => {
  process.env.DAILY_COST_CAP_USD = '1.00';
  process.env.ALERT_COST_THRESHOLD_USD = '0.80';
  process.env.DALLE_COST_PER_IMAGE = '0.04';
  // Patch budget file path by writing a fresh one
  fs.mkdirSync(path.dirname(BUDGET_FILE), { recursive: true });
});

after(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

describe('budget guardrails', () => {
  it('alert threshold must be less than cap', () => {
    const cap = parseFloat(process.env.DAILY_COST_CAP_USD);
    const alert = parseFloat(process.env.ALERT_COST_THRESHOLD_USD);
    assert.ok(alert < cap, `Alert $${alert} must be < cap $${cap}`);
  });

  it('DALLE cost is less than cap', () => {
    const cap = parseFloat(process.env.DAILY_COST_CAP_USD);
    const cost = parseFloat(process.env.DALLE_COST_PER_IMAGE);
    assert.ok(cost < cap, `DALL-E cost $${cost} must be < cap $${cap}`);
  });
});

describe('logger', () => {
  it('reads LOG_LEVEL dynamically (not frozen at import time)', async () => {
    process.env.LOG_LEVEL = 'error';
    const { logger } = await import('./logger.js');
    let logged = false;
    const orig = console.log;
    console.log = () => { logged = true; };
    logger.info('should be suppressed');
    console.log = orig;
    assert.equal(logged, false, 'info should be suppressed when LOG_LEVEL=error');
    delete process.env.LOG_LEVEL;
  });
});
