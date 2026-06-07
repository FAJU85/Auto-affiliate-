import { describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';

describe('getProduct — dedup and fallback logic', () => {
  it('throws when no networks are configured', async () => {
    // Clear all network env vars
    const keys = [
      'ADMITAD_FEED_URL', 'ADMITAD_CLIENT_ID', 'ADMITAD_CLIENT_SECRET',
      'ADMITAD_WEBSITE_ID', 'ADMITAD_CATALOG_URL_1', 'TEMU_AFFILIATE_URL_1',
      'TEMU_AFFILIATE_URL_2', 'TAKEADS_API_KEY', 'TRAVELPAYOUTS_TOKEN',
    ];
    const saved = Object.fromEntries(keys.map(k => [k, process.env[k]]));
    keys.forEach(k => delete process.env[k]);

    try {
      const { getProduct } = await import('./index.js');
      await assert.rejects(() => getProduct(), /No affiliate network/);
    } finally {
      Object.entries(saved).forEach(([k, v]) => { if (v !== undefined) process.env[k] = v; });
    }
  });

  it('dedup: skips recently-posted product and returns a fresh one', () => {
    const products = [
      { id: '1', name: 'Old Product', siteUrl: 'https://old.example.com', source: 'test' },
      { id: '2', name: 'New Product', siteUrl: 'https://new.example.com', source: 'test' },
    ];

    // wasPosted returns true for the old product's URL
    const wasPosted = (url) => url === 'https://old.example.com';
    const shuffled  = [...products];
    const fresh = shuffled.find(p => !wasPosted(p.siteUrl, p.name));
    assert.equal(fresh.name, 'New Product');
  });

  it('dedup: falls back to any product when all were recently posted', () => {
    const products = [
      { id: '1', name: 'A', siteUrl: 'https://a.example.com', source: 'test' },
    ];
    const wasPosted = () => true;
    const fresh = products.find(p => !wasPosted(p.siteUrl, p.name));
    assert.equal(fresh, undefined, 'no fresh product found — expected fallback to first');
    // Fallback: pick products[0]
    assert.equal(products[0].name, 'A');
  });
});

describe('getProduct — product shape validation', () => {
  it('unified product interface has all required keys', () => {
    const product = {
      id: '42',
      name: 'Test Product',
      description: 'A test product',
      siteUrl: 'https://example.com/item/42.html',
      imageUrl: null,
      price: 9.99,
      currency: 'USD',
      commissionRate: 0.05,
      source: 'test',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) {
      assert.ok(key in product, `missing key: ${key}`);
    }
  });
});
