import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const TAKEADS_API_BASE = 'https://api.takeads.com';

/**
 * Fetches a product from Takeads CPC network.
 * Returns null if TAKEADS_API_KEY is not set or if the request fails.
 *
 * @returns {Promise<Object|null>} Normalized product or null if unavailable
 */
export async function getTakeadsProduct() {
  const apiKey = process.env.TAKEADS_API_KEY;
  if (!apiKey) {
    logger.warn('TAKEADS_API_KEY not set — skipping Takeads');
    return null;
  }

  logger.info('Fetching Takeads product…');
  try {
    const res = await fetch(`${TAKEADS_API_BASE}/v1/offers?limit=50&sort=-commission`, {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        Accept: 'application/json',
      },
      signal: AbortSignal.timeout(30_000),
    });

    if (!res.ok) {
      const text = await res.text();
      logger.warn(`Takeads API error ${res.status}: ${text.slice(0, 200)}`);
      return null;
    }

    const data = await res.json();
    const offers = data.data || data.offers || data.results || [];
    logger.info(`Takeads: fetched ${offers.length} offers`);

    if (offers.length === 0) return null;

    // Sort by commission descending, top 5, pick random
    offers.sort((a, b) => parseFloat(b.commission || b.commissionRate || 0) - parseFloat(a.commission || a.commissionRate || 0));
    const top5 = offers.slice(0, 5);
    const picked = top5[Math.floor(Math.random() * top5.length)];

    return normalizeOffer(picked);
  } catch (err) {
    logger.error(`Takeads fetch failed: ${err.message}`);
    return null;
  }
}

function normalizeOffer(o) {
  return {
    id: String(o.id || o.offerId || ''),
    name: String(o.name || o.title || 'Unknown Product').trim(),
    description: String(o.description || o.name || '').trim(),
    siteUrl: String(o.trackingUrl || o.affiliateUrl || o.url || ''),
    imageUrl: o.imageUrl || o.image || o.logoUrl || null,
    price: parseFloat(o.price || 0),
    currency: String(o.currency || 'USD'),
    commissionRate: parseFloat(o.commission || o.commissionRate || 0),
    source: 'takeads',
  };
}
