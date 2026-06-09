import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';

describe('SOVRN feed', () => {
  let origKey;

  before(() => {
    origKey = process.env.SOVRN_API_KEY;
  });

  after(() => {
    if (origKey === undefined) delete process.env.SOVRN_API_KEY;
    else process.env.SOVRN_API_KEY = origKey;
  });

  test('getSovrnProduct returns null when SOVRN_API_KEY not set', async () => {
    delete process.env.SOVRN_API_KEY;
    const { getSovrnProduct } = await import('./sovrn.js');
    const result = await getSovrnProduct();
    assert.equal(result, null);
  });

  test('monetizeUrl returns original URL when key not set', async () => {
    delete process.env.SOVRN_API_KEY;
    const { monetizeUrl } = await import('./sovrn.js');
    const url = 'https://www.amazon.com/dp/B09XS7JWHH';
    const result = await monetizeUrl(url);
    assert.equal(result, url);
  });

  test('monetizeUrl returns original URL when passed empty string', async () => {
    const { monetizeUrl } = await import('./sovrn.js');
    const result = await monetizeUrl('');
    assert.equal(result, '');
  });

  test('SOVRN is exported from feeds/index.js TASKS', async () => {
    const { TASKS } = await import('./index.js');
    const task = TASKS.find(t => t.key === 'sovrn');
    assert.ok(task, 'sovrn task missing from TASKS');
    assert.ok(typeof task.fn === 'function');
    assert.ok(typeof task.env === 'function');
  });

  test('SOVRN task env() returns false when key not set', async () => {
    delete process.env.SOVRN_API_KEY;
    const { TASKS } = await import('./index.js');
    const task = TASKS.find(t => t.key === 'sovrn');
    assert.equal(task.env(), false);
  });

  test('SOVRN task env() returns true when key is set', async () => {
    process.env.SOVRN_API_KEY = 'testkey';
    const { TASKS } = await import('./index.js');
    const task = TASKS.find(t => t.key === 'sovrn');
    assert.equal(task.env(), true);
    delete process.env.SOVRN_API_KEY;
  });
});
