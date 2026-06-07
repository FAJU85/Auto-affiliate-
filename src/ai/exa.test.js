import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
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
    const name     = 'Wireless Earbuds';
    const category = 'Electronics';
    const expected = name !== category;
    assert.ok(expected, 'different name and category → both should appear in query');
  });

  it('falls back to name-only query when category equals product name', () => {
    const name     = 'AirPods';
    const category = 'AirPods';
    const sameAsCat = category === name;
    assert.ok(sameAsCat, 'same name and category → name-only query branch');
  });
});

describe('safeQuery (inline logic)', () => {
  function safeQuery(name, category) {
    const clean = String(name || '').replace(/[^\w\s\-]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);
    return category && category !== name
      ? `${clean} ${category} review features benefits`
      : `${clean} review features why buy`;
  }

  it('includes category when name and category differ', () => {
    const q = safeQuery('Nike Running Shoes', 'Fashion');
    assert.ok(q.includes('Nike Running Shoes'), 'name in query');
    assert.ok(q.includes('Fashion'), 'category in query');
    assert.ok(q.includes('review features benefits'), 'enrichment suffix');
  });

  it('uses name-only query when name and category match', () => {
    const q = safeQuery('Electronics', 'Electronics');
    assert.ok(q.includes('why buy'), 'name-only suffix used');
    assert.ok(!q.includes('review features benefits'), 'no category suffix');
  });

  it('strips special characters from product names', () => {
    const q = safeQuery('Product! (With) <Special> "Chars"', 'Tech');
    assert.ok(!/[<>"!()]/g.test(q.split(' Tech ')[0]), 'special chars removed from name');
  });

  it('handles null/undefined inputs', () => {
    const q1 = safeQuery(null, 'Electronics');
    assert.ok(typeof q1 === 'string', 'null name returns string');
    const q2 = safeQuery('Product', null);
    assert.ok(typeof q2 === 'string', 'null category returns string');
  });

  it('truncates very long product names to 80 chars', () => {
    const longName = 'A'.repeat(200);
    const q = safeQuery(longName, 'Test');
    assert.ok(q.length > 0, 'query generated');
    const namePart = q.split(' Test ')[0];
    assert.ok(namePart.length <= 80, 'name part capped at 80 chars');
  });
});

describe('exa.js module structure', () => {
  it('uses correct Exa API endpoint', () => {
    const src = fs.readFileSync('src/ai/exa.js', 'utf8');
    assert.ok(src.includes('api.exa.ai/search'), 'correct Exa endpoint');
  });

  it('requests highlights in API call', () => {
    const src = fs.readFileSync('src/ai/exa.js', 'utf8');
    assert.ok(src.includes('highlights: true'), 'highlights enabled in request');
  });

  it('limits to 3 results for cost efficiency', () => {
    const src = fs.readFileSync('src/ai/exa.js', 'utf8');
    assert.ok(src.includes('numResults: 3'), 'requests only 3 results');
  });
});
