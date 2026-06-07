import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// Test the og:image regex patterns extracted from imagesearch.js
// property before content
const OG_REGEX_A = /<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i;
// content before property
const OG_REGEX_B = /<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i;
const IMG_REGEX = /<img[^>]+src=["'](https:\/\/[^"']+)["']/i;

describe('og:image extraction regex', () => {
  it('matches property-before-content form', () => {
    const html = `<meta property="og:image" content="https://cdn.example.com/img.jpg">`;
    const m = html.match(OG_REGEX_A);
    assert.ok(m, 'regex matches');
    assert.equal(m[1], 'https://cdn.example.com/img.jpg');
  });

  it('matches content-before-property form', () => {
    const html = `<meta content="https://cdn.example.com/img2.jpg" property="og:image">`;
    const m = html.match(OG_REGEX_B);
    assert.ok(m, 'regex matches alternate form');
    assert.equal(m[1], 'https://cdn.example.com/img2.jpg');
  });

  it('does not match unrelated meta tags', () => {
    const html = `<meta property="og:title" content="My Product">`;
    const m = html.match(OG_REGEX_A) || html.match(OG_REGEX_B);
    assert.equal(m, null);
  });

  it('handles single quotes', () => {
    const html = `<meta property='og:image' content='https://cdn.example.com/sq.jpg'>`;
    const m = html.match(OG_REGEX_A);
    assert.ok(m);
    assert.equal(m[1], 'https://cdn.example.com/sq.jpg');
  });
});

describe('first img src fallback regex', () => {
  it('extracts first https img src', () => {
    const html = `<img class="hero" src="https://img.example.com/product.jpg" alt="Product">`;
    const m = html.match(IMG_REGEX);
    assert.ok(m);
    assert.equal(m[1], 'https://img.example.com/product.jpg');
  });

  it('does not match http:// src (only https)', () => {
    const html = `<img src="http://insecure.example.com/img.jpg">`;
    const m = html.match(IMG_REGEX);
    assert.equal(m, null);
  });

  it('does not match relative src', () => {
    const html = `<img src="/images/product.jpg">`;
    const m = html.match(IMG_REGEX);
    assert.equal(m, null);
  });
});

describe('bad image URL detection', () => {
  const BAD_URLS = [
    'https://example.com/logo.png',
    'https://example.com/qr_code.jpg',
    'https://example.com/sprite.svg',
    'https://example.com/placeholder.jpg',
    'https://example.com/no_image.gif',
    'data:image/png;base64,abc',
  ];
  const GOOD_URLS = [
    'https://example.com/product-image.jpg',
    'https://cdn.aliexpress.com/img/product123.jpg',
    'https://shop.example.com/items/shoes-blue.webp',
  ];

  it('flags bad image URLs (logo, QR, placeholder, etc)', () => {
    const src = (() => {
      // Inline the isBadImageUrl logic from imagesearch.js
      const BAD_URL_PATTERNS = [
        /qr[_\-.]?code/i, /barcode/i, /captcha/i,
        /\blogo\b/i, /sprite/i, /icon\.(png|svg|gif|webp)$/i,
        /placeholder/i, /default[-_]image/i, /no[-_]image/i, /blank/i,
        /selene-static/i, /data:image/i,
      ];
      return url => {
        if (!url || typeof url !== 'string') return true;
        if (!url.startsWith('http')) return true;
        return BAD_URL_PATTERNS.some(p => p.test(url));
      };
    })();

    for (const u of BAD_URLS) assert.ok(src(u), `should be bad: ${u}`);
    for (const u of GOOD_URLS) assert.ok(!src(u), `should be good: ${u}`);
  });
});

describe('findProductImage returns null on all-fail', () => {
  it('LANGSEARCH_API_KEY absent and no siteUrl → returns null', async () => {
    delete process.env.LANGSEARCH_API_KEY;
    const { findProductImage } = await import('./imagesearch.js');
    const result = await findProductImage('Test Product', null);
    assert.equal(result, null);
  });
});
