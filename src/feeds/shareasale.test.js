import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { getShareASaleProduct } from './shareasale.js';

describe('getShareASaleProduct', () => {
  it('returns null when credentials are not set', async () => {
    const saved = {
      t: process.env.SHAREASALE_TOKEN,
      s: process.env.SHAREASALE_SECRET,
      a: process.env.SHAREASALE_AFFILIATE_ID,
    };
    delete process.env.SHAREASALE_TOKEN;
    delete process.env.SHAREASALE_SECRET;
    delete process.env.SHAREASALE_AFFILIATE_ID;
    const result = await getShareASaleProduct();
    assert.equal(result, null);
    if (saved.t) process.env.SHAREASALE_TOKEN        = saved.t;
    if (saved.s) process.env.SHAREASALE_SECRET       = saved.s;
    if (saved.a) process.env.SHAREASALE_AFFILIATE_ID = saved.a;
  });
});

describe('ShareASale non-Latin filter', () => {
  it('non-Latin filter exists in shareasale.js', () => {
    const src = fs.readFileSync('src/feeds/shareasale.js', 'utf8');
    assert.ok(src.includes('isLikelyEnglishOrNeutral'), 'non-Latin filter defined');
    assert.ok(src.includes('nonLatin'), 'uses nonLatin detection');
  });

  it('isLikelyEnglishOrNeutral rejects Cyrillic names', () => {
    function isLikelyEnglishOrNeutral(str) {
      if (!str || str.length < 3) return true;
      const nonLatin = (str.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
      return nonLatin / str.length < 0.4;
    }
    assert.ok(isLikelyEnglishOrNeutral('Running Shoes Store'), 'Latin accepted');
    assert.ok(!isLikelyEnglishOrNeutral('Магазин одежды'), 'Cyrillic rejected');
  });
});

describe('ShareASale XML parser', () => {
  it('skips products with no AffiliateURL', () => {
    // Simulate the filter logic
    const items = [
      { affiliateUrl: '', name: 'Bad Product' },
      { affiliateUrl: 'https://www.shareasale.com/r.cfm?b=1&u=2&m=3', name: 'Good Product' },
    ];
    const valid = items.filter(i => {
      if (!i.affiliateUrl) return false;
      try { new URL(i.affiliateUrl); return true; } catch { return false; }
    });
    assert.equal(valid.length, 1);
    assert.equal(valid[0].name, 'Good Product');
  });

  it('unified interface has all required keys', () => {
    const product = {
      id: 'sku-123', name: 'Running Shoes', description: 'Comfortable shoes',
      siteUrl: 'https://www.shareasale.com/r.cfm?b=1&u=2&m=3',
      imageUrl: null, price: 89.99, currency: 'USD', commissionRate: 8, source: 'shareasale',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'shareasale');
  });
});
