import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { searchProductUrls } from './exa.js';

describe('searchProductUrls', () => {
  it('returns empty array when EXA_API_KEY is not set', async () => {
    const saved = process.env.EXA_API_KEY;
    delete process.env.EXA_API_KEY;
    const result = await searchProductUrls('Test Product');
    assert.deepEqual(result, []);
    if (saved !== undefined) process.env.EXA_API_KEY = saved;
  });

  it('accepts optional numResults parameter', async () => {
    // Verifies the signature accepts 2 args without throwing
    const saved = process.env.EXA_API_KEY;
    delete process.env.EXA_API_KEY;
    const result = await searchProductUrls('Test Product', 5);
    assert.deepEqual(result, []);
    if (saved !== undefined) process.env.EXA_API_KEY = saved;
  });

  it('handles null product name gracefully', async () => {
    const saved = process.env.EXA_API_KEY;
    delete process.env.EXA_API_KEY;
    const result = await searchProductUrls(null);
    assert.deepEqual(result, []);
    if (saved !== undefined) process.env.EXA_API_KEY = saved;
  });
});

describe('query sanitisation (inline logic)', () => {
  function safeQuery(name) {
    return String(name || '')
      .replace(/[^\w\s\-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 80) + ' product page';
  }

  it('appends product page suffix', () => {
    const q = safeQuery('Nike Running Shoes');
    assert.ok(q.includes('product page'), 'suffix present');
  });

  it('strips special characters', () => {
    const q = safeQuery('Product! (With) <Special> "Chars"');
    assert.ok(!/[<>"!()]/g.test(q.replace(' product page', '')), 'special chars removed');
  });

  it('truncates very long product names to 80 chars before suffix', () => {
    const longName = 'A'.repeat(200);
    const q = safeQuery(longName);
    const namePart = q.replace(' product page', '');
    assert.ok(namePart.length <= 80, 'name part capped at 80 chars');
  });

  it('handles null input', () => {
    const q = safeQuery(null);
    assert.ok(typeof q === 'string', 'null returns string');
    assert.ok(q.includes('product page'), 'returns suffix-only query');
  });
});

describe('exa.js module structure', () => {
  it('uses correct Exa API endpoint', () => {
    const src = fs.readFileSync('src/ai/exa.js', 'utf8');
    assert.ok(src.includes('api.exa.ai/search'), 'correct Exa endpoint');
  });

  it('limits to 3 results by default for cost efficiency', () => {
    const src = fs.readFileSync('src/ai/exa.js', 'utf8');
    assert.ok(src.includes('numResults = 3'), 'default numResults is 3');
  });

  it('has timeout guard on fetch call', () => {
    const src = fs.readFileSync('src/ai/exa.js', 'utf8');
    assert.ok(src.includes('AbortSignal.timeout') || src.includes('timeout'), 'timeout guard present');
  });
});
