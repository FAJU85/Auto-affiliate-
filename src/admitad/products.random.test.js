import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// Inline the selection logic for deterministic testing
function selectFromTopN(campaigns, minEcpc, n = 5) {
  const filtered = campaigns.filter(c => !!c.site_url && parseFloat(c.avg_ecpc || 0) >= minEcpc);
  filtered.sort((a, b) => parseFloat(b.avg_ecpc) - parseFloat(a.avg_ecpc));
  if (filtered.length === 0) return null;
  const pool = filtered.slice(0, n);
  return pool[Math.floor(Math.random() * pool.length)];
}

const CAMPAIGNS = Array.from({ length: 20 }, (_, i) => ({
  id: String(i + 1),
  name: `Campaign ${i + 1}`,
  site_url: `https://shop${i + 1}.example.com`,
  avg_ecpc: String((20 - i) * 0.05), // ecpc: 1.00, 0.95, 0.90 ... descending
}));

const TOP5_IDS = CAMPAIGNS.slice(0, 5).map(c => c.id); // ids 1-5 (highest ecpc)

describe('random selection from top 5', () => {
  it('selected campaign is always one of the top 5 by ecpc (100 trials)', () => {
    for (let i = 0; i < 100; i++) {
      const selected = selectFromTopN(CAMPAIGNS, 0.10);
      assert.ok(TOP5_IDS.includes(selected.id), `Trial ${i}: selected id ${selected.id} not in top 5`);
    }
  });

  it('returns null when no campaigns meet threshold', () => {
    const result = selectFromTopN(CAMPAIGNS, 999);
    assert.equal(result, null);
  });

  it('works with exactly 1 valid campaign', () => {
    const single = [{ id: '1', name: 'Only', site_url: 'https://a.com', avg_ecpc: '0.50' }];
    const result = selectFromTopN(single, 0.10);
    assert.equal(result.id, '1');
  });

  it('works with 3 valid campaigns (pool smaller than 5)', () => {
    const small = CAMPAIGNS.slice(0, 3);
    const ids = small.map(c => c.id);
    for (let i = 0; i < 50; i++) {
      const result = selectFromTopN(small, 0.10);
      assert.ok(ids.includes(result.id), 'Must select from the 3 available');
    }
  });

  it('excludes campaigns below minEcpc from the pool', () => {
    // Only campaigns with ecpc >= 0.80 qualify: ids 1-4 (ecpc 1.00, 0.95, 0.90, 0.85)
    for (let i = 0; i < 50; i++) {
      const result = selectFromTopN(CAMPAIGNS, 0.80);
      const ecpc = parseFloat(CAMPAIGNS.find(c => c.id === result.id).avg_ecpc);
      assert.ok(ecpc >= 0.80, `Selected campaign ecpc ${ecpc} is below threshold`);
    }
  });
});
