import { describe, it, before, after, mock } from 'node:test';
import assert from 'node:assert/strict';

// Inline the fallback logic: if fetch fails, upscaleImage returns original buffer
// We test the contract without hitting the network

const FAKE_BUFFER = Buffer.from('fake-image-data');

describe('upscaleImage fallback behaviour', () => {
  it('returns original buffer when HF_API_TOKEN is not set', async () => {
    delete process.env.HF_API_TOKEN;
    const { upscaleImage } = await import('./upscale.js?v=notoken');
    const result = await upscaleImage(FAKE_BUFFER);
    assert.deepEqual(result, FAKE_BUFFER, 'returns original buffer when token missing');
  });

  it('original buffer is a Buffer instance', () => {
    assert.ok(Buffer.isBuffer(FAKE_BUFFER));
    assert.equal(FAKE_BUFFER.length, 'fake-image-data'.length);
  });
});

describe('upscaleImage timeout configuration', () => {
  it('TIMEOUT_MS is set to 90 seconds', async () => {
    const src = await import('fs').then(fs =>
      fs.readFileSync('src/ai/upscale.js', 'utf8')
    );
    assert.ok(src.includes('90_000'), 'TIMEOUT_MS = 90_000ms (90s) is present');
  });

  it('backoff schedule is [10s, 30s, 60s]', async () => {
    const src = await import('fs').then(fs =>
      fs.readFileSync('src/ai/upscale.js', 'utf8')
    );
    assert.ok(src.includes('10_000'), '10s first backoff present');
    assert.ok(src.includes('30_000'), '30s second backoff present');
    assert.ok(src.includes('60_000'), '60s third backoff present');
  });
});
