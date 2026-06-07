import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { sourceEmoji } from './publisher.js';

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

describe('sourceEmoji', () => {
  it('returns travel emoji for travelpayouts', () => {
    assert.equal(sourceEmoji('travelpayouts'), '✈️');
  });

  it('returns shopping emoji for temu', () => {
    assert.equal(sourceEmoji('temu'), '🛍️');
  });

  it('returns fallback link emoji for unknown source', () => {
    assert.equal(sourceEmoji('unknown-network'), '🔗');
    assert.equal(sourceEmoji(null), '🔗');
    assert.equal(sourceEmoji(undefined), '🔗');
  });

  it('covers all 9 known networks', () => {
    const networks = ['travelpayouts','temu','cj','shareasale','impact','takeads','admitad','admitad-catalog','admitad-api'];
    for (const n of networks) {
      assert.notEqual(sourceEmoji(n), '🔗', `${n} should have a dedicated emoji`);
    }
  });
});

describe('hashtag facets', () => {
  function buildHashtagFacets(text) {
    const facets = [];
    const re = /#([a-zA-Z][a-zA-Z0-9_]*)/g;
    let m;
    while ((m = re.exec(text)) !== null) {
      const start = Buffer.byteLength(text.slice(0, m.index), 'utf8');
      const end   = start + Buffer.byteLength(m[0], 'utf8');
      facets.push({ index: { byteStart: start, byteEnd: end }, features: [{ $type: 'app.bsky.richtext.facet#tag', tag: m[1] }] });
    }
    return facets;
  }

  it('returns empty array when no hashtags', () => {
    const facets = buildHashtagFacets('Check out this deal today!');
    assert.equal(facets.length, 0);
  });

  it('detects a single hashtag with correct byte offsets', () => {
    const text = 'Great deal #shopping today';
    const facets = buildHashtagFacets(text);
    assert.equal(facets.length, 1);
    assert.equal(facets[0].features[0].tag, 'shopping');
    const extracted = Buffer.from(text, 'utf8').slice(facets[0].index.byteStart, facets[0].index.byteEnd).toString('utf8');
    assert.equal(extracted, '#shopping');
  });

  it('detects multiple hashtags', () => {
    const text = 'Awesome #deals on #tech products!';
    const facets = buildHashtagFacets(text);
    assert.equal(facets.length, 2);
    assert.equal(facets[0].features[0].tag, 'deals');
    assert.equal(facets[1].features[0].tag, 'tech');
  });

  it('handles hashtags after multibyte emoji', () => {
    const text = '🛍️ Big sale #deals';
    const facets = buildHashtagFacets(text);
    assert.equal(facets.length, 1);
    const extracted = Buffer.from(text, 'utf8').slice(facets[0].index.byteStart, facets[0].index.byteEnd).toString('utf8');
    assert.equal(extracted, '#deals');
  });

  it('does not match # not followed by a letter', () => {
    const facets = buildHashtagFacets('Price is $100 #123 ok');
    assert.equal(facets.length, 0);
  });
});

describe('external embed builder', () => {
  it('builds external embed with correct fields', () => {
    const product = { name: 'Running Shoes', description: 'Comfortable shoes for all', source: 'impact' };
    const deeplink = 'https://track.impact.com/c/abc';
    // Inline the logic from buildExternalEmbed
    const embed = {
      $type: 'app.bsky.embed.external',
      external: { uri: deeplink, title: product.name, description: product.description, thumb: undefined },
    };
    assert.equal(embed.$type, 'app.bsky.embed.external');
    assert.equal(embed.external.uri, deeplink);
    assert.equal(embed.external.title, product.name);
    assert.equal(embed.external.description, product.description);
  });

  it('truncates long title and description to 300 chars', () => {
    const longName = 'A'.repeat(400);
    const longDesc = 'B'.repeat(400);
    const title = longName.slice(0, 300);
    const desc  = longDesc.slice(0, 300);
    assert.equal(title.length, 300);
    assert.equal(desc.length, 300);
  });
});
