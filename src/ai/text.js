import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const HF_API = 'https://api-inference.huggingface.co/models';

/**
 * Generates affiliate post text via Hugging Face Inference API (Llama 3).
 * Falls back to a template string if the API fails or rate-limits.
 */
export async function generatePostText(product, trends) {
  const model = process.env.HF_MODEL || 'meta-llama/Meta-Llama-3-8B-Instruct';
  const token = process.env.HF_API_TOKEN;

  if (!token) {
    logger.warn('HF_API_TOKEN not set, using template fallback');
    return templateFallback(product, trends);
  }

  const trendContext = trends.length
    ? `Trending now: ${trends.map(t => t.title).join(', ')}.`
    : '';

  const prompt = `<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You write concise, engaging affiliate marketing posts for Bluesky (max 280 chars). No hashtags spam. Be natural.
<|eot_id|><|start_header_id|>user<|end_header_id|>
${trendContext}
Write a Bluesky post for: "${product.name}" (${product.category}).
Description: ${product.description.slice(0, 150)}
Include a call-to-action. Under 200 characters. Do not include the URL (it will be appended).
<|eot_id|><|start_header_id|>assistant<|end_header_id|>`;

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(`${HF_API}/${model}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          inputs: prompt,
          parameters: {
            max_new_tokens: 80,
            temperature: 0.7,
            return_full_text: false,
            stop: ['<|eot_id|>', '\n\n'],
          },
        }),
      });

      if (res.status === 503) {
        // Model loading — wait and retry
        const j = await res.json().catch(() => ({}));
        const wait = Math.min((j.estimated_time || 20) * 1000, 30000);
        logger.warn(`HF model loading, waiting ${wait}ms (attempt ${attempt})`);
        await sleep(wait);
        continue;
      }

      if (res.status === 429) {
        logger.warn(`HF rate limited (attempt ${attempt}), backing off`);
        await sleep(attempt * 5000);
        continue;
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HF API error ${res.status}: ${text}`);
      }

      const data = await res.json();
      const generated = Array.isArray(data) ? data[0]?.generated_text : data?.generated_text;
      if (!generated) throw new Error('Empty response from HF');

      const cleaned = generated.trim().replace(/^["']|["']$/g, '');
      logger.info(`Text generated (${cleaned.length} chars): ${cleaned.slice(0, 60)}...`);
      return cleaned.slice(0, 250);
    } catch (err) {
      logger.warn(`HF text attempt ${attempt} failed: ${err.message}`);
      if (attempt === 3) break;
      await sleep(attempt * 2000);
    }
  }

  logger.warn('All HF attempts failed, using template fallback');
  return templateFallback(product, trends);
}

function templateFallback(product, trends) {
  const trend = trends[0]?.title || '';
  const base = trend
    ? `${trend} and looking for deals? Check out ${product.name}!`
    : `Discover ${product.name} — ${product.category} at a great price!`;
  return base.slice(0, 200);
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
