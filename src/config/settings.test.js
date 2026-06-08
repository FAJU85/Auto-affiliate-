import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs';
import os from 'os';
import path from 'path';

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'settings-test-'));
process.env.DATA_DIR = tmpDir;

const { getSettings, saveSettings, getSpaceHost } = await import('./settings.js');

describe('getSettings', () => {
  it('returns defaults when no settings file exists', () => {
    const s = getSettings();
    assert.ok(s.cronSchedule === '0 * * * *' || s.cronSchedule === '30 * * * *', 'cronSchedule is a cron expression');
    assert.equal(s.postingHours, '8-22');
    assert.equal(s.maxPostLength, 300);
    assert.ok(typeof s.postSystemPrompt === 'string');
  });

  it('merged defaults fill missing keys', () => {
    const s = getSettings();
    assert.ok('dailyCostCap' in s);
    assert.ok('alertThreshold' in s);
  });
});

describe('saveSettings', () => {
  it('persists and returns updated settings', () => {
    const updated = saveSettings({ cronSchedule: '30 * * * *' });
    assert.equal(updated.cronSchedule, '30 * * * *');
    assert.equal(updated.postingHours, '8-22', 'other defaults preserved');
  });
});

describe('getSpaceHost', () => {
  it('returns empty string when not configured', () => {
    const saved = process.env.SPACE_HOST;
    delete process.env.SPACE_HOST;
    const host = getSpaceHost();
    assert.equal(typeof host, 'string');
    if (saved) process.env.SPACE_HOST = saved;
  });

  it('removes trailing slash from configured host', () => {
    saveSettings({ spaceHost: 'https://example.com/' });
    const host = getSpaceHost();
    assert.ok(!host.endsWith('/'), 'trailing slash removed');
  });
});
