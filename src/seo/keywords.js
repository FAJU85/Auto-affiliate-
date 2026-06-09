/**
 * SEO Keyword Research Module
 *
 * Pulls trending keywords from multiple free sources and scores
 * affiliate products against them so the most search-relevant
 * product is chosen each run.
 */

import Parser from 'rss-parser';
import { logger } from '../utils/logger.js';

const rssParser = new Parser();

// ── Keyword sources ──────────────────────────────────────────────────────────

async function fetchGoogleTrends(geo = 'US') {
  const url = `https://trends.google.com/trending/rss?geo=${geo}`;
  try {
    const feed = await rssParser.parseURL(url);
    return (feed.items || []).slice(0, 20).map(i => ({
      keyword: i.title,
      traffic: parseInt(String(i['ht:approx_traffic'] || '0').replace(/\D/g, '')) || 0,
      source: 'google-trends',
    }));
  } catch (err) {
    logger.warn(`Google Trends fetch failed: ${err.message}`);
    return [];
  }
}

async function fetchBingTrends() {
  try {
    const res = await (await import('node-fetch')).default(
      'https://trends.bing.com/api/insights?mkt=en-US&timeSpan=Day&top=20',
      { headers: { 'Accept': 'application/json' }, signal: AbortSignal.timeout(8000) }
    );
    if (!res.ok) return [];
    const json = await res.json();
    const items = json?.result?.query || json?.searches || [];
    return items.slice(0, 20).map(q => ({
      keyword: q.query || q.title || String(q),
      traffic: q.searchesCount || 0,
      source: 'bing-trends',
    }));
  } catch {
    return [];
  }
}

// ── Keyword scoring ──────────────────────────────────────────────────────────

const CATEGORY_KEYWORDS = {
  Electronics:      ['tech', 'gadget', 'smart', 'wireless', 'bluetooth', 'phone', 'laptop', 'earbuds', 'camera'],
  Fashion:          ['style', 'wear', 'outfit', 'dress', 'shoes', 'fashion', 'clothing', 'trend'],
  'Home & Garden':  ['home', 'decor', 'kitchen', 'garden', 'furniture', 'interior', 'living'],
  'Health & Fitness':['fitness', 'health', 'workout', 'gym', 'diet', 'wellness', 'vitamin', 'supplement'],
  Beauty:           ['beauty', 'skincare', 'makeup', 'cosmetic', 'glow', 'hair', 'perfume'],
  Travel:           ['travel', 'flight', 'hotel', 'vacation', 'trip', 'destination', 'tour'],
  'Toys & Kids':    ['kids', 'toy', 'children', 'baby', 'game', 'play'],
  Digital:          ['software', 'app', 'online', 'subscription', 'digital', 'course'],
};

/**
 * Scores a product against a list of trending keywords.
 * Returns a 0-100 score and the matched keywords.
 */
export function scoreProductKeywords(product, keywords) {
  const text = `${product.name} ${product.description || ''} ${product.category || ''}`.toLowerCase();
  let score = 0;
  const matched = [];

  for (const kw of keywords) {
    const kwLower = kw.keyword.toLowerCase();
    const kwWords = kwLower.split(/\s+/);
    const hit = kwWords.some(w => w.length > 3 && text.includes(w));
    if (hit) {
      const boost = Math.log10(Math.max(kw.traffic, 10));
      score += boost;
      matched.push({ keyword: kw.keyword, traffic: kw.traffic, source: kw.source });
    }
  }

  // Bonus for category-keyword alignment
  const catKeys = CATEGORY_KEYWORDS[product.category] || [];
  for (const ck of catKeys) {
    if (text.includes(ck)) score += 0.5;
  }

  return {
    score: Math.min(Math.round(score * 10), 100),
    matched: matched.slice(0, 5),
  };
}

/**
 * Returns top-N keywords from Google Trends + Bing Trends, deduplicated.
 */
// Static fallback keywords used when both live trend sources fail
const STATIC_FALLBACK_KEYWORDS = [
  'best deals', 'sale', 'discount', 'free shipping', 'limited offer',
  'new arrivals', 'top rated', 'must have', 'affordable', 'buy now',
  'fashion', 'tech', 'beauty', 'home decor', 'fitness', 'travel deals',
  'electronics', 'skincare', 'shoes', 'accessories', 'gadgets',
  'workout gear', 'kitchen essentials', 'gift ideas', 'back to school',
].map(keyword => ({ keyword, traffic: 1000, source: 'static-fallback' }));

export async function getTrendingKeywords(limit = 30) {
  const [google, bing] = await Promise.all([
    fetchGoogleTrends(process.env.TRENDS_GEO || 'US'),
    fetchBingTrends(),
  ]);

  const all = [...google, ...bing];
  // Deduplicate by normalized keyword
  const seen = new Set();
  const unique = all.filter(k => {
    const norm = k.keyword.toLowerCase().replace(/\s+/g, ' ').trim();
    if (seen.has(norm)) return false;
    seen.add(norm);
    return true;
  });

  // Sort by traffic descending
  unique.sort((a, b) => b.traffic - a.traffic);

  if (unique.length === 0) {
    logger.warn('SEO: no live trending keywords — using static fallback list');
    return STATIC_FALLBACK_KEYWORDS.slice(0, limit);
  }

  logger.info(`SEO keywords: ${unique.slice(0, 5).map(k => k.keyword).join(', ')} (+${Math.max(unique.length - 5, 0)} more)`);
  return unique.slice(0, limit);
}

/**
 * Picks the best product from candidates by SEO keyword relevance.
 * Falls back to random if no product scores.
 */
export function pickBestProduct(candidates, keywords) {
  if (!keywords.length) return candidates[Math.floor(Math.random() * candidates.length)];

  const scored = candidates.map(p => {
    const { score, matched } = scoreProductKeywords(p, keywords);
    return { product: p, score, matched };
  }).sort((a, b) => b.score - a.score);

  const best = scored[0];
  if (best.score > 0) {
    logger.info(`SEO: best product "${best.product.name}" score=${best.score} matched=[${best.matched.map(m => m.keyword).join(', ')}]`);
    return { product: best.product, seoScore: best.score, seoKeywords: best.matched };
  }

  // No keyword match — return random
  const fallback = candidates[Math.floor(Math.random() * candidates.length)];
  logger.info(`SEO: no keyword match, random pick "${fallback.name}"`);
  return { product: fallback, seoScore: 0, seoKeywords: [] };
}

/**
 * Selects the best hashtags for a post from trending keywords + product category.
 * Returns max 5 hashtags.
 */
export function selectHashtags(product, keywords, maxTags = 5) {
  const category = product.category || '';
  const catTags = CATEGORY_KEYWORDS[category] || [];

  // Take top matched trending keywords as hashtags
  const trendTags = keywords
    .filter(k => {
      const kw = k.keyword.toLowerCase();
      const text = `${product.name} ${product.description || ''}`.toLowerCase();
      return kw.split(/\s+/).some(w => w.length > 3 && text.includes(w));
    })
    .slice(0, 3)
    .map(k => k.keyword.replace(/\s+/g, '').replace(/[^a-zA-Z0-9]/g, ''));

  // Category tags
  const catHashtags = catTags.slice(0, 2).map(t => t.charAt(0).toUpperCase() + t.slice(1));

  // Combine, deduplicate, limit
  const all = [...new Set([...trendTags, ...catHashtags, 'deals', 'sale'])];
  return all.slice(0, maxTags).map(t => `#${t}`);
}
