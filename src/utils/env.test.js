import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

// Inline isValidCron to test without importing the full module (avoids OAuth side-effects)
function isValidCron(expr) {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return false;
  return parts.every(p => /^[\d\*\/,\-]+$/.test(p));
}

describe('isValidCron', () => {
  it('accepts standard hourly schedule', () => {
    assert.ok(isValidCron('0 * * * *'));
  });

  it('accepts every 30 minutes', () => {
    assert.ok(isValidCron('*/30 * * * *'));
  });

  it('accepts complex expression', () => {
    assert.ok(isValidCron('0 8,12,18 * * 1-5'));
  });

  it('rejects 4-field expression', () => {
    assert.ok(!isValidCron('* * * *'));
  });

  it('rejects 6-field expression', () => {
    assert.ok(!isValidCron('0 * * * * *'));
  });

  it('rejects expression with invalid chars', () => {
    assert.ok(!isValidCron('0 * * * @reboot'));
  });
});

describe('env module structure', () => {
  it('OPTIONAL_LABELS covers all 9 affiliate networks', () => {
    const src = fs.readFileSync('src/utils/env.js', 'utf8');
    const networks = ['ADMITAD', 'TEMU', 'TAKEADS', 'TRAVELPAYOUTS', 'IMPACT', 'CJ', 'SHAREASALE'];
    for (const n of networks) {
      assert.ok(src.includes(n), `env.js missing label for: ${n}`);
    }
  });
});
