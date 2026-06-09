import { getAdmitadProduct } from './admitad.js';
import { getAdmitadApiProduct } from '../admitad/campaigns.js';
import { getAdmitadCatalogProduct } from './admitad-catalog.js';
import { getTemuProduct } from './temu.js';
import { getTakeadsProduct } from './takeads.js';
import { getTravelpayoutsProduct } from './travelpayouts.js';
import { getImpactProduct } from './impact.js';
import { getCJProduct } from './cj.js';
import { getShareASaleProduct } from './shareasale.js';
import { getSovrnProduct } from './sovrn.js';
import { logger } from '../utils/logger.js';
import { getLastPostedSource, getRecentPostedSources, wasAdvertiserRecentlyPosted } from '../utils/metrics.js';

export const TASKS = [
  { key: 'admitad-feed',    fn: getAdmitadProduct,         env: () => !!process.env.ADMITAD_FEED_URL },
  { key: 'admitad-api',     fn: getAdmitadApiProduct,      env: () => !!(process.env.ADMITAD_CLIENT_ID && process.env.ADMITAD_CLIENT_SECRET && process.env.ADMITAD_WEBSITE_ID) },
  { key: 'admitad-catalog', fn: getAdmitadCatalogProduct,  env: () => [1,2,3,4,5].some(n => process.env[`ADMITAD_CATALOG_URL_${n}`]) },
  { key: 'temu',            fn: getTemuProduct,            env: () => !!(process.env.TEMU_AFFILIATE_URL_1 || process.env.TEMU_AFFILIATE_URL_2) },
  { key: 'takeads',         fn: getTakeadsProduct,         env: () => !!process.env.TAKEADS_API_KEY },
  { key: 'travelpayouts',   fn: getTravelpayoutsProduct,   env: () => !!process.env.TRAVELPAYOUTS_TOKEN },
  { key: 'impact',          fn: getImpactProduct,          env: () => !!(process.env.IMPACT_ACCOUNT_SID && process.env.IMPACT_AUTH_TOKEN) },
  { key: 'cj',              fn: getCJProduct,              env: () => !!(process.env.CJ_API_KEY && process.env.CJ_WEBSITE_ID) },
  { key: 'shareasale',      fn: getShareASaleProduct,      env: () => !!(process.env.SHAREASALE_TOKEN && process.env.SHAREASALE_SECRET && process.env.SHAREASALE_AFFILIATE_ID) },
  { key: 'sovrn',           fn: getSovrnProduct,           env: () => !!process.env.SOVRN_API_KEY },
];

const CATEGORY_PATTERNS = [
  { pattern: /\b(flight|hotel|travel|airline|airport|vacation|trip|holiday|tour)\b/i, category: 'Travel' },
  { pattern: /\b(phone|laptop|tablet|earbuds|headphone|speaker|camera|smartwatch|tv|monitor|router|keyboard|mouse)\b/i, category: 'Electronics' },
  { pattern: /\b(dress|shirt|shoes|sneakers|jacket|jeans|clothing|fashion|handbag|watch|jewel|ring|necklace)\b/i, category: 'Fashion' },
  { pattern: /\b(sofa|furniture|decor|curtain|bedding|kitchen|appliance|vacuum|blender|lamp|rug)\b/i, category: 'Home' },
  { pattern: /\b(skincare|makeup|lipstick|mascara|perfume|hair|shampoo|cream|moisturizer|serum)\b/i, category: 'Beauty' },
  { pattern: /\b(vitamin|supplement|protein|fitness|yoga|gym|running|bike|treadmill|sport)\b/i, category: 'Health & Fitness' },
  { pattern: /\b(toy|game|puzzle|lego|kids|baby|stroller|diaper)\b/i, category: 'Toys & Kids' },
  { pattern: /\b(book|ebook|course|software|app|subscription)\b/i, category: 'Digital' },
  { pattern: /\b(pet|dog|cat|bird|fish|animal)\b/i, category: 'Pet Supplies' },
];

function inferCategory(name) {
  if (!name) return null;
  for (const { pattern, category } of CATEGORY_PATTERNS) {
    if (pattern.test(name)) return category;
  }
  return null;
}

// Per-network last error and selection count tracking (in-memory, reset on restart)
const networkErrors = {};
const networkSelectCounts = {};

export function getNetworkErrors() {
  return { ...networkErrors };
}

