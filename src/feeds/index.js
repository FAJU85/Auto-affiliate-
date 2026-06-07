import { getAdmitadProduct } from './admitad.js';
import { getAdmitadApiProduct } from '../admitad/campaigns.js';
import { getAdmitadCatalogProduct } from './admitad-catalog.js';
import { getTemuProduct } from './temu.js';
import { logger } from '../utils/logger.js';

/**
 * Collects products from all configured affiliate networks in parallel,
 * then picks one at random from the successful results, skipping any
 * that were recently posted (dedup).
 *
 * Unified product interface:
 *   { id, name, description, siteUrl, imageUrl, price, currency, commissionRate, source }
 *
 * @param {Function} wasPosted - (deeplink, name) => boolean dedup check
 * @returns {Promise<Object>} A single product from one of the networks
 * @throws {Error} If no network yields a fresh product
 */
export async function getProduct(wasPosted) {
  const tasks = [
    { key: 'admitad-feed',    fn: getAdmitadProduct,         enabled: !!process.env.ADMITAD_FEED_URL },
    { key: 'admitad-api',     fn: getAdmitadApiProduct,      enabled: !!(process.env.ADMITAD_CLIENT_ID && process.env.ADMITAD_CLIENT_SECRET && process.env.ADMITAD_WEBSITE_ID) },
    { key: 'admitad-catalog', fn: getAdmitadCatalogProduct,  enabled: [1,2,3,4,5].some(n => process.env[`ADMITAD_CATALOG_URL_${n}`]) },
    { key: 'temu',            fn: getTemuProduct,            enabled: !!(process.env.TEMU_AFFILIATE_URL_1 || process.env.TEMU_AFFILIATE_URL_2) },
  ];

  const results = await Promise.allSettled(
    tasks.filter(t => t.enabled).map(t => t.fn().then(v => ({ key: t.key, value: v })))
  );

  const candidates = [];
  for (const r of results) {
    if (r.status === 'fulfilled' && r.value?.value) {
      candidates.push(r.value.value);
      logger.info(`Network available: ${r.value.key} → "${r.value.value.name}"`);
    } else if (r.status === 'fulfilled') {
      logger.warn(`Network unavailable: ${r.value?.key || 'unknown'} returned null`);
    } else {
      logger.warn(`Network unavailable: ${r.reason?.message || 'unknown error'}`);
    }
  }

  if (candidates.length === 0) {
    throw new Error('No affiliate network returned a product. Configure at least one: ADMITAD_FEED_URL, ADMITAD_CLIENT_ID+SECRET, or ADMITAD_CATALOG_URL_1.');
  }

  // Shuffle candidates then pick the first one not recently posted
  const shuffled = candidates.sort(() => Math.random() - 0.5);
  if (wasPosted) {
    const fresh = shuffled.find(p => !wasPosted(p.siteUrl, p.name));
    if (fresh) {
      logger.info(`Selected fresh product from "${fresh.source}": ${fresh.name}`);
      return fresh;
    }
    logger.warn('All candidate products were recently posted — picking least-recently-used anyway');
  }

  const picked = shuffled[0];
  logger.info(`Selected product from "${picked.source}": ${picked.name}`);
  return picked;
}
