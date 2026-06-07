import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { nextCronRun } from './cron-next.js';

describe('nextCronRun', () => {
  it('returns null for invalid expression', () => {
    assert.equal(nextCronRun('not valid cron at all'), null);
  });

  it('returns a Date for valid expression', () => {
    const next = nextCronRun('0 * * * *');
    assert.ok(next instanceof Date);
  });

  it('next run is in the future', () => {
    const now = new Date();
    const next = nextCronRun('0 * * * *', now);
    assert.ok(next > now);
  });

  it('every-hour cron next run is within 60 minutes', () => {
    const now = new Date('2025-01-01T10:30:00Z');
    const next = nextCronRun('0 * * * *', now);
    assert.ok(next instanceof Date);
    assert.equal(next.getUTCMinutes(), 0);
    assert.equal(next.getUTCHours(), 11);
  });

  it('step expression */15 matches multiples of 15', () => {
    const now = new Date('2025-01-01T10:01:00Z');
    const next = nextCronRun('*/15 * * * *', now);
    assert.ok(next instanceof Date);
    assert.equal(next.getUTCMinutes() % 15, 0);
  });

  it('specific hour and minute', () => {
    const now = new Date('2025-01-01T08:00:00Z');
    const next = nextCronRun('30 9 * * *', now);
    assert.ok(next instanceof Date);
    assert.equal(next.getUTCHours(), 9);
    assert.equal(next.getUTCMinutes(), 30);
  });
});
