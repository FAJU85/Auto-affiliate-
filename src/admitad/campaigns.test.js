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
