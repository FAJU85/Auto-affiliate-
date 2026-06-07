import sharp from 'sharp';
import { logger } from '../utils/logger.js';

const MAX_DIMENSION = 1200; // px — Bluesky renders at ≤1200px wide
const MAX_BYTES     = 950_000; // stay under Bluesky's 976 848-byte blob limit

/**
 * Resizes and re-encodes an image buffer to fit Bluesky's upload constraints.
 * Returns the optimised buffer, or the original if already within limits.
 */
export async function optimiseImage(buf) {
  if (!buf) return buf;
  try {
    const meta = await sharp(buf).metadata();
    const needsResize = (meta.width > MAX_DIMENSION || meta.height > MAX_DIMENSION);
    const needsReencode = buf.length > MAX_BYTES;

    if (!needsResize && !needsReencode) return buf;

    let pipeline = sharp(buf);
    if (needsResize) {
      pipeline = pipeline.resize(MAX_DIMENSION, MAX_DIMENSION, {
        fit: 'inside',
        withoutEnlargement: true,
      });
    }

    const optimised = await pipeline.jpeg({ quality: 82, progressive: true }).toBuffer();

    if (optimised.length > MAX_BYTES) {
      // Second pass with lower quality if still too large
      const compressed = await sharp(buf)
        .resize(MAX_DIMENSION, MAX_DIMENSION, { fit: 'inside', withoutEnlargement: true })
        .jpeg({ quality: 60 })
        .toBuffer();
      logger.info(`Image optimised (q60): ${buf.length} → ${compressed.length} bytes`);
      return compressed;
    }

    logger.info(`Image optimised: ${buf.length} → ${optimised.length} bytes (${meta.width}x${meta.height} → ≤${MAX_DIMENSION}px)`);
    return optimised;
  } catch (err) {
    logger.warn(`Image optimisation failed: ${err.message} — using original`);
    return buf;
  }
}
