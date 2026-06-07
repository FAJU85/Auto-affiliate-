import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';

describe('hf-secrets guards', () => {
  it('writeSecret returns false when SPACE_ID is missing', async () => {
    const saved = process.env.SPACE_ID;
    const savedToken = process.env.HF_TOKEN;
    delete process.env.SPACE_ID;
    delete process.env.HF_TOKEN;

    const { writeSecret } = await import('./hf-secrets.js');
    const result = await writeSecret('TEST_KEY', 'test_value');
    assert.equal(result, false, 'returns false without credentials');

    if (saved !== undefined) process.env.SPACE_ID = saved;
    if (savedToken !== undefined) process.env.HF_TOKEN = savedToken;
  });

  it('writeSecret returns false when HF_TOKEN is missing', async () => {
    const saved = process.env.HF_TOKEN;
    delete process.env.HF_TOKEN;
    process.env.SPACE_ID = 'owner/space';

    const { writeSecret } = await import('./hf-secrets.js');
    const result = await writeSecret('TEST_KEY', 'test_value');
    assert.equal(result, false, 'returns false without token');

    delete process.env.SPACE_ID;
    if (saved !== undefined) process.env.HF_TOKEN = saved;
  });

  it('deleteSecret resolves without throwing when credentials missing', async () => {
    delete process.env.SPACE_ID;
    delete process.env.HF_TOKEN;

    const { deleteSecret } = await import('./hf-secrets.js');
    await assert.doesNotReject(() => deleteSecret('TEST_KEY'), 'no throw when unconfigured');
  });
});
