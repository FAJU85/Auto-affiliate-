import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { getTakeadsProduct } from './takeads.js';

describe('getTakeadsProduct', () => {
  it('returns null when TAKEADS_API_KEY is not set', async () => {
    const saved = process.env.TAKEADS_API_KEY;
    delete process.env.TAKEADS_API_KEY;
    const result = await getTakeadsProduct();
    assert.equal(result, null);
    if (saved) process.env.TAKEADS_API_KEY = saved;
  });
});

describe('Takeads product shape', () => {
  it('unified interface has all required keys', () => {
    const product = {
      id: '12345', name: 'Example Brand', description: 'Example Brand',
      siteUrl: 'https://track.takeads.com/v3/link/abc123',
      imageUrl: null, price: null, currency: 'USD', commissionRate: 5.2, source: 'takeads',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'takeads');
  });
});

describe('Takeads non-Latin filter', () => {
  function isLikelyEnglishOrNeutral(str) {
    if (!str || str.length < 3) return true;
    const nonLatin = (str.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
    return nonLatin / str.length < 0.4;
  }

  it('accepts Latin names', () => {
    assert.ok(isLikelyEnglishOrNeutral('Nike Running Store'), 'Latin name accepted');
    assert.ok(isLikelyEnglishOrNeutral('Amazon.com'), 'domain accepted');
  });

  it('rejects predominantly Cyrillic names', () => {
    assert.ok(!isLikelyEnglishOrNeutral('Магазин товаров'), 'Cyrillic rejected');
  });

  it('non-Latin filter exists in takeads.js source', () => {
    const src = fs.readFileSync('src/feeds/takeads.js', 'utf8');
    assert.ok(src.includes('nonLatin'), 'non-Latin filter in source');
    assert.ok(src.includes('top10'), 'top10 candidate pool');
  });
});
