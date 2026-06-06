import { getAdmitadProduct } from './admitad.js';
import { getTakeadsProduct } from './takeads.js';
import { getAdmitadApiProduct } from '../admitad/campaigns.js';
import { getTravelpayoutsProduct } from './travelpayouts.js';
import { getAdmitadCatalogProduct } from './admitad-catalog.js';
import { logger } from '../utils/logger.js';

/**
 * Collects one product from each configured affiliate network in parallel,
 * then picks one at random from the successful results.
 *
 * Unified product interface:
 *   { id, name, description, siteUrl, imageUrl, price, currency, commissionRate, source }
 *
 * @returns {Promise<Object>} A single product from one of the networks
 * @throws {Error} If no network yields a product
 */
export async function getProduct() {
  const tasks = [
    { key: 'admitad-feed',    fn: getAdmitadProduct,         enabled: !!process.env.ADMITAD_FEED_URL },
    { key: 'admitad-api',     fn: getAdmitadApiProduct,      enabled: !!(process.env.ADMITAD_CLIENT_ID && process.env.ADMITAD_CLIENT_SECRET) },
    { key: 'admitad-catalog', fn: getAdmitadCatalogProduct,  enabled: !!(process.env.ADMITAD_CATALOG_URL_1 || process.env.ADMITAD_CATALOG_URL_2) },
    { key: 'takeads',         fn: getTakeadsProduct,         enabled: !!process.env.TAKEADS_API_KEY },
    { key: 'travelpayouts',   fn: getTravelpayoutsProduct,   enabled: !!process.env.TRAVELPAYOUTS_TOKEN },
  ];

  const results = await Promise.allSettled(
    tasks.filter(t => t.enabled).map(t => t.fn().then(v => ({ key: t.key, value: v })))
  );

  const candidates = [];
  for (const r of results) {
    if (r.status === 'fulfilled' && r.value?.value) {
      candidates.push(r.value.value);
      logger.info(`Network available: ${r.value.key} → "${r.value.value.name}"`);
    } else {
      logger.warn(`Network unavailable: ${r.reason?.message || 'returned null'}`);
    }
  }

  if (candidates.length === 0) {
    throw new Error('No affiliate network returned a product. Configure at least one: ADMITAD_FEED_URL, ADMITAD_CLIENT_ID+SECRET, TAKEADS_API_KEY, or TRAVELPAYOUTS_TOKEN.');
  }

  const picked = candidates[Math.floor(Math.random() * candidates.length)];
  logger.info(`Selected product from "${picked.source}": ${picked.name}`);
  return picked;
}
