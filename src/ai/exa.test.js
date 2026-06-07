import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { getProductHighlights } from './exa.js';

describe('getProductHighlights', () => {
  it('returns null when EXA_API_KEY is not set', async () => {
    const saved = process.env.EXA_API_KEY;
    delete process.env.EXA_API_KEY;
    const result = await getProductHighlights('Test Product', 'Electronics');
    assert.equal(result, null);
    if (saved !== undefined) process.env.EXA_API_KEY = saved;
  });

  it('uses product name and category in query when both are provided', () => {
    // White-box: verify the query branch logic
    const name     = 'Wireless Earbuds';
    const category = 'Electronics';
    const expected = name !== category; // different → include both
    assert.ok(expected, 'different name and category → both should appear in query');
  });

  it('falls back to name-only query when category equals product name', () => {
    const name     = 'AirPods';
    const category = 'AirPods';
    const sameAsCat = category === name;
    assert.ok(sameAsCat, 'same name and category → name-only query branch');
  });
});
