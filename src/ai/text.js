import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

const DEEPSEEK_API = 'https://api.deepseek.com/v1/chat/completions';

// Strip special tokens and control characters from untrusted external data
function sanitiseForPrompt(str) {
  return str
    .replace(/<\|[^|>]*\|>/g, '')   // strip <|...|> tokens
    .replace(/[\x00-\x1F\x7F]/g, ' ') // strip control chars
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Generates affiliate post text via DeepSeek Chat API.
 * Falls back to a template string if the API fails or key is missing.
 */
export async function generatePostText(product, trends) {
  const apiKey = process.env.DEEPSEEK_API_KEY;

  if (!apiKey) {
    logger.warn('DEEPSEEK_API_KEY not set, using template fallback');
    return templateFallback(product, trends);
  }

  const safeName = sanitiseForPrompt(product.name).slice(0, 80);
  const safeCategory = sanitiseForPrompt(product.category).slice(0, 40);
  const safeDesc = sanitiseForPrompt(product.description).slice(0, 150);
  const safeTrends = trends.map(t => sanitiseForPrompt(t.title)).filter(Boolean);

  const trendContext = safeTrends.length
    ? `Trending now: ${safeTrends.join(', ')}.`
    : '';

  const systemPrompt = 'You write concise, engaging affiliate marketing posts for Bluesky (max 280 chars). No hashtag spam. Be natural.';
  const userPrompt = `${trendContext}\nWrite a Bluesky post for: "${safeName}" (${safeCategory}).\nDescription: ${safeDesc}\nInclude a call-to-action. Under 200 characters. Do not include the URL (it will be appended).`;

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(DEEPSEEK_API, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'deepseek-chat',
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt },
          ],
          max_tokens: 100,
          temperature: 0.8,
        }),
      });

      if (res.status === 429) {
        logger.warn(`DeepSeek rate limited (attempt ${attempt}), backing off`);
        await sleep(attempt * 5000);
        continue;
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`DeepSeek API error ${res.status}: ${text}`);
      }

      const data = await res.json();
      const generated = data?.choices?.[0]?.message?.content;
      if (!generated) throw new Error('Empty response from DeepSeek');

      const cleaned = generated.trim().replace(/^["']|["']$/g, '');
      logger.info(`Text generated (${cleaned.length} chars): ${cleaned.slice(0, 60)}...`);
      return cleaned.slice(0, 250);
    } catch (err) {
      logger.warn(`DeepSeek text attempt ${attempt} failed: ${err.message}`);
      if (attempt === 3) break;
      await sleep(attempt * 2000);
    }
  }

  logger.warn('All DeepSeek attempts failed, using template fallback');
  return templateFallback(product, trends);
}

function templateFallback(product, trends) {
  const trend = trends[0]?.title || '';
  const base = trend
    ? `${trend} and looking for deals? Check out ${product.name}!`
    : `Discover ${product.name} — ${product.category} at a great price!`;
  return base.slice(0, 200);
}
