import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

describe('bluesky/client credential validation', () => {
  beforeEach(() => {
    delete process.env.BSKY_HANDLE;
    delete process.env.BSKY_APP_PASSWORD;
  });

  it('throws when BSKY_HANDLE and BSKY_APP_PASSWORD are missing and no OAuth', async () => {
    // Stub getOAuthAgent to return null (no OAuth session)
    const mod = await import('./client.js');
    mod.invalidateAgent(); // force fresh auth attempt
    await assert.rejects(
      () => mod.getBskyAgent(),
      /Bluesky not connected/
    );
  });

  it('exports invalidateAgent function', async () => {
    const mod = await import('./client.js');
    assert.equal(typeof mod.invalidateAgent, 'function');
  });

  it('exports getBskySession function', async () => {
    const mod = await import('./client.js');
    assert.equal(typeof mod.getBskySession, 'function');
  });
});
