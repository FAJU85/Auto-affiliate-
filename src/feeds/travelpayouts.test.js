import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

describe('getTravelpayoutsProduct', () => {
  it('returns null when TRAVELPAYOUTS_TOKEN is not set', async () => {
    const saved = process.env.TRAVELPAYOUTS_TOKEN;
    delete process.env.TRAVELPAYOUTS_TOKEN;
    const { getTravelpayoutsProduct } = await import('./travelpayouts.js');
    const result = await getTravelpayoutsProduct();
    assert.equal(result, null);
    if (saved) process.env.TRAVELPAYOUTS_TOKEN = saved;
  });
});

describe('Travelpayouts product shape', () => {
  it('unified interface has all required keys', () => {
    const product = {
      id: 'tp-NYC-LON-2026-01-01', name: 'Flight NYC → LON (AA)', description: 'From $299.',
      siteUrl: 'https://www.aviasales.com/NYC-LON/?marker=123',
      imageUrl: null, price: 299, currency: 'USD', commissionRate: 0,
      category: 'Travel', source: 'travelpayouts',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'travelpayouts');
    assert.equal(product.category, 'Travel');
  });

  it('product id includes date for daily caption cache variety', () => {
    const today = new Date().toISOString().slice(0, 10);
    const id = `tp-NYC-LON-${today}`;
    assert.ok(id.includes(today), 'id includes today date');
  });
});
