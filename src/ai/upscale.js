import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

const HF_UPSCALER_URL = 'https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-x4-upscaler';
const TIMEOUT_MS = 90_000;

/**
 * Upscales an image buffer using HuggingFace stable-diffusion-x4-upscaler.
 * Returns upscaled Buffer or original buffer on any failure.
 */
export async function upscaleImage(imageBuffer) {
  const token = process.env.HF_API_TOKEN;
  if (!token) {
    logger.warn('HF_API_TOKEN not set, skipping upscale');
    return imageBuffer;
  }

  const backoffs = [10_000, 30_000, 60_000];

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

      let res;
      try {
        res = await fetch(HF_UPSCALER_URL, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/octet-stream',
          },
          body: imageBuffer,
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timeout);
      }

      if (res.status === 503) {
        const waitMs = backoffs[attempt] ?? 60_000;
        logger.warn(`HF upscaler loading, waiting ${waitMs / 1000}s (attempt ${attempt + 1})`);
        await sleep(waitMs);
        continue;
      }

      if (res.status === 429) {
        logger.warn(`HF upscaler rate limited (attempt ${attempt + 1}), backing off 15s`);
        await sleep(15_000);
        continue;
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HF upscaler error ${res.status}: ${text}`);
      }

      const upscaled = Buffer.from(await res.arrayBuffer());
      logger.info(`Image upscaled: ${imageBuffer.length} → ${upscaled.length} bytes`);
      return upscaled;
    } catch (err) {
      logger.warn(`Upscale attempt ${attempt + 1} failed: ${err.message}`);
      if (attempt < 2) continue;
    }
  }

  logger.warn('All upscale attempts failed, returning original buffer');
  return imageBuffer;
}