export function getNetworkSelectCounts() {
  return { ...networkSelectCounts };
}

async function collectCandidates() {
  const enabled = TASKS.filter(t => t.env());
  const results = await Promise.allSettled(
    enabled.map(t => t.fn().then(v => ({ key: t.key, value: v })))
  );

  const candidates = [];
  for (let i = 0; i < results.length; i++) {
    const r   = results[i];
    const key = enabled[i].key;
    if (r.status === 'fulfilled' && r.value?.value) {
      const product = r.value.value;
      // Skip products with very short or missing names
      if (!product.name || product.name.trim().length < 5) {
        networkErrors[key] = { error: 'product name too short', at: new Date().toISOString() };
        logger.warn(`Network ${key}: product name too short ("${product.name}") — skipping`);
        continue;
      }
      if (!product.category) product.category = inferCategory(product.name) || key;
      candidates.push(product);
      delete networkErrors[key];
      logger.info(`Network available: ${key} → "${product.name}"`);
    } else if (r.status === 'fulfilled') {
      networkErrors[key] = { error: 'returned null', at: new Date().toISOString() };
      logger.warn(`Network unavailable: ${key} returned null`);
    } else {
      networkErrors[key] = { error: r.reason?.message || 'unknown error', at: new Date().toISOString() };
      logger.warn(`Network unavailable: ${key}: ${r.reason?.message || 'unknown error'}`);
    }
  }
  return candidates;
}

function extractAdvertiserDomain(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    // Keep only the registered domain (e.g. shopify.com from partners.shopify.com)
    const parts = host.split('.');
    return parts.length >= 2 ? parts.slice(-2).join('.') : host;
  } catch { return null; }
}

function pickWithRotation(candidates, wasPosted) {
  const recentSources = getRecentPostedSources(3);
  const shuffled = candidates.sort(() => Math.random() - 0.5);
  // Move recently-used sources to the end (last used = least priority)
  const rotated = recentSources.length
    ? [...shuffled.filter(p => !recentSources.includes(p.source)), ...shuffled.filter(p => recentSources.includes(p.source))]
    : shuffled;

  if (wasPosted) {
    // Prefer products that are both not-recently-posted AND from a new advertiser domain
    const fresh = rotated.find(p => {
      if (wasPosted(p.siteUrl, p.name)) return false;
      // Skip if same advertiser domain posted in last 4 hours (prevents 4× Shopify in a row)
      if (wasAdvertiserRecentlyPosted(p.siteUrl, 4)) {
        logger.info(`Skipping ${p.name} — same advertiser domain posted recently`);
        return false;
      }
      return true;
    });
    if (fresh) {
      networkSelectCounts[fresh.source] = (networkSelectCounts[fresh.source] || 0) + 1;
      logger.info(`Selected fresh product from "${fresh.source}": ${fresh.name}`);
      return fresh;
    }
    // Fallback: at least avoid recently-posted exact match
    const anyFresh = rotated.find(p => !wasPosted(p.siteUrl, p.name));
    if (anyFresh) {
      networkSelectCounts[anyFresh.source] = (networkSelectCounts[anyFresh.source] || 0) + 1;
      logger.info(`Selected product (domain-repeat allowed) from "${anyFresh.source}": ${anyFresh.name}`);
      return anyFresh;
    }
    logger.warn('All candidate products were recently posted — picking least-recently-used anyway');
  }

  const picked = rotated[0];
  networkSelectCounts[picked.source] = (networkSelectCounts[picked.source] || 0) + 1;
  logger.info(`Selected product from "${picked.source}": ${picked.name}`);
  return picked;
}

/**
 * Collects products from all configured affiliate networks in parallel,
 * then picks one at random from the successful results, skipping any
 * that were recently posted (dedup).
 *
 * @param {Function} wasPosted - (deeplink, name) => boolean dedup check
 * @returns {Promise<Object>} A single product from one of the networks
 * @throws {Error} If no network yields a fresh product
 */
export async function getProduct(wasPosted) {
  const candidates = await collectCandidates();
  if (candidates.length === 0) {
    throw new Error('No affiliate network returned a product. Configure at least one: ADMITAD_FEED_URL, ADMITAD_CLIENT_ID+SECRET, or ADMITAD_CATALOG_URL_1.');
  }
  return pickWithRotation(candidates, wasPosted);
}
