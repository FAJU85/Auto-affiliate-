import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { sleep } from './sleep.js';

describe('sleep', () => {
  it('resolves after the specified delay', async () => {
    const start = Date.now();
    await sleep(50);
    assert.ok(Date.now() - start >= 40);
  });

  it('returns a Promise', () => {
    const p = sleep(1);
    assert.ok(p instanceof Promise);
    return p;
  });
});
