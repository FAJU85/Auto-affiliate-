import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

describe('admitad/auth', () => {
  beforeEach(() => {
    delete process.env.ADMITAD_CLIENT_ID;
    delete process.env.ADMITAD_CLIENT_SECRET;
  });

  it('getAdmitadToken throws when credentials missing', async () => {
    const { getAdmitadToken } = await import('./auth.js');
    await assert.rejects(
      () => getAdmitadToken(),
      /Missing ADMITAD_CLIENT_ID/
    );
  });

  it('invalidateAdmitadToken is exported as a function', async () => {
    const { invalidateAdmitadToken } = await import('./auth.js');
    assert.equal(typeof invalidateAdmitadToken, 'function');
    // Should not throw
    invalidateAdmitadToken();
  });
});
