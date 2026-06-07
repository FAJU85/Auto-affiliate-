import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';
import { getSettings } from '../config/settings.js';
import { dataPath } from '../utils/datadir.js';

const GROQ_API     = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODEL   = 'llama-3.3-70b-versatile';
const MISTRAL_API   = 'https://api.mistral.ai/v1/chat/completions';
const MISTRAL_MODEL = 'mistral-small-latest';
const CACHE_FILE   = dataPath('caption-cache.json');

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

// Network-specific system prompts override the default when the source matches
const SOURCE_PROMPTS = {
  travelpayouts: 'Write short travel deal posts for social media. Max 200 chars. Mention origin, destination and price. No hashtags. Excited tone.',
  temu:          'Write short deal-focused posts for social media. Max 200 chars. Emphasise value and variety. No hashtags. Friendly tone.',
  cj:            'Write short promotional posts for social media. Max 200 chars. Highlight the offer or discount. No hashtags. Persuasive tone.',
  shareasale:    'Write short deal posts for social media. Max 200 chars. Highlight product benefits and any discount. No hashtags. Friendly tone.',
  impact:        'Write short promotional posts for social media. Max 200 chars. Highlight the brand or offer. No hashtags. Confident tone.',
  takeads:       'Write short promotional posts for social media. Max 200 chars. Highlight the brand and commission value. No hashtags. Persuasive tone.',
  admitad:          'Write short deal posts for social media. Max 200 chars. Highlight the discount or product benefit. No hashtags. Friendly tone.',
  'admitad-catalog': 'Write short deal posts for social media. Max 200 chars. Highlight the discount or product benefit. No hashtags. Friendly tone.',
  'admitad-api':     'Write short deal posts for social media. Max 200 chars. Highlight the discount or product benefit. No hashtags. Friendly tone.',
};

function getSystemPrompt(product) {
  const settings = getSettings();
  return SOURCE_PROMPTS[product.source] || settings.postSystemPrompt;
}

function buildMessages(product, trends) {
  const safeName        = sanitiseForPrompt(product.name).slice(0, 80);
  const safeCategory    = sanitiseForPrompt(product.category || product.source || '').slice(0, 40);
  const safeDesc        = sanitiseForPrompt(product.description).slice(0, 80);
  const safeTrend       = trends[0] ? sanitiseForPrompt(trends[0].title) : '';
  const safeHighlights  = product.exaHighlights
    ? sanitiseForPrompt(product.exaHighlights).slice(0, 200)
    : '';

  const system       = getSystemPrompt(product);
  const userTemplate = getSettings().postUserTemplate;
  const user = userTemplate
    .replace('{name}',        safeName)
    .replace('{category}',    safeCategory)
    .replace('{description}', safeDesc)
    .replace('{trend}',       safeTrend || 'none')
    .replace('{highlights}',  safeHighlights || '');

  return { system, user };
}

// --- Generic OpenAI-compatible chat call ---

async function callChatAPI({ url, model, apiKey, system, user, name }) {
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
        logger.warn(`${name} rate limited (attempt ${attempt}), backing off`);
        await sleep(attempt * 5000);
        continue;
      }

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${name} API error ${res.status}: ${text}`);
      }

      const data = await res.json();
      const text = data?.choices?.[0]?.message?.content;
      if (!text) throw new Error(`Empty response from ${name}`);

      return text.trim().replace(/^["']|["']$/g, '').slice(0, 250);
    } catch (err) {
      logger.warn(`${name} attempt ${attempt} failed: ${err.message}`);
      if (attempt === 3) return null;
      await sleep(attempt * 2000);
    }
  }
  return null;
}

// --- Main export ---

/**
 * Generates affiliate post text.
 * Priority: cache hit → Groq llama-3.3-70b (free) → Mistral small → template
 */
export async function generatePostText(product, trends) {
  // 1. Cache hit — zero cost
  const cached = getCached(product.id);
  if (cached) {
    logger.info(`Caption cache hit for product ${product.id} (${cached.length} chars)`);
    return cached;
  }

  const { system, user } = buildMessages(product, trends);

  // Try providers in order: Groq (free) → Mistral → template
  const providers = [
    { key: process.env.GROQ_API_KEY,    url: GROQ_API,    model: GROQ_MODEL,    name: 'Groq' },
    { key: process.env.MISTRAL_API_KEY, url: MISTRAL_API, model: MISTRAL_MODEL, name: 'Mistral' },
  ];

  for (const p of providers) {
    if (!p.key) continue;
    const result = await callChatAPI({ url: p.url, model: p.model, apiKey: p.key, system, user, name: p.name });
    if (result) {
      logger.info(`${p.name} text generated (${result.length} chars): ${result.slice(0, 60)}...`);
      setCached(product.id, result);
      return result;
    }
    logger.warn(`${p.name} failed, trying next provider`);
  }

  logger.warn('All AI providers failed or unconfigured, using template fallback');
  return templateFallback(product, trends);
}

function templateFallback(product, trends) {
  const trend = trends[0]?.title || '';
  const base  = trend
    ? `${trend} and looking for deals? Check out ${product.name}!`
    : `Discover ${product.name} — ${product.category} at a great price!`;
  return base.slice(0, 200);
}
