import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { parseRetryAfter } from './rate-limit.js';

describe('parseRetryAfter', () => {
  it('parses integer seconds', () => {
    assert.equal(parseRetryAfter('30'), 30_000);
    assert.equal(parseRetryAfter('0'), 0);
  });

  it('parses HTTP-date format', () => {
    const future = new Date(Date.now() + 5000).toUTCString();
    const result = parseRetryAfter(future);
    assert.ok(result !== null && result > 0 && result <= 6000);
  });

  it('returns null for missing or invalid header', () => {
    assert.equal(parseRetryAfter(null), null);
    assert.equal(parseRetryAfter(undefined), null);
    assert.equal(parseRetryAfter('not-a-date'), null);
  });

  it('returns null for empty string', () => {
    assert.equal(parseRetryAfter(''), null);
  });
});
