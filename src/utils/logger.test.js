import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

describe('logger ring buffer', () => {
  it('getRecentLogs returns an array', async () => {
    const { getRecentLogs, logger } = await import('./logger.js');
    logger.info('test log entry for ring buffer');
    const logs = getRecentLogs(10);
    assert.ok(Array.isArray(logs));
    assert.ok(logs.length > 0);
  });

  it('each log entry has ts, level, and msg fields', async () => {
    const { getRecentLogs, logger } = await import('./logger.js');
    logger.warn('test warning');
    const logs = getRecentLogs(5);
    const last = logs.at(-1);
    assert.ok(last.ts, 'has ts');
    assert.ok(last.level, 'has level');
    assert.ok(typeof last.msg === 'string', 'has msg string');
  });

  it('respects n limit', async () => {
    const { getRecentLogs } = await import('./logger.js');
    const logs = getRecentLogs(2);
    assert.ok(logs.length <= 2);
  });
});
