import OpenAI from 'openai';
import fetch from 'node-fetch';
import { recordCost, canAffordDalle } from '../utils/budget.js';
import { logger } from '../utils/logger.js';

let openai = null;

function getClient() {
  if (!openai) {
    if (!process.env.OPENAI_API_KEY) throw new Error('OPENAI_API_KEY not set');
    openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }
  return openai;
}

/**
 * Generates an image via DALL-E 3.
 * Returns Buffer of the PNG image, or null if budget exceeded.
 */
export async function generateProductImage(product) {
  if (!canAffordDalle()) {
    logger.warn('DALL-E skipped: daily budget cap would be exceeded');
    return null;
  }

  const prompt = `Clean product advertisement image for "${product.name}". Category: ${product.category}. Professional, bright, minimal background, no text overlay.`;

  try {
    const client = getClient();
    const response = await client.images.generate({
      model: 'dall-e-3',
      prompt,
      n: 1,
      size: '1024x1024',
      quality: 'standard',
      response_format: 'url',
    });

    const imageUrl = response.data[0]?.url;
    if (!imageUrl) throw new Error('No image URL in DALL-E response');

    const imgRes = await fetch(imageUrl);
    if (!imgRes.ok) throw new Error(`Failed to download DALL-E image: ${imgRes.status}`);

    const buffer = Buffer.from(await imgRes.arrayBuffer());
    const cost = parseFloat(process.env.DALLE_COST_PER_IMAGE || '0.04');
    recordCost(cost);
    logger.info(`DALL-E image generated (${buffer.length} bytes), cost: $${cost}`);
    return buffer;
  } catch (err) {
    logger.error(`DALL-E generation failed: ${err.message}`);
    return null;
  }
}
