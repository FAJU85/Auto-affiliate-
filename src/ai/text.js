import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

// HuggingFace free Inference API — OpenAI-compatible chat endpoint
const HF_API_BASE = 'https://api-inference.huggingface.co/v1/chat/completions';
const HF_PRIMARY   = 'Qwen/Qwen2.5-72B-Instruct';
const HF_FALLBACK  = 'mistralai/Mistral-7B-Instruct-v0.3';
const CACHE_FILE   = path.resolve('data/caption-cache.json');

function sanitiseForPrompt(str) {
  return String(str ?? '')
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
  try { return JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8')); }
  catch { return {}; }
}

function writeCache(data) {
  fs.mkdirSync(path.dirname(CACHE_FILE), { recursive: true });
  const today = new Date().toISOString().slice(0, 10);
  const pruned = Object.fromEntries(
    Object.entries(data).filter(([k]) => k.endsWith(today))
  );
  const tmp = `${CACHE_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(pruned, null, 2));
  fs.renameSync(tmp, CACHE_FILE);
}

function getCached(productId) {
  return readCache()[cacheKey(productId)] ?? null;
}

function setCached(productId, caption) {
  const cache = readCache();
  cache[cacheKey(productId)] = caption;
  writeCache(cache);
}

// --- Prompt builder ---

function buildMessages(product, trends) {
  const safeName     = sanitiseForPrompt(product.name).slice(0, 80);
  const safeCategory = sanitiseForPrompt(product.category).slice(0, 40);
  const safeDesc     = sanitiseForPrompt(product.description).slice(0, 80);
  const safeTrend    = trends[0] ? sanitiseForPrompt(trends[0].title) : '';

  const system = 'Write short affiliate posts for Bluesky. Max 200 chars. No hashtags. Natural tone.';
  const user   = safeTrend
    ? `Trending: ${safeTrend}. Product: "${safeName}" (${safeCategory}). ${safeDesc}. CTA, no URL.`
    : `Product: "${safeName}" (${safeCategory}). ${safeDesc}. Write a post with CTA, no URL.`;

  return { system, user };
}

// --- HuggingFace chat call with retry ---

async function callHfModel(model, system, user, apiKey) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(HF_API_BASE, {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
          max_tokens: 60,
          temperature: 0.8,
        }),
      });

      if (res.status === 429) {
        logger.warn(`HF (${model}) rate limited (attempt ${attempt}), backing off`);
        await sleep(attempt * 5000);
        continue;
      }

      if (res.status === 503) {
        logger.warn(`HF (${model}) loading (attempt ${attempt}), retrying`);
        await sleep(attempt * 10000);
        continue;
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HF API error ${res.status}: ${text}`);
      }

      const data = await res.json();
      const text = data?.choices?.[0]?.message?.content;
      if (!text) throw new Error(`Empty response from HF (${model})`);

      return text.trim().replace(/^["']|["']$/g, '').slice(0, 250);
    } catch (err) {
      logger.warn(`HF (${model}) attempt ${attempt} failed: ${err.message}`);
      if (attempt === 3) return null;
      await sleep(attempt * 2000);
    }
  }
  return null;
}

// --- Main export ---

/**
 * Generates affiliate post text.
 * Priority: cache hit → HF Qwen2.5-72B (free) → HF Mistral-7B (free) → template
 */
export async function generatePostText(product, trends) {
  // 1. Cache hit — zero cost
  const cached = getCached(product.id);
  if (cached) {
    logger.info(`Caption cache hit for product ${product.id} (${cached.length} chars)`);
    return cached;
  }

  const { system, user } = buildMessages(product, trends);
  const hfKey = process.env.HF_API_TOKEN;

  if (hfKey) {
    // 2. Qwen2.5-72B — high quality, free tier
    const primary = await callHfModel(HF_PRIMARY, system, user, hfKey);
    if (primary) {
      logger.info(`HF Qwen2.5-72B text generated (${primary.length} chars): ${primary.slice(0, 60)}...`);
      setCached(product.id, primary);
      return primary;
    }
    logger.warn('Qwen2.5-72B failed, trying Mistral-7B fallback');

    // 3. Mistral-7B — lighter model, free tier
    const fallback = await callHfModel(HF_FALLBACK, system, user, hfKey);
    if (fallback) {
      logger.info(`HF Mistral-7B text generated (${fallback.length} chars): ${fallback.slice(0, 60)}...`);
      setCached(product.id, fallback);
      return fallback;
    }
    logger.warn('Mistral-7B failed, falling back to template');
  } else {
    logger.warn('HF_API_TOKEN not set, using template fallback');
  }

  // 4. Template — always works
  return templateFallback(product, trends);
}

function templateFallback(product, trends) {
  const trend = trends[0]?.title || '';
  const base  = trend
    ? `${trend} and looking for deals? Check out ${product.name}!`
    : `Discover ${product.name} — ${product.category} at a great price!`;
  return base.slice(0, 200);
}
