import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';

// Override DATA_DIR so metrics.js writes to a temp directory
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'metrics-test-'));
process.env.DATA_DIR = tmpDir;

const {
  wasRecentlyPosted, getLastPostedSource, getRecentPostedSources,
  getDailyNetworkStats, purgePostedBySource, recordRun,
  recordEngagement, getTopPosts, getDedupBySource, getRecentRuns,
} = await import('./metrics.js');

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

describe('purgePostedBySource', () => {
  it('removes entries for the specified source', () => {
    recordRun({ success: true, deeplink: 'https://example.com/purge1', product: 'PurgeItem', productSource: 'shareasale' });
    const removed = purgePostedBySource('shareasale');
    assert.ok(removed >= 1, 'at least one entry removed');
  });

  it('does not remove entries for other sources', () => {
    recordRun({ success: true, deeplink: 'https://example.com/keep1', product: 'KeepItem', productSource: 'temu' });
    purgePostedBySource('shareasale');
    // temu entry should still exist
    assert.ok(wasRecentlyPosted('https://example.com/keep1', 'KeepItem'), 'other source entry preserved');
  });

  it('returns 0 when source has no entries', () => {
    const removed = purgePostedBySource('nonexistent-network');
    assert.equal(removed, 0);
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

describe('getDedupBySource', () => {
  it('returns an object', () => {
    const result = getDedupBySource();
    assert.ok(result !== null && typeof result === 'object');
  });

  it('counts active entries grouped by source', () => {
    recordRun({ success: true, deeplink: 'https://example.com/dedup1', product: 'DedupItem1', productSource: 'takeads' });
    recordRun({ success: true, deeplink: 'https://example.com/dedup2', product: 'DedupItem2', productSource: 'takeads' });
    const result = getDedupBySource();
    assert.ok(result.takeads >= 2, `takeads count should be >= 2, got ${result.takeads}`);
  });

  it('different sources are counted separately', () => {
    recordRun({ success: true, deeplink: 'https://example.com/sep1', product: 'SepItem', productSource: 'cj' });
    const result = getDedupBySource();
    assert.ok(typeof result.cj === 'number' && result.cj >= 1);
    assert.ok(typeof result.takeads === 'number' && result.takeads >= 2);
  });
});

describe('recordEngagement + getTopPosts', () => {
  it('recordEngagement updates likes and reposts on a run', () => {
    const uri = 'at://did:example/post/999';
    recordRun({ success: true, deeplink: 'https://example.com/eng1', product: 'EngItem', productSource: 'impact', postUri: uri });
    recordEngagement(uri, 42, 7);
    const runs = getRecentRuns(500);
    const run = runs.find(r => r.postUri === uri);
    assert.ok(run, 'run with postUri found');
    assert.equal(run.likes, 42);
    assert.equal(run.reposts, 7);
  });

  it('recordEngagement does nothing for unknown uri', () => {
    assert.doesNotThrow(() => recordEngagement('at://unknown/post/0', 1, 0));
  });

  it('getTopPosts returns array sorted by likes desc', () => {
    const uri2 = 'at://did:example/post/888';
    recordRun({ success: true, deeplink: 'https://example.com/eng2', product: 'PopItem', productSource: 'temu', postUri: uri2 });
    recordEngagement(uri2, 100, 10);
    const top = getTopPosts(30, 5);
    assert.ok(Array.isArray(top));
    assert.ok(top.length >= 1);
    if (top.length >= 2) {
      assert.ok((top[0].likes || 0) >= (top[1].likes || 0), 'sorted by likes descending');
    }
  });

  it('getTopPosts excludes posts with 0 likes', () => {
    const uri3 = 'at://did:example/post/777';
    recordRun({ success: true, deeplink: 'https://example.com/eng3', product: 'ZeroItem', productSource: 'cj', postUri: uri3 });
    // do NOT call recordEngagement — likes stays 0
    const top = getTopPosts(30, 10);
    assert.ok(!top.find(r => r.postUri === uri3), 'zero-likes post excluded');
  });
});

after(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true });
});
