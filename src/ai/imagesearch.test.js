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

describe('findProductImage returns null on all-fail', () => {
  it('LANGSEARCH_API_KEY absent and no siteUrl → returns null', async () => {
    delete process.env.LANGSEARCH_API_KEY;
    const { findProductImage } = await import('./imagesearch.js');
    const result = await findProductImage('Test Product', null);
    assert.equal(result, null);
  });
});
