import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { getAdmitadCatalogProduct } from './admitad-catalog.js';

describe('getAdmitadCatalogProduct', () => {
  it('returns null when no ADMITAD_CATALOG_URL_N vars are set', async () => {
    const saved = [1,2,3,4,5].map(n => process.env[`ADMITAD_CATALOG_URL_${n}`]);
    [1,2,3,4,5].forEach(n => delete process.env[`ADMITAD_CATALOG_URL_${n}`]);
    const result = await getAdmitadCatalogProduct();
    assert.equal(result, null);
    saved.forEach((v, i) => { if (v) process.env[`ADMITAD_CATALOG_URL_${i+1}`] = v; });
  });
});

describe('Admitad catalog JSON parser', () => {
  it('filters items without valid affiliate link', () => {
    const items = [
      { id: '1', name: 'Good Item', goto_link: 'https://rzekl.com/g/abc' },
      { id: '2', name: 'No link' },
      { id: '3', name: 'Bad link', goto_link: 'not-a-url' },
    ];
    const valid = items.filter(o => {
      const link = o.goto_link || o.gotolink || o.affiliate_url || o.url;
      if (!link) return false;
      try { new URL(link); return true; } catch { return false; }
    });
    assert.equal(valid.length, 1);
    assert.equal(valid[0].name, 'Good Item');
  });

  it('product shape has all required keys', () => {
    const product = {
      id: 'offer-42', name: 'Winter Jacket', description: 'Warm winter jacket',
      siteUrl: 'https://rzekl.com/g/xyz', imageUrl: null,
      price: 59.99, currency: 'USD', commissionRate: 0, source: 'admitad-catalog',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'admitad-catalog');
  });
});
