import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

const DEEPSEEK_API = 'https://api.deepseek.com/v1/chat/completions';
const CACHE_FILE = path.resolve('data/caption-cache.json');

// Strip special tokens and control characters from untrusted external data
function sanitiseForPrompt(str) {
  return str
    .replace(/<\|[^|>]*\|>/g, '')
    .replace(/[\x00-\x1F\x7F]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// --- Caption cache (keyed by productId + UTC date) ---

function cacheKey(productId) {
  const date = new Date().toISOString().slice(0, 10);
  return `${productId}:${date}`;
}

function readCache() {
  try {
    return JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
  } catch {
    return {};
  }
}

function writeCache(data) {
  fs.mkdirSync(path.dirname(CACHE_FILE), { recursive: true });
  const tmp = `${CACHE_FILE}.tmp`;
  // Prune entries older than today to keep file small
  const today = new Date().toISOString().slice(0, 10);
  const pruned = Object.fromEntries(
    Object.entries(data).filter(([k]) => k.endsWith(today))
  );
  fs.writeFileSync(tmp, JSON.stringify(pruned, null, 2));
  fs.renameSync(tmp, CACHE_FILE);
}

function getCached(productId) {
  const cache = readCache();
  return cache[cacheKey(productId)] ?? null;
}

function setCached(productId, caption) {
  const cache = readCache();
  cache[cacheKey(productId)] = caption;
  writeCache(cache);
}

// --- Text generation ---

/**
 * Generates affiliate post text via DeepSeek Chat API.
 * Caches result by product ID + date to avoid duplicate API calls.
 * Falls back to template if API key missing or all attempts fail.
 */
export async function generatePostText(product, trends) {
  // Cache hit — free
  const cached = getCached(product.id);
  if (cached) {
    logger.info(`Caption cache hit for product ${product.id} (${cached.length} chars)`);
    return cached;
  }

  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) {
    logger.warn('DEEPSEEK_API_KEY not set, using template fallback');
    return templateFallback(product, trends);
  }

  const safeName = sanitiseForPrompt(product.name).slice(0, 80);
  const safeCategory = sanitiseForPrompt(product.category).slice(0, 40);
  const safeDesc = sanitiseForPrompt(product.description).slice(0, 80); // trimmed 150→80
  const safeTrend = trends[0] ? sanitiseForPrompt(trends[0].title) : '';

  const systemPrompt = 'Write short affiliate posts for Bluesky. Max 200 chars. No hashtags. Natural tone.';
  const userPrompt = safeTrend
    ? `Trending: ${safeTrend}. Product: "${safeName}" (${safeCategory}). ${safeDesc}. CTA, no URL.`
    : `Product: "${safeName}" (${safeCategory}). ${safeDesc}. Write a post with CTA, no URL.`;

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
          max_tokens: 60,
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

      const cleaned = generated.trim().replace(/^["']|["']$/g, '').slice(0, 250);
      logger.info(`Text generated (${cleaned.length} chars): ${cleaned.slice(0, 60)}...`);
      setCached(product.id, cleaned);
      return cleaned;
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
