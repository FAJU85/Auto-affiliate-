import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://api.travelpayouts.com';

// Popular origin cities to rotate through for variety
const ORIGINS = ['NYC', 'LON', 'PAR', 'DXB', 'SIN', 'LAX', 'BKK', 'IST'];

export async function getTravelpayoutsProduct() {
  const token = process.env.TRAVELPAYOUTS_TOKEN;
  if (!token) return null;

  logger.info('Fetching Travelpayouts flight deals…');
  try {
    const origin = ORIGINS[Math.floor(Math.random() * ORIGINS.length)];

    const res = await fetch(
      `${API_BASE}/v2/prices/latest?currency=usd&origin=${origin}&limit=10&show_to_affiliates=true&sorting=price&period_type=year`,
      {
        headers: { 'X-Access-Token': token, Accept: 'application/json' },
        signal: AbortSignal.timeout(20_000),
      }
    );

    if (!res.ok) {
      const text = await res.text();
      logger.warn(`Travelpayouts API error ${res.status}: ${text.slice(0, 200)}`);
      return null;
    }

    const data = await res.json();
    const deals = data.data || [];
    logger.info(`Travelpayouts: ${deals.length} deals from ${origin}`);
    if (deals.length === 0) return null;

    // Pick the deal with best value (lowest price, highest popularity)
    const picked = deals[Math.floor(Math.random() * Math.min(5, deals.length))];

    const destination = picked.destination;
    const price       = picked.value;
    const airline     = picked.airline || '';
    const departs     = picked.depart_date || '';

    // Build affiliate link — aviasales needs full YYYYMMDD date
    const dateStr = departs.replace(/-/g, ''); // "2026-07-15" → "20260715"
    const affiliateUrl = `https://www.aviasales.com/search/${origin}${dateStr}${destination}1?marker=${token}`;

    logger.info(`Travelpayouts deal: ${origin}→${destination} $${price} (${airline})`);

    return {
      id:             `tp-${origin}-${destination}-${departs}`,
      name:           `Flight ${origin} → ${destination}${airline ? ` (${airline})` : ''}`,
      description:    `From $${price}. Fly ${origin} to ${destination}${departs ? ` departing ${departs}` : ''}.`,
      siteUrl:        affiliateUrl,
      imageUrl:       null,
      price:          parseFloat(price) || null,
      currency:       'USD',
      commissionRate: 0,
      category:       'Travel',
      source:         'travelpayouts',
    };
  } catch (err) {
    logger.warn(`Travelpayouts fetch failed: ${err.message}`);
    return null;
  }
}
