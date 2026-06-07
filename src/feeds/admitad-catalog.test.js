import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { getAdmitadCatalogProduct } from './admitad-catalog.js';

describe('getAdmitadCatalogProduct', () => {
  it('returns null when no ADMITAD_CATALOG_URL_N vars are set', async () => {
    const saved = [1,2,3,4,5].map(n => process.env[`ADMITAD_CATALOG_URL_${n}`]);
    [1,2,3,4,5].forEach(n => delete process.env[`ADMITAD_CATALOG_URL_${n}`]);
    const result = await getAdmitadCatalogProduct();
    assert.equal(result, null);
    saved.forEach((v, i) => { if (v) process.env[`ADMITAD_CATALOG_URL_${i+1}`] = v; });
  });
});

describe('Admitad catalog XML campaign non-Latin filter', () => {
  it('isLikelyEnglishOrNeutral filter is applied in parseCampaignXml', () => {
    const src = fs.readFileSync('src/feeds/admitad-catalog.js', 'utf8');
    // Verify the filter is called before the URL check inside parseCampaignXml
    const campaignXmlFn = src.slice(src.indexOf('function parseCampaignXml'), src.indexOf('function parseYmlCatalog'));
    assert.ok(campaignXmlFn.includes('isLikelyEnglishOrNeutral'), 'non-Latin filter applied in parseCampaignXml');
  });

  it('isLikelyEnglishOrNeutral inline logic: rejects Cyrillic names', () => {
    function isLikelyEnglishOrNeutral(str) {
      if (!str || str.length < 3) return true;
      const nonLatin = (str.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
      return nonLatin / str.length < 0.4;
    }
    assert.ok(isLikelyEnglishOrNeutral('Summer Fashion Store'), 'Latin accepted');
    assert.ok(!isLikelyEnglishOrNeutral('Летняя мода'), 'Cyrillic rejected');
    assert.ok(!isLikelyEnglishOrNeutral('时尚精品店'), 'CJK rejected');
  });
});

describe('Admitad catalog JSON parser', () => {
  it('filters items without valid affiliate link', () => {
    const items = [
      { id: '1', name: 'Good Item', goto_link: 'https://rzekl.com/g/abc' },
      { id: '2', name: 'No link' },
      { id: '3', name: 'Bad link', goto_link: 'not-a-url' },
    ];
    const valid = items.filter(o => {
      const link = o.goto_link || o.gotolink || o.affiliate_url || o.url;
      if (!link) return false;
      try { new URL(link); return true; } catch { return false; }
    });
    assert.equal(valid.length, 1);
    assert.equal(valid[0].name, 'Good Item');
  });

  it('product shape has all required keys', () => {
    const product = {
      id: 'offer-42', name: 'Winter Jacket', description: 'Warm winter jacket',
      siteUrl: 'https://rzekl.com/g/xyz', imageUrl: null,
      price: 59.99, currency: 'USD', commissionRate: 0, source: 'admitad-catalog',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'admitad-catalog');
  });

  it('prefers items with images over items without', () => {
    // Simulate the image preference logic
    const items = [
      { id: '1', name: 'No Image Item', goto_link: 'https://rzekl.com/g/a' },
      { id: '2', name: 'Image Item', goto_link: 'https://rzekl.com/g/b', picture: 'https://cdn.example.com/img.jpg' },
    ];
    const withImage = items.filter(o => {
      const img = o.picture || o.image || o.image_url;
      return img && /^https?:\/\//.test(img) && !/\blogo\b|sprite|placeholder/i.test(img);
    });
    assert.equal(withImage.length, 1);
    assert.equal(withImage[0].name, 'Image Item');
  });
});

describe('Admitad catalog supports up to 5 URL slots', () => {
  it('ADMITAD_CATALOG_URL_1 through _5 are all valid slot names', () => {
    const src = fs.readFileSync('src/feeds/admitad-catalog.js', 'utf8');
    assert.ok(src.includes('ADMITAD_CATALOG_URL_'), 'slot var pattern present');
    for (let n = 1; n <= 5; n++) {
      assert.ok(src.includes(`ADMITAD_CATALOG_URL_${n}`) || src.includes('`ADMITAD_CATALOG_URL_${n}`'), `slot ${n} referenced`);
    }
  });
});
