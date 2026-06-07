import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';

// Override DATA_DIR so metrics.js writes to a temp directory
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'metrics-test-'));
process.env.DATA_DIR = tmpDir;

const { wasRecentlyPosted, getLastPostedSource, recordRun } = await import('./metrics.js');

describe('wasRecentlyPosted', () => {
  it('returns false when nothing posted yet', () => {
    assert.equal(wasRecentlyPosted('https://example.com/a', 'Widget'), false);
  });

  it('returns true after recording a successful run with matching deeplink', () => {
    recordRun({ success: true, deeplink: 'https://example.com/b', product: 'Gadget', productSource: 'temu' });
    assert.equal(wasRecentlyPosted('https://example.com/b', 'Other'), true);
  });

  it('returns true after recording a run with matching normalized name', () => {
    recordRun({ success: true, deeplink: 'https://example.com/c', product: 'Cool Shoes', productSource: 'impact' });
    assert.equal(wasRecentlyPosted('https://different.com/x', 'Cool Shoes'), true);
  });
});

describe('getLastPostedSource', () => {
  it('returns source of most recent post', () => {
    assert.equal(getLastPostedSource(), 'impact');
  });

  it('returns a string (not null) after at least one post', () => {
    const src = getLastPostedSource();
    assert.ok(typeof src === 'string' && src.length > 0);
  });
});

after(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true });
});
