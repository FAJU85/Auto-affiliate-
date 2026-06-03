import { describe, it, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'atomic-test-'));

after(() => fs.rmSync(tmpDir, { recursive: true, force: true }));

describe('atomic write pattern (tmp + rename)', () => {
  it('leaves no .tmp file on success', () => {
    const file = path.join(tmpDir, 'test.json');
    const tmp = `${file}.tmp`;
    const data = JSON.stringify({ value: 42 });

    fs.writeFileSync(tmp, data);
    fs.renameSync(tmp, file);

    assert.ok(fs.existsSync(file), 'target file exists');
    assert.ok(!fs.existsSync(tmp), 'tmp file removed');
    assert.equal(JSON.parse(fs.readFileSync(file, 'utf8')).value, 42);
  });

  it('target is unchanged if tmp write fails before rename', () => {
    const file = path.join(tmpDir, 'stable.json');
    fs.writeFileSync(file, JSON.stringify({ original: true }));

    // Simulate crash before rename — tmp exists but rename never called
    const tmp = `${file}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify({ corrupt: true }));
    // "crash" — do NOT call renameSync

    const content = JSON.parse(fs.readFileSync(file, 'utf8'));
    assert.equal(content.original, true, 'original file untouched');
  });
});
