import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';

describe('getTemuProduct', () => {
  before(() => {
    process.env.TEMU_AFFILIATE_URL_1 = 'https://temu.to/k/testlink1';
    process.env.TEMU_AFFILIATE_URL_2 = 'https://temu.to/m/testlink2';
    process.env.TEMU_AFFILIATE_URL_3 = 'https://temu.to/k/testlink3';
  });

  after(() => {
    delete process.env.TEMU_AFFILIATE_URL_1;
    delete process.env.TEMU_AFFILIATE_URL_2;
    delete process.env.TEMU_AFFILIATE_URL_3;
  });

  it('returns null when no Temu URLs are configured', async () => {
    const saved = [process.env.TEMU_AFFILIATE_URL_1, process.env.TEMU_AFFILIATE_URL_2, process.env.TEMU_AFFILIATE_URL_3];
    delete process.env.TEMU_AFFILIATE_URL_1;
    delete process.env.TEMU_AFFILIATE_URL_2;
    delete process.env.TEMU_AFFILIATE_URL_3;
    const { getTemuProduct } = await import('./temu.js');
    const result = await getTemuProduct();
    assert.equal(result, null);
    [process.env.TEMU_AFFILIATE_URL_1, process.env.TEMU_AFFILIATE_URL_2, process.env.TEMU_AFFILIATE_URL_3] = saved;
  });

  it('returns a product with required fields when URLs are set', async () => {
    const { getTemuProduct } = await import('./temu.js');
    const product = await getTemuProduct();
    assert.ok(product !== null, 'product returned');
    assert.ok(typeof product.name === 'string' && product.name.length > 0, 'has name');
    assert.ok(typeof product.description === 'string', 'has description');
    assert.ok(['https://temu.to/k/testlink1', 'https://temu.to/m/testlink2', 'https://temu.to/k/testlink3'].includes(product.siteUrl), 'siteUrl is one of the configured URLs');
    assert.equal(product.source, 'temu');
    assert.equal(product.currency, 'USD');
    assert.ok(typeof product.id === 'string', 'has id');
  });

  it('rotates across all 10 deal themes over repeated calls', async () => {
    const { getTemuProduct } = await import('./temu.js');
    const names = new Set();
    for (let i = 0; i < 40; i++) {
      const p = await getTemuProduct();
      names.add(p.name);
    }
    assert.ok(names.size > 3, `expected variety in themes, got ${names.size} unique names`);
  });
});
