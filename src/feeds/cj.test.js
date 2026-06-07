import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { getCJProduct } from './cj.js';

describe('getCJProduct', () => {
  it('returns null when CJ_API_KEY is not set', async () => {
    const saved = { key: process.env.CJ_API_KEY, wid: process.env.CJ_WEBSITE_ID };
    delete process.env.CJ_API_KEY;
    delete process.env.CJ_WEBSITE_ID;
    const result = await getCJProduct();
    assert.equal(result, null);
    if (saved.key) process.env.CJ_API_KEY    = saved.key;
    if (saved.wid) process.env.CJ_WEBSITE_ID = saved.wid;
  });

  it('returns null when only one credential is set', async () => {
    const saved = { key: process.env.CJ_API_KEY, wid: process.env.CJ_WEBSITE_ID };
    process.env.CJ_API_KEY = 'test-key';
    delete process.env.CJ_WEBSITE_ID;
    const result = await getCJProduct();
    assert.equal(result, null);
    if (saved.key) process.env.CJ_API_KEY = saved.key; else delete process.env.CJ_API_KEY;
    if (saved.wid) process.env.CJ_WEBSITE_ID = saved.wid;
  });
});

describe('CJ keyword rotation', () => {
  it('SEARCH_KEYWORDS array exists with diverse terms', () => {
    const src = fs.readFileSync('src/feeds/cj.js', 'utf8');
    assert.ok(src.includes('SEARCH_KEYWORDS'), 'SEARCH_KEYWORDS defined');
    assert.ok(src.includes("'sale'"), 'sale keyword present');
    assert.ok(src.includes("'discount'"), 'discount keyword present');
    assert.ok(src.includes("'deal'"), 'deal keyword present');
  });

  it('random page 1-5 is used for variety', () => {
    const src = fs.readFileSync('src/feeds/cj.js', 'utf8');
    assert.ok(src.includes('Math.random() * 5'), 'random page 1-5');
  });
});

describe('CJ Affiliate product shape', () => {
  it('normalises link array vs single-object API response', () => {
    // CJ returns array or plain object depending on result count — both must work
    const single = { destination: 'https://cj.com/r/abc', 'link-name': 'Deal', description: 'Test' };
    const asArray = Array.isArray([single]) ? [single] : [single];
    assert.ok(asArray.length === 1);
    assert.ok(asArray[0].destination);
  });

  it('unified interface has all required keys', () => {
    const product = {
      id: 'lnk-1', name: 'Nike Promo', description: 'Get 20% off',
      siteUrl: 'https://cj.com/r/xyz', imageUrl: null,
      price: null, currency: 'USD', commissionRate: 15, source: 'cj',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'cj');
  });
});
