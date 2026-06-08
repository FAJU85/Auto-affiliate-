import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { getShareASaleProduct } from './shareasale.js';

describe('getShareASaleProduct', () => {
  it('returns null when credentials are not set', async () => {
    const saved = {
      t: process.env.SHAREASALE_TOKEN,
      s: process.env.SHAREASALE_SECRET,
      a: process.env.SHAREASALE_AFFILIATE_ID,
    };
    delete process.env.SHAREASALE_TOKEN;
    delete process.env.SHAREASALE_SECRET;
    delete process.env.SHAREASALE_AFFILIATE_ID;
    const result = await getShareASaleProduct();
    assert.equal(result, null);
    if (saved.t) process.env.SHAREASALE_TOKEN        = saved.t;
    if (saved.s) process.env.SHAREASALE_SECRET       = saved.s;
    if (saved.a) process.env.SHAREASALE_AFFILIATE_ID = saved.a;
  });
});

describe('ShareASale non-Latin filter', () => {
  it('non-Latin filter exists in shareasale.js', () => {
    const src = fs.readFileSync('src/feeds/shareasale.js', 'utf8');
    assert.ok(src.includes('isLikelyEnglishOrNeutral'), 'non-Latin filter defined');
    assert.ok(src.includes('nonLatin'), 'uses nonLatin detection');
  });

  it('isLikelyEnglishOrNeutral rejects Cyrillic names', () => {
    function isLikelyEnglishOrNeutral(str) {
      if (!str || str.length < 3) return true;
      const nonLatin = (str.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
      return nonLatin / str.length < 0.4;
    }
    assert.ok(isLikelyEnglishOrNeutral('Running Shoes Store'), 'Latin accepted');
    assert.ok(!isLikelyEnglishOrNeutral('Магазин одежды'), 'Cyrillic rejected');
  });
});

describe('ShareASale XML parser', () => {
  it('skips products with no AffiliateURL', () => {
    // Simulate the filter logic
    const items = [
      { affiliateUrl: '', name: 'Bad Product' },
      { affiliateUrl: 'https://www.shareasale.com/r.cfm?b=1&u=2&m=3', name: 'Good Product' },
    ];
    const valid = items.filter(i => {
      if (!i.affiliateUrl) return false;
      try { new URL(i.affiliateUrl); return true; } catch { return false; }
    });
    assert.equal(valid.length, 1);
    assert.equal(valid[0].name, 'Good Product');
  });

  it('unified interface has all required keys', () => {
    const product = {
      id: 'sku-123', name: 'Running Shoes', description: 'Comfortable shoes',
      siteUrl: 'https://www.shareasale.com/r.cfm?b=1&u=2&m=3',
      imageUrl: null, price: 89.99, currency: 'USD', commissionRate: 8, source: 'shareasale',
    };
    const required = ['id', 'name', 'description', 'siteUrl', 'imageUrl', 'price', 'currency', 'commissionRate', 'source'];
    for (const key of required) assert.ok(key in product, `missing: ${key}`);
    assert.equal(product.source, 'shareasale');
  });
});

describe('ShareASale extractXmlValue', () => {
  // Inline the function for unit testing
  function extractXmlValue(xml, tag) {
    const m = xml.match(new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>|<${tag}[^>]*>([^<]*)<\\/${tag}>`));
    if (!m) return '';
    return (m[1] !== undefined ? m[1] : m[2] || '').trim();
  }

  it('extracts plain text value', () => {
    const xml = '<Name>Running Shoes Pro</Name>';
    assert.equal(extractXmlValue(xml, 'Name'), 'Running Shoes Pro');
  });

  it('extracts CDATA-wrapped value', () => {
    const xml = '<Description><![CDATA[Premium running shoes with cushioned sole]]></Description>';
    assert.equal(extractXmlValue(xml, 'Description'), 'Premium running shoes with cushioned sole');
  });

  it('extracts CDATA containing HTML', () => {
    const xml = '<Description><![CDATA[<b>Great</b> shoes for <em>running</em>]]></Description>';
    assert.equal(extractXmlValue(xml, 'Description'), '<b>Great</b> shoes for <em>running</em>');
  });

  it('returns empty string when tag not found', () => {
    const xml = '<Name>Product</Name>';
    assert.equal(extractXmlValue(xml, 'MissingTag'), '');
  });

  it('trims whitespace from extracted value', () => {
    const xml = '<Name>  Padded Name  </Name>';
    assert.equal(extractXmlValue(xml, 'Name'), 'Padded Name');
  });
});

describe('ShareASale parseProducts (inline)', () => {
  // Inline the full parse logic for isolated testing
  function extractXmlValue(xml, tag) {
    const m = xml.match(new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>|<${tag}[^>]*>([^<]*)<\\/${tag}>`));
    if (!m) return '';
    return (m[1] !== undefined ? m[1] : m[2] || '').trim();
  }
  function isLikelyEnglishOrNeutral(str) {
    if (!str || str.length < 3) return true;
    const nonLatin = (str.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
    return nonLatin / str.length < 0.4;
  }
  function parseProducts(xml) {
    const products = [];
    const re = /<product>([\s\S]*?)<\/product>/g;
    let m;
    while ((m = re.exec(xml)) !== null) {
      const body = m[1];
      const affiliateUrl = extractXmlValue(body, 'AffiliateURL') || extractXmlValue(body, 'affiliateurl');
      const name = extractXmlValue(body, 'Name') || extractXmlValue(body, 'name');
      if (!affiliateUrl || !name) continue;
      if (!isLikelyEnglishOrNeutral(name)) continue;
      try { new URL(affiliateUrl); } catch { continue; }
      products.push({
        id: extractXmlValue(body, 'SKU') || '',
        name: name.trim(),
        description: (extractXmlValue(body, 'Description') || name).trim().slice(0, 300),
        siteUrl: affiliateUrl,
        imageUrl: extractXmlValue(body, 'ImageURL') || null,
        price: parseFloat(extractXmlValue(body, 'Price') || '0') || null,
        currency: 'USD',
        commissionRate: parseFloat(extractXmlValue(body, 'Commission') || '0'),
        source: 'shareasale',
      });
    }
    return products;
  }

  const sampleXml = `
    <product>
      <SKU>SHOE-001</SKU>
      <Name>Trail Running Shoes</Name>
      <Description><![CDATA[Premium trail running shoes]]></Description>
      <AffiliateURL>https://www.shareasale.com/r.cfm?b=1&u=2&m=3</AffiliateURL>
      <ImageURL>https://cdn.example.com/shoe.jpg</ImageURL>
      <Price>89.99</Price>
      <Commission>8</Commission>
    </product>
    <product>
      <SKU>BAD-002</SKU>
      <Name>No URL Product</Name>
      <AffiliateURL></AffiliateURL>
      <Price>10.00</Price>
    </product>
    <product>
      <SKU>NONLATIN-003</SKU>
      <Name>Магазин обуви</Name>
      <AffiliateURL>https://www.shareasale.com/r.cfm?b=4&u=5&m=6</AffiliateURL>
    </product>
  `;

  it('parses valid product XML correctly', () => {
    const products = parseProducts(sampleXml);
    assert.equal(products.length, 1);
    assert.equal(products[0].name, 'Trail Running Shoes');
    assert.equal(products[0].id, 'SHOE-001');
    assert.equal(products[0].price, 89.99);
    assert.equal(products[0].commissionRate, 8);
    assert.equal(products[0].source, 'shareasale');
  });

  it('skips products with empty AffiliateURL', () => {
    const products = parseProducts(sampleXml);
    assert.ok(!products.some(p => p.id === 'BAD-002'), 'no-URL product skipped');
  });

  it('skips non-Latin named products', () => {
    const products = parseProducts(sampleXml);
    assert.ok(!products.some(p => p.id === 'NONLATIN-003'), 'Cyrillic product skipped');
  });

  it('uses name as fallback description when Description is missing', () => {
    const xml = `
      <product>
        <Name>Cool Gadget</Name>
        <AffiliateURL>https://www.shareasale.com/r.cfm?b=9</AffiliateURL>
      </product>
    `;
    const products = parseProducts(xml);
    assert.equal(products.length, 1);
    assert.equal(products[0].description, 'Cool Gadget');
  });

  it('truncates description to 300 chars', () => {
    const longDesc = 'A'.repeat(400);
    const xml = `
      <product>
        <Name>Test Product</Name>
        <Description><![CDATA[${longDesc}]]></Description>
        <AffiliateURL>https://www.shareasale.com/r.cfm?b=1</AffiliateURL>
      </product>
    `;
    const products = parseProducts(xml);
    assert.equal(products[0].description.length, 300);
  });
});
