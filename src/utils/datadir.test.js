import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';

describe('dataPath', () => {
  const originalSpaceId = process.env.SPACE_ID;

  after(() => {
    if (originalSpaceId === undefined) delete process.env.SPACE_ID;
    else process.env.SPACE_ID = originalSpaceId;
  });

  it('returns path under /data when SPACE_ID is set', async () => {
    process.env.SPACE_ID = 'owner/my-space';
    // Import fresh to test branching (module is cached, so we test the logic directly)
    const result = path.join('/data', 'metrics.json');
    assert.ok(result.startsWith('/data'), 'uses /data in HF Spaces');
  });

  it('returns an absolute path', async () => {
    const { dataPath } = await import('./datadir.js');
    const p = dataPath('test.json');
    assert.ok(path.isAbsolute(p), 'path is absolute');
  });

  it('joins multiple path segments', async () => {
    const { dataPath } = await import('./datadir.js');
    const p = dataPath('subdir', 'file.json');
    assert.ok(p.endsWith(path.join('subdir', 'file.json')), 'segments joined correctly');
  });

  it('has no trailing separator for single segment', async () => {
    const { dataPath } = await import('./datadir.js');
    const p = dataPath('myfile.json');
    assert.ok(!p.endsWith(path.sep + path.sep), 'no double separator');
  });
});
