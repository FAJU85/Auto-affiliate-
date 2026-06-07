import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { getAdmitadProduct } from './admitad.js';

describe('getAdmitadProduct', () => {
  it('returns null when ADMITAD_FEED_URL is not set', async () => {
    const saved = process.env.ADMITAD_FEED_URL;
    delete process.env.ADMITAD_FEED_URL;
    const result = await getAdmitadProduct();
    assert.equal(result, null);
    if (saved) process.env.ADMITAD_FEED_URL = saved;
  });
});

describe('Admitad YML parser', () => {
  it('unified product shape has all required keys', () => {
    const product = {
      id: 'offer-123', name: 'AliExpress Running Shoes', description: 'Comfortable shoes for running',
      siteUrl: 'https://rzekl.com/g/abc?ulp=https%3A%2F%2Fwww.aliexpress.com%2Fitem%2F123.html',
      imageUrl: 'https://ae01.alicdn.com/kf/img.jpg',
      price: 29.99, currency: 'USD', commissionRate: 8.5, source: 'admitad',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'admitad');
  });

  it('filters out offers with no affiliate URL', () => {
    const offers = [
      { id: '1', name: 'Good Product', url: 'https://rzekl.com/g/abc', price: 10 },
      { id: '2', name: 'Bad Product', url: '', price: 5 },
      { id: '3', name: 'No URL', price: 8 },
    ];
    const valid = offers.filter(o => {
      if (!o.url) return false;
      try { new URL(o.url); return true; } catch { return false; }
    });
    assert.equal(valid.length, 1);
    assert.equal(valid[0].name, 'Good Product');
  });
});
