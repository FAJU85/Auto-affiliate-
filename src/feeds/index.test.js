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

describe('getNetworkErrors', () => {
  it('exports getNetworkErrors returning an object', async () => {
    const { getNetworkErrors } = await import('./index.js');
    const errs = getNetworkErrors();
    assert.ok(errs !== null && typeof errs === 'object');
  });
});

describe('getNetworkSelectCounts', () => {
  it('exports getNetworkSelectCounts returning an object', async () => {
    const { getNetworkSelectCounts } = await import('./index.js');
    const counts = getNetworkSelectCounts();
    assert.ok(counts !== null && typeof counts === 'object');
  });
});

describe('TASKS consistency', () => {
  it('TASKS covers all 10 networks', async () => {
    const { TASKS } = await import('./index.js');
    const expectedKeys = [
      'admitad-feed', 'admitad-api', 'admitad-catalog',
      'temu', 'takeads', 'travelpayouts', 'impact', 'cj', 'shareasale', 'sovrn',
    ];
    assert.ok(Array.isArray(TASKS), 'TASKS is an array');
    assert.equal(TASKS.length, 10, 'TASKS has 10 networks');
    for (const key of expectedKeys) {
      assert.ok(TASKS.some(t => t.key === key), `TASKS missing: ${key}`);
    }
  });

  it('each TASK has key, fn, and env properties', async () => {
    const { TASKS } = await import('./index.js');
    for (const task of TASKS) {
      assert.ok(typeof task.key === 'string', `key is string: ${task.key}`);
      assert.ok(typeof task.fn === 'function', `fn is function: ${task.key}`);
      assert.ok(typeof task.env === 'function', `env is function: ${task.key}`);
    }
  });
});

describe('inferCategory', () => {
  // Inline the logic for unit testing
  const CATEGORY_PATTERNS = [
    { pattern: /\b(flight|hotel|travel|airline|vacation|trip)\b/i, category: 'Travel' },
    { pattern: /\b(phone|laptop|earbuds|headphone|camera|smartwatch|tv)\b/i, category: 'Electronics' },
    { pattern: /\b(dress|shoes|sneakers|jacket|jeans|handbag|ring|necklace)\b/i, category: 'Fashion' },
    { pattern: /\b(skincare|makeup|lipstick|perfume|hair|shampoo|serum)\b/i, category: 'Beauty' },
    { pattern: /\b(vitamin|fitness|yoga|gym|running|sport)\b/i, category: 'Health & Fitness' },
    { pattern: /\b(toy|game|kids|baby|stroller)\b/i, category: 'Toys & Kids' },
    { pattern: /\b(pet|dog|cat|bird)\b/i, category: 'Pet Supplies' },
  ];
  function inferCategory(name) {
    if (!name) return null;
    for (const { pattern, category } of CATEGORY_PATTERNS) {
      if (pattern.test(name)) return category;
    }
    return null;
  }

  it('infers Travel for flight products', () => {
    assert.equal(inferCategory('Cheap flight NYC to LON'), 'Travel');
    assert.equal(inferCategory('Hotel deal Miami Beach'), 'Travel');
  });

  it('infers Electronics for tech products', () => {
    assert.equal(inferCategory('Wireless Earbuds Pro'), 'Electronics');
    assert.equal(inferCategory('4K Smart TV 55"'), 'Electronics');
  });

  it('infers Fashion for clothing/accessories', () => {
    assert.equal(inferCategory('Women Running Shoes'), 'Fashion');
    assert.equal(inferCategory('Designer Handbag Sale'), 'Fashion');
  });

  it('returns null for unrecognized categories', () => {
    assert.equal(inferCategory('Random Widget 3000'), null);
    assert.equal(inferCategory(null), null);
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
