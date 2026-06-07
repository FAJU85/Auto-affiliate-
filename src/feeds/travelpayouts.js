import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://api.travelpayouts.com';
const ORIGINS  = ['NYC', 'LON', 'PAR', 'DXB', 'SIN', 'LAX', 'BKK', 'IST', 'SYD', 'TYO', 'GRU', 'JNB', 'CDG', 'AMS', 'FCO', 'MEX'];

async function fetchDeals(token, origin) {
  const res = await fetch(
    `${API_BASE}/v2/prices/latest?currency=usd&origin=${origin}&limit=10&show_to_affiliates=true&sorting=price&period_type=year`,
    { headers: { 'X-Access-Token': token, Accept: 'application/json' }, signal: AbortSignal.timeout(20_000) }
  );
  if (!res.ok) {
    const text = await res.text();
    logger.warn(`Travelpayouts API error ${res.status}: ${text.slice(0, 200)}`);
    return [];
  }
  const data = await res.json();
  return data.data || [];
}

function buildProduct(deal, origin, marker) {
  const { destination, value: price, airline = '', depart_date: departs = '' } = deal;
  if (!destination) return null;
  // General route search — always shows results; date-specific URLs redirect to homepage
  const siteUrl = `https://www.aviasales.com/${origin}-${destination}/?marker=${marker}`;
  logger.info(`Travelpayouts deal: ${origin}→${destination} $${price} (${airline})`);
  return {
    id:             `tp-${origin}-${destination}-${new Date().toISOString().slice(0, 10)}`,
    name:           `Flight ${origin} → ${destination}${airline ? ` (${airline})` : ''}`,
    description:    `From $${price}. Fly ${origin} to ${destination}${departs ? ` departing ${departs}` : ''}.`,
    siteUrl,
    imageUrl:       null,
    price:          parseFloat(price) || null,
    currency:       'USD',
    commissionRate: 0,
    category:       'Travel',
    source:         'travelpayouts',
  };
}

export async function getTravelpayoutsProduct() {
  const token  = process.env.TRAVELPAYOUTS_TOKEN;
  // TRAVELPAYOUTS_MARKER is the partner marker number from the dashboard.
  // Different from the API token — falls back to token if not set (links may not track).
  const marker = process.env.TRAVELPAYOUTS_MARKER || token;
  if (!token) return null;

  logger.info('Fetching Travelpayouts flight deals…');
  try {
    const origin = ORIGINS[Math.floor(Math.random() * ORIGINS.length)];
    const deals  = await fetchDeals(token, origin);
    logger.info(`Travelpayouts: ${deals.length} deals from ${origin}`);
    if (deals.length === 0) return null;

    const picked = deals[Math.floor(Math.random() * Math.min(5, deals.length))];
    return buildProduct(picked, origin, marker);
  } catch (err) {
    logger.warn(`Travelpayouts fetch failed: ${err.message}`);
    return null;
  }
}
