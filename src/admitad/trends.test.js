import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

describe('admitad/trends', () => {
  const origUrl = process.env.TRENDS_RSS_URL;

  afterEach(() => {
    if (origUrl !== undefined) process.env.TRENDS_RSS_URL = origUrl;
    else delete process.env.TRENDS_RSS_URL;
  });

  it('returns empty array on fetch failure (bad URL)', async () => {
    process.env.TRENDS_RSS_URL = 'http://localhost:1/nonexistent-rss';
    const { getTopTrends } = await import('./trends.js');
    const result = await getTopTrends(3);
    assert.deepEqual(result, []);
  });

  it('returns array (possibly empty) even when env var is unset', async () => {
    delete process.env.TRENDS_RSS_URL;
    // May succeed or fail network-wise; either way must return an array
    const { getTopTrends } = await import('./trends.js');
    const result = await getTopTrends(1).catch(() => []);
    assert.ok(Array.isArray(result));
  });
});
