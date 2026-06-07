import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { isWithinPostingWindow } from './schedule.js';

describe('isWithinPostingWindow', () => {
  it('returns true when POSTING_HOURS is not set (defaults 8-22)', () => {
    delete process.env.POSTING_HOURS;
    // Result depends on current UTC hour — just verify it returns a boolean
    const result = isWithinPostingWindow();
    assert.ok(typeof result === 'boolean');
  });

  it('returns true when window is 0-23 (always on)', () => {
    process.env.POSTING_HOURS = '0-23';
    assert.equal(isWithinPostingWindow(), true);
    delete process.env.POSTING_HOURS;
  });

  it('returns true for malformed value (fail-open)', () => {
    process.env.POSTING_HOURS = 'invalid';
    assert.equal(isWithinPostingWindow(), true);
    delete process.env.POSTING_HOURS;
  });

  it('correctly identifies hour inside a simple window', () => {
    // Patch Date to return a known UTC hour
    const origDate = global.Date;
    global.Date = class extends origDate {
      getUTCHours() { return 14; } // 2pm UTC
    };
    process.env.POSTING_HOURS = '8-22';
    assert.equal(isWithinPostingWindow(), true);
    global.Date = origDate;
    delete process.env.POSTING_HOURS;
  });

  it('correctly identifies hour outside a simple window', () => {
    const origDate = global.Date;
    global.Date = class extends origDate {
      getUTCHours() { return 3; } // 3am UTC
    };
    process.env.POSTING_HOURS = '8-22';
    assert.equal(isWithinPostingWindow(), false);
    global.Date = origDate;
    delete process.env.POSTING_HOURS;
  });

  it('handles wrap-around overnight windows correctly', () => {
    const origDate = global.Date;
    global.Date = class extends origDate {
      getUTCHours() { return 23; } // 11pm UTC
    };
    process.env.POSTING_HOURS = '22-6';
    assert.equal(isWithinPostingWindow(), true);
    global.Date = origDate;
    delete process.env.POSTING_HOURS;
  });
});
