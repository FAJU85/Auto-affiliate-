import { getAdmitadProduct } from './admitad.js';
import { getTakeadsProduct } from './takeads.js';
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
  const [admitad, takeads] = await Promise.allSettled([
    getAdmitadProduct(),
    getTakeadsProduct(),
  ]);

  const candidates = [];

  if (admitad.status === 'fulfilled' && admitad.value) {
    candidates.push(admitad.value);
    logger.info(`Network available: admitad → "${admitad.value.name}"`);
  } else {
    logger.warn(`admitad unavailable: ${admitad.reason?.message || 'returned null'}`);
  }

  if (takeads.status === 'fulfilled' && takeads.value) {
    candidates.push(takeads.value);
    logger.info(`Network available: takeads → "${takeads.value.name}"`);
  } else {
    logger.warn(`takeads unavailable: ${takeads.reason?.message || 'returned null'}`);
  }

  if (candidates.length === 0) {
    throw new Error('No affiliate network returned a product. Check ADMITAD_FEED_URL and TAKEADS_API_KEY.');
  }

  const picked = candidates[Math.floor(Math.random() * candidates.length)];
  logger.info(`Selected product from "${picked.source}": ${picked.name}`);
  return picked;
}
