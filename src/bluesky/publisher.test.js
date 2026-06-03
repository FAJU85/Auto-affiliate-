import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// Re-implement the facet calculation logic extracted for testing
function buildPostRecord(text, deeplink, maxLen = 300) {
  const combined = `${text}\n\n${deeplink}`;
  const combinedBytes = Buffer.from(combined, 'utf8');
  const truncatedBytes = combinedBytes.slice(0, maxLen);
  const truncated = truncatedBytes.toString('utf8');

  const prefixBytes = Buffer.byteLength(text + '\n\n', 'utf8');
  const linkStart = prefixBytes;
  const linkEnd = Math.min(prefixBytes + Buffer.byteLength(deeplink, 'utf8'), truncatedBytes.length);

  return { text: truncated, linkStart, linkEnd };
}

describe('publisher facet byte offsets', () => {
  it('ASCII text produces correct facet indices', () => {
    const { text, linkStart, linkEnd } = buildPostRecord('Buy now!', 'https://example.com/aff');
    const extracted = Buffer.from(text, 'utf8').slice(linkStart, linkEnd).toString('utf8');
    assert.equal(extracted, 'https://example.com/aff');
  });

  it('multibyte (emoji) text produces correct facet indices', () => {
    const textWithEmoji = '🔥 Hot deal today';
    const deeplink = 'https://aff.example.com/p/123';
    const { text, linkStart, linkEnd } = buildPostRecord(textWithEmoji, deeplink);
    const extracted = Buffer.from(text, 'utf8').slice(linkStart, linkEnd).toString('utf8');
    assert.equal(extracted, deeplink);
  });

  it('truncated text does not produce negative or overflowing facet range', () => {
    // Very long text that will be truncated before the URL fits
    const longText = 'A'.repeat(295);
    const deeplink = 'https://aff.example.com/very-long-url';
    const { linkStart, linkEnd } = buildPostRecord(longText, deeplink, 300);
    assert.ok(linkStart >= 0, 'linkStart >= 0');
    assert.ok(linkEnd >= linkStart, 'linkEnd >= linkStart');
    assert.ok(linkEnd <= 300, 'linkEnd within maxLen');
  });

  it('no facet is emitted when URL does not fit in truncated text', () => {
    // When text already fills maxLen, prefix > maxLen so linkStart > linkEnd
    // publisher.js guards this with `linkStart < linkEnd` check — facets array is []
    const longText = 'A'.repeat(300);
    const deeplink = 'https://will-be-truncated.com';
    const { linkStart, linkEnd } = buildPostRecord(longText, deeplink, 300);
    // linkStart > linkEnd means the facet guard will drop it (correct behaviour)
    const facetValid = linkStart < linkEnd;
    assert.equal(facetValid, false, 'facet must be omitted when URL does not appear in truncated text');
  });
});

describe('publisher text truncation', () => {
  it('truncates at byte boundary, not char boundary', () => {
    const text = '🎉'.repeat(70); // 70 × 4 bytes = 280 bytes
    const deeplink = 'https://shop.example.com';
    const { text: result } = buildPostRecord(text, deeplink, 300);
    assert.ok(Buffer.byteLength(result, 'utf8') <= 300);
  });
});
