import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// Inline the filter+sort+random-pick logic to test without network calls
function filterSortPick(campaigns, minEcpc) {
  const filtered = campaigns.filter(c => {
    const hasUrl = !!c.site_url;
    const ecpc = parseFloat(c.avg_ecpc || 0);
    return hasUrl && ecpc >= minEcpc;
  });
  filtered.sort((a, b) => parseFloat(b.avg_ecpc || 0) - parseFloat(a.avg_ecpc || 0));
  if (filtered.length === 0) throw new Error('No valid products found after filtering');
  const top5 = filtered.slice(0, 5);
  const idx = Math.floor(Math.random() * top5.length);
  return { picked: top5[idx], top5 };
}

const SAMPLE = [
  { id: '1', name: 'A', site_url: 'https://a.com', avg_ecpc: '0.90' },
  { id: '2', name: 'B', site_url: 'https://b.com', avg_ecpc: '0.80' },
  { id: '3', name: 'C', site_url: 'https://c.com', avg_ecpc: '0.70' },
  { id: '4', name: 'D', site_url: 'https://d.com', avg_ecpc: '0.60' },
  { id: '5', name: 'E', site_url: 'https://e.com', avg_ecpc: '0.50' },
  { id: '6', name: 'F', site_url: 'https://f.com', avg_ecpc: '0.40' },
  { id: '7', name: 'G', site_url: '',              avg_ecpc: '0.99' },
  { id: '8', name: 'H', site_url: 'https://h.com', avg_ecpc: '0.01' },
];

const TOP5_IDS = new Set(['1', '2', '3', '4', '5']);

describe('random selection always picks from top-5 by ecpc', () => {
  it('runs 100 times and always selects from top-5 candidates', () => {
    for (let i = 0; i < 100; i++) {
      const { picked, top5 } = filterSortPick(SAMPLE, 0.10);
      assert.ok(TOP5_IDS.has(picked.id), `Iteration ${i}: picked id=${picked.id} is not in top-5`);
      assert.equal(top5.length, 5, 'top5 should have 5 elements');
    }
  });

  it('top-5 are sorted by ecpc desc', () => {
    const { top5 } = filterSortPick(SAMPLE, 0.10);
    assert.equal(top5[0].id, '1');
    assert.equal(top5[1].id, '2');
    assert.equal(top5[2].id, '3');
    assert.equal(top5[3].id, '4');
    assert.equal(top5[4].id, '5');
  });

  it('item ranked 6th is never picked when 5+ candidates exist', () => {
    for (let i = 0; i < 200; i++) {
      const { picked } = filterSortPick(SAMPLE, 0.10);
      assert.notEqual(picked.id, '6');
    }
  });

  it('works correctly when fewer than 5 candidates exist', () => {
    const small = SAMPLE.slice(0, 3);
    for (let i = 0; i < 50; i++) {
      const { picked, top5 } = filterSortPick(small, 0.10);
      assert.ok(['1', '2', '3'].includes(picked.id));
      assert.equal(top5.length, 3);
    }
  });

  it('throws when no candidates pass the filter', () => {
    assert.throws(
      () => filterSortPick(SAMPLE, 999),
      /No valid products found after filtering/,
    );
  });
});
