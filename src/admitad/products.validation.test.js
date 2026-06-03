import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

function isValidHttpUrl(str) {
  try {
    const u = new URL(str);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch { return false; }
}

function isValidCron(expr) {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return false;
  return parts.every(p => /^[\d\*\/,\-]+$/.test(p));
}

describe('URL validation', () => {
  it('accepts https URLs', () => assert.ok(isValidHttpUrl('https://shop.example.com/p?id=1')));
  it('accepts http URLs', () => assert.ok(isValidHttpUrl('http://shop.example.com')));
  it('rejects empty string', () => assert.ok(!isValidHttpUrl('')));
  it('rejects javascript: protocol', () => assert.ok(!isValidHttpUrl('javascript:alert(1)')));
  it('rejects bare domain', () => assert.ok(!isValidHttpUrl('example.com')));
  it('rejects undefined', () => assert.ok(!isValidHttpUrl(undefined)));
});

describe('cron expression validation', () => {
  it('accepts standard hourly cron', () => assert.ok(isValidCron('0 * * * *')));
  it('accepts complex valid cron', () => assert.ok(isValidCron('*/15 0-23 1,15 * 1-5')));
  it('rejects 4-field expression', () => assert.ok(!isValidCron('0 * * *')));
  it('rejects 6-field expression', () => assert.ok(!isValidCron('0 * * * * *')));
  it('rejects text', () => assert.ok(!isValidCron('every hour')));
  it('rejects empty string', () => assert.ok(!isValidCron('')));
});
