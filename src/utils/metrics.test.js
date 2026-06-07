import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';

// Override DATA_DIR so metrics.js writes to a temp directory
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'metrics-test-'));
process.env.DATA_DIR = tmpDir;

const { wasRecentlyPosted, getLastPostedSource, getRecentPostedSources, getDailyNetworkStats, recordRun } = await import('./metrics.js');

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

describe('getRecentPostedSources', () => {
  it('returns an array of recent sources', () => {
    const sources = getRecentPostedSources(5);
    assert.ok(Array.isArray(sources));
    assert.ok(sources.length > 0);
    assert.ok(sources.every(s => typeof s === 'string' && s.length > 0), 'all elements are non-empty strings');
  });

  it('returns at most n sources', () => {
    const sources = getRecentPostedSources(1);
    assert.ok(sources.length <= 1);
  });
});

describe('getDailyNetworkStats', () => {
  it('returns an array of N day objects', () => {
    const stats = getDailyNetworkStats(7);
    assert.equal(stats.length, 7);
    assert.ok(stats.every(d => typeof d.date === 'string' && d.date.length === 10));
  });

  it('reflects recorded runs in byNetwork', () => {
    recordRun({ success: true, deeplink: 'https://example.com/d', product: 'Headphones', productSource: 'cj' });
    const stats = getDailyNetworkStats(1);
    assert.equal(stats.length, 1);
    assert.ok(stats[0].byNetwork.cj >= 1);
  });

  it('counts failed runs separately', () => {
    recordRun({ success: false, deeplink: null, product: null, productSource: null, error: 'timeout' });
    const stats = getDailyNetworkStats(1);
    assert.ok(stats[0].failed >= 1);
  });
});

after(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true });
});
