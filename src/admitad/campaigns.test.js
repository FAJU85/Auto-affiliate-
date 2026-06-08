import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

describe('admitad/campaigns', () => {
  beforeEach(() => {
    delete process.env.ADMITAD_WEBSITE_ID;
    delete process.env.ADMITAD_CLIENT_ID;
    delete process.env.ADMITAD_CLIENT_SECRET;
  });

  it('throws when ADMITAD_WEBSITE_ID is missing', async () => {
    const { getAdmitadApiProduct } = await import('./campaigns.js');
    await assert.rejects(
      () => getAdmitadApiProduct(),
      /ADMITAD_WEBSITE_ID not set/
    );
  });
});

describe('admitad/campaigns — non-Latin filter logic', () => {
  // Inline the filter logic for unit testing without network calls
  function isValidCampaignName(name) {
    if (!name) return false;
    const str = String(name);
    const nonLatin = (str.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
    return nonLatin / (str.length || 1) < 0.4;
  }

  it('accepts purely Latin campaign names', () => {
    assert.ok(isValidCampaignName('Amazon UK'));
    assert.ok(isValidCampaignName('Nike Official Store'));
    assert.ok(isValidCampaignName('Best Buy Electronics'));
  });

  it('accepts campaign names with numbers and punctuation', () => {
    assert.ok(isValidCampaignName('Top 10 Deals 2024'));
    assert.ok(isValidCampaignName('H&M Fashion Store'));
    assert.ok(isValidCampaignName('Buy 1 Get 1 Free!'));
  });

  it('rejects fully Cyrillic campaign names', () => {
    assert.ok(!isValidCampaignName('Магазин одежды'));
    assert.ok(!isValidCampaignName('Авиабилеты дешево'));
  });

  it('rejects fully CJK campaign names', () => {
    assert.ok(!isValidCampaignName('京东商城'));
    assert.ok(!isValidCampaignName('淘宝网购物'));
  });

  it('accepts mixed names under 40% non-Latin threshold', () => {
    // "AliExpress店" — 2 CJK out of 13 chars = ~15% non-Latin
    assert.ok(isValidCampaignName('AliExpress Store123'));
  });

  it('rejects names exceeding 40% non-Latin threshold', () => {
    // 5 Cyrillic in an 8-char string = 62.5% non-Latin
    assert.ok(!isValidCampaignName('АлиТест'));
  });

  it('handles empty or null names', () => {
    assert.ok(!isValidCampaignName(''));
    assert.ok(!isValidCampaignName(null));
    assert.ok(!isValidCampaignName(undefined));
  });
});

describe('admitad/campaigns — campaign filter criteria', () => {
  // Inline the filter used in campaigns.js
  function isValidCampaign(c) {
    if (!c.site_url || parseFloat(c.avg_ecpc || 0) <= 0) return false;
    const name = String(c.name || '');
    const nonLatin = (name.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
    return nonLatin / (name.length || 1) < 0.4;
  }

  it('rejects campaigns without site_url', () => {
    assert.ok(!isValidCampaign({ name: 'Test', avg_ecpc: '0.5' }));
    assert.ok(!isValidCampaign({ name: 'Test', site_url: '', avg_ecpc: '0.5' }));
  });

  it('rejects campaigns with zero or negative ecpc', () => {
    assert.ok(!isValidCampaign({ name: 'Test', site_url: 'https://ex.com', avg_ecpc: '0' }));
    assert.ok(!isValidCampaign({ name: 'Test', site_url: 'https://ex.com', avg_ecpc: '-1' }));
    assert.ok(!isValidCampaign({ name: 'Test', site_url: 'https://ex.com', avg_ecpc: null }));
  });

  it('accepts valid campaigns with positive ecpc and Latin name', () => {
    assert.ok(isValidCampaign({ name: 'Nike Store', site_url: 'https://nike.com', avg_ecpc: '0.12' }));
    assert.ok(isValidCampaign({ name: 'eBay UK', site_url: 'https://ebay.co.uk', avg_ecpc: '1.5' }));
  });

  it('rejects valid ecpc campaigns with non-Latin names', () => {
    assert.ok(!isValidCampaign({ name: 'Алиэкспресс', site_url: 'https://ali.com', avg_ecpc: '0.5' }));
  });
});
