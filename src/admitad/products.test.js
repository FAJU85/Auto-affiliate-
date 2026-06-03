import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// Filter logic extracted for unit testing without network calls
function filterAndSort(campaigns, minEcpc) {
  const filtered = campaigns.filter(c => {
    const hasUrl = !!c.site_url;
    const ecpc = parseFloat(c.avg_ecpc || 0);
    return hasUrl && ecpc >= minEcpc;
  });
  filtered.sort((a, b) => parseFloat(b.avg_ecpc || 0) - parseFloat(a.avg_ecpc || 0));
  return filtered;
}

const SAMPLE = [
  { id: '1', name: 'Low ECPC', site_url: 'https://a.com', avg_ecpc: '0.05' },
  { id: '2', name: 'No URL',   site_url: '',              avg_ecpc: '0.50' },
  { id: '3', name: 'Best',     site_url: 'https://b.com', avg_ecpc: '0.25' },
  { id: '4', name: 'Good',     site_url: 'https://c.com', avg_ecpc: '0.15' },
];

describe('admitad product filtering', () => {
  it('excludes items below minEcpc', () => {
    const result = filterAndSort(SAMPLE, 0.10);
    const ids = result.map(c => c.id);
    assert.ok(!ids.includes('1'), 'Low ECPC item excluded');
  });

  it('excludes items without a URL', () => {
    const result = filterAndSort(SAMPLE, 0.10);
    const ids = result.map(c => c.id);
    assert.ok(!ids.includes('2'), 'No-URL item excluded');
  });

  it('sorts by ecpc descending', () => {
    const result = filterAndSort(SAMPLE, 0.10);
    assert.equal(result[0].id, '3', 'Best ECPC item is first');
    assert.equal(result[1].id, '4');
  });

  it('returns empty array when nothing qualifies', () => {
    const result = filterAndSort(SAMPLE, 1.00);
    assert.equal(result.length, 0);
  });

  it('minEcpc threshold is respected (not just > 0)', () => {
    // With minEcpc = 0.10, item with ecpc=0.05 must be excluded
    const result = filterAndSort(SAMPLE, 0.10);
    assert.ok(result.every(c => parseFloat(c.avg_ecpc) >= 0.10));
  });
});
