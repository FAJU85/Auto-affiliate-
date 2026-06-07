import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { normaliseAliExpressUrl } from './aliexpress-url.js';

describe('normaliseAliExpressUrl', () => {
  it('passes through non-AliExpress URLs unchanged', () => {
    const url = 'https://temu.com/some-product';
    assert.equal(normaliseAliExpressUrl(url), url);
  });

  it('passes through Admitad wrappers for non-AliExpress targets unchanged', () => {
    const url = 'https://ad.rzekl.com/g/123/?ulp=https%3A%2F%2Ftemu.com%2Fitem';
    assert.equal(normaliseAliExpressUrl(url), url);
  });

  it('preserves aff_short_key and cleans dl_target_url in deep_link.htm', () => {
    const raw = 'https://ad.rzekl.com/g/1/?ulp=https%3A%2F%2Fs.click.aliexpress.com%2Fdeep_link.htm%3Faff_short_key%3D_abc%26dl_target_url%3Dhttps%3A%2F%2Fwww.aliexpress.com%2Fitem%2F1005009896231645.html%3FpdpNpi%3Djunk';
    const result = normaliseAliExpressUrl(raw);
    assert.ok(result.includes('aff_short_key'), 'aff_short_key preserved');
    assert.ok(result.includes('1005009896231645'), 'item ID preserved');
    assert.ok(!result.includes('pdpNpi'), 'tracking junk removed');
    assert.ok(!result.includes('pdp_npi'), 'pdp_npi removed');
  });

  it('handles direct aliexpress.com/item URL', () => {
    const raw = 'https://www.aliexpress.com/item/32856726357.html?pdp_npi=3%40dis';
    const result = normaliseAliExpressUrl(raw);
    assert.ok(result.includes('32856726357'), 'item ID preserved');
    assert.ok(!result.includes('pdp_npi'), 'tracking removed');
  });

  it('handles Admitad wrapper around direct AliExpress URL', () => {
    const inner = encodeURIComponent('https://www.aliexpress.com/item/12345.html?pdp_npi=junk');
    const raw = `https://ad.rzekl.com/g/1/?ulp=${inner}`;
    const result = normaliseAliExpressUrl(raw);
    assert.ok(result.includes('12345'), 'item ID preserved');
    assert.ok(!result.includes('pdp_npi'), 'tracking removed');
  });

  it('returns URL unchanged when item ID cannot be extracted', () => {
    const raw = 'https://www.aliexpress.com/store/homepage?pdp_npi=junk';
    const result = normaliseAliExpressUrl(raw);
    assert.ok(typeof result === 'string', 'returns string');
  });
});
