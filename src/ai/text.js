import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

// Groq: free tier, 14,400 req/day, no cold starts, OpenAI-compatible
// DeepSeek: paid fallback (~$0.0005/call) when Groq unavailable
const GROQ_API    = 'https://api.groq.com/openai/v1/chat/completions';
const DEEPSEEK_API = 'https://api.deepseek.com/v1/chat/completions';
const CACHE_FILE  = path.resolve('data/caption-cache.json');

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

// --- Shared prompt builders ---

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

// --- Generic OpenAI-compatible chat call with retry ---

async function callChatAPI({ url, apiKey, model, system, user, providerName }) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(url, {
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
        logger.warn(`${providerName} rate limited (attempt ${attempt}), backing off`);
        await sleep(attempt * 5000);
        continue;
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${providerName} API error ${res.status}: ${text}`);
      }

      const data  = await res.json();
      const text  = data?.choices?.[0]?.message?.content;
      if (!text) throw new Error(`Empty response from ${providerName}`);

      return text.trim().replace(/^["']|["']$/g, '').slice(0, 250);
    } catch (err) {
      logger.warn(`${providerName} attempt ${attempt} failed: ${err.message}`);
      if (attempt === 3) return null;
      await sleep(attempt * 2000);
    }
  }
  return null;
}

// --- Main export ---

/**
 * Generates affiliate post text.
 * Priority: cache hit (free) → Groq/Llama-3.3-70B (free) → DeepSeek (paid fallback) → template
 */
export async function generatePostText(product, trends) {
  // 1. Cache hit — zero cost
  const cached = getCached(product.id);
  if (cached) {
    logger.info(`Caption cache hit for product ${product.id} (${cached.length} chars)`);
    return cached;
  }

  const { system, user } = buildMessages(product, trends);

  // 2. Groq — free, 70B quality, no cold starts
  const groqKey = process.env.GROQ_API_KEY;
  if (groqKey) {
    const result = await callChatAPI({
      url: GROQ_API,
      apiKey: groqKey,
      model: 'llama-3.3-70b-versatile',
      system, user,
      providerName: 'Groq',
    });
    if (result) {
      logger.info(`Groq text generated (${result.length} chars): ${result.slice(0, 60)}...`);
      setCached(product.id, result);
      return result;
    }
    logger.warn('Groq failed, falling back to DeepSeek');
  }

  // 3. DeepSeek — paid fallback (~$0.0002/call with optimised tokens)
  const deepseekKey = process.env.DEEPSEEK_API_KEY;
  if (deepseekKey) {
    const result = await callChatAPI({
      url: DEEPSEEK_API,
      apiKey: deepseekKey,
      model: 'deepseek-chat',
      system, user,
      providerName: 'DeepSeek',
    });
    if (result) {
      logger.info(`DeepSeek text generated (${result.length} chars): ${result.slice(0, 60)}...`);
      setCached(product.id, result);
      return result;
    }
    logger.warn('DeepSeek failed, falling back to template');
  }

  // 4. Template — always free, always works
  if (!groqKey && !deepseekKey) {
    logger.warn('No GROQ_API_KEY or DEEPSEEK_API_KEY set, using template fallback');
  }
  return templateFallback(product, trends);
}

function templateFallback(product, trends) {
  const trend = trends[0]?.title || '';
  const base  = trend
    ? `${trend} and looking for deals? Check out ${product.name}!`
    : `Discover ${product.name} — ${product.category} at a great price!`;
  return base.slice(0, 200);
}
