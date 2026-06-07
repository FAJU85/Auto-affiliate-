import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

// api-inference.huggingface.co is not reachable from within HF Spaces containers
const HF_UPSCALER_ENABLED = false;
const HF_UPSCALER_URL = 'https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-x4-upscaler';
const TIMEOUT_MS = 90_000;
const BACKOFFS    = [10_000, 30_000, 60_000];

async function callUpscalerApi(token, imageBuffer) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(HF_UPSCALER_URL, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/octet-stream' },
      body: imageBuffer,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Upscales an image buffer using HuggingFace stable-diffusion-x4-upscaler.
 * Returns upscaled Buffer or original buffer on any failure.
 */
export async function upscaleImage(imageBuffer) {
  if (!HF_UPSCALER_ENABLED) return imageBuffer;
  const token = process.env.HF_API_TOKEN;
  if (!token) return imageBuffer;

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await callUpscalerApi(token, imageBuffer);

      if (res.status === 503) {
        const waitMs = BACKOFFS[attempt] ?? 60_000;
        logger.warn(`HF upscaler loading, waiting ${waitMs / 1000}s (attempt ${attempt + 1})`);
        await sleep(waitMs);
        continue;
      }
      if (res.status === 429) {
        logger.warn(`HF upscaler rate limited (attempt ${attempt + 1}), backing off 15s`);
        await sleep(15_000);
        continue;
      }
      if (!res.ok) throw new Error(`HF upscaler error ${res.status}: ${await res.text()}`);

      const upscaled = Buffer.from(await res.arrayBuffer());
      logger.info(`Image upscaled: ${imageBuffer.length} → ${upscaled.length} bytes`);
      return upscaled;
    } catch (err) {
      logger.warn(`Upscale attempt ${attempt + 1} failed: ${err.message}`);
    }
  }

  logger.warn('All upscale attempts failed, returning original buffer');
  return imageBuffer;
}
