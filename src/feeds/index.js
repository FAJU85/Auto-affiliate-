import { getAdmitadProduct } from './admitad.js';
import { getAdmitadApiProduct } from '../admitad/campaigns.js';
import { getAdmitadCatalogProduct } from './admitad-catalog.js';
import { getTemuProduct } from './temu.js';
import { getTakeadsProduct } from './takeads.js';
import { getTravelpayoutsProduct } from './travelpayouts.js';
import { getImpactProduct } from './impact.js';
import { getCJProduct } from './cj.js';
import { getShareASaleProduct } from './shareasale.js';
import { logger } from '../utils/logger.js';
import { getLastPostedSource, getRecentPostedSources } from '../utils/metrics.js';

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
];

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
      if (!product.category) product.category = key;
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

function pickWithRotation(candidates, wasPosted) {
  const recentSources = getRecentPostedSources(3);
  const shuffled = candidates.sort(() => Math.random() - 0.5);
  // Move recently-used sources to the end (last used = least priority)
  const rotated = recentSources.length
    ? [...shuffled.filter(p => !recentSources.includes(p.source)), ...shuffled.filter(p => recentSources.includes(p.source))]
    : shuffled;

  if (wasPosted) {
    const fresh = rotated.find(p => !wasPosted(p.siteUrl, p.name));
    if (fresh) {
      networkSelectCounts[fresh.source] = (networkSelectCounts[fresh.source] || 0) + 1;
      logger.info(`Selected fresh product from "${fresh.source}": ${fresh.name}`);
      return fresh;
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
