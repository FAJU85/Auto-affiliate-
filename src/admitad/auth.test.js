import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

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

  it('getAdmitadToken throws when only CLIENT_ID is set', async () => {
    process.env.ADMITAD_CLIENT_ID = 'test-id';
    delete process.env.ADMITAD_CLIENT_SECRET;
    const { getAdmitadToken } = await import('./auth.js');
    await assert.rejects(
      () => getAdmitadToken(),
      /Missing ADMITAD_CLIENT_ID or ADMITAD_CLIENT_SECRET/
    );
    delete process.env.ADMITAD_CLIENT_ID;
  });

  it('getAdmitadToken throws when only CLIENT_SECRET is set', async () => {
    delete process.env.ADMITAD_CLIENT_ID;
    process.env.ADMITAD_CLIENT_SECRET = 'test-secret';
    const { getAdmitadToken } = await import('./auth.js');
    await assert.rejects(
      () => getAdmitadToken(),
      /Missing ADMITAD_CLIENT_ID or ADMITAD_CLIENT_SECRET/
    );
    delete process.env.ADMITAD_CLIENT_SECRET;
  });
});

describe('admitad/auth module structure', () => {
  it('exports getAdmitadToken as a function', async () => {
    const mod = await import('./auth.js');
    assert.equal(typeof mod.getAdmitadToken, 'function');
  });

  it('exports invalidateAdmitadToken as a function', async () => {
    const mod = await import('./auth.js');
    assert.equal(typeof mod.invalidateAdmitadToken, 'function');
  });

  it('uses ADMITAD_SCOPE env var when set', () => {
    const src = fs.readFileSync('src/admitad/auth.js', 'utf8');
    assert.ok(src.includes('ADMITAD_SCOPE'), 'ADMITAD_SCOPE env var used');
    assert.ok(src.includes('advcampaigns'), 'default scope includes advcampaigns');
    assert.ok(src.includes('deeplink_generator'), 'default scope includes deeplink_generator');
  });
});
