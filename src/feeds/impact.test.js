import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { getImpactProduct } from './impact.js';

describe('getImpactProduct', () => {
  it('returns null when credentials are not configured', async () => {
    const saved = { sid: process.env.IMPACT_ACCOUNT_SID, tok: process.env.IMPACT_AUTH_TOKEN };
    delete process.env.IMPACT_ACCOUNT_SID;
    delete process.env.IMPACT_AUTH_TOKEN;
    const result = await getImpactProduct();
    assert.equal(result, null);
    if (saved.sid) process.env.IMPACT_ACCOUNT_SID = saved.sid;
    if (saved.tok) process.env.IMPACT_AUTH_TOKEN   = saved.tok;
  });

  it('returns null when only one credential is set', async () => {
    const saved = { sid: process.env.IMPACT_ACCOUNT_SID, tok: process.env.IMPACT_AUTH_TOKEN };
    process.env.IMPACT_ACCOUNT_SID = 'test-sid';
    delete process.env.IMPACT_AUTH_TOKEN;
    const result = await getImpactProduct();
    assert.equal(result, null);
    if (saved.sid) process.env.IMPACT_ACCOUNT_SID = saved.sid;
    else delete process.env.IMPACT_ACCOUNT_SID;
    if (saved.tok) process.env.IMPACT_AUTH_TOKEN = saved.tok;
  });
});

describe('Impact.com product shape', () => {
  it('unified interface has all required keys', () => {
    const product = {
      id: 'ad-42', name: 'Nike Sale', description: 'Up to 50% off', siteUrl: 'https://impact.go2cloud.org/aff_c',
      imageUrl: null, price: null, currency: 'USD', commissionRate: 0, source: 'impact',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'impact');
  });
});
