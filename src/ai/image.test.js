import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

describe('ai/image DALL-E guard', () => {
  beforeEach(() => {
    delete process.env.OPENAI_API_KEY;
  });

  it('returns null when OPENAI_API_KEY missing and budget exceeded (or key absent)', async () => {
    // canAffordDalle reads DAILY_COST_CAP_USD; set a cap of 0 so it refuses
    const saved = process.env.DAILY_COST_CAP_USD;
    process.env.DAILY_COST_CAP_USD = '0';
    try {
      const { generateProductImage } = await import('./image.js');
      const result = await generateProductImage({ name: 'Test', category: 'Electronics' });
      assert.equal(result, null);
    } finally {
      if (saved !== undefined) process.env.DAILY_COST_CAP_USD = saved;
      else delete process.env.DAILY_COST_CAP_USD;
    }
  });
});
