import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

/**
 * Fetches the Admitad XML product feed and returns a random top product
 * sorted by commissionRate (descending). No OAuth required — the feed URL
 * already contains all auth parameters and the <url> is a pre-built deeplink.
 *
 * @returns {Promise<Object|null>} Normalized product or null if unavailable
 */
export async function getAdmitadProduct() {
  const feedUrl = process.env.ADMITAD_FEED_URL;
  if (!feedUrl) {
    logger.warn('ADMITAD_FEED_URL not set — skipping Admitad feed');
    return null;
  }

  logger.info('Fetching Admitad XML feed…');
  let xml;
  try {
    const controller = new AbortController();
    // 30s total budget — abort early once we have enough data
    const timeout = setTimeout(() => controller.abort(), 30_000);
    try {
      const res = await fetch(feedUrl, { signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      // Stream body, stop after 2MB — enough to parse hundreds of offers
      const MAX_BYTES = 2 * 1024 * 1024;
      const chunks = [];
      let total = 0;
      for await (const chunk of res.body) {
        chunks.push(chunk);
        total += chunk.length;
        if (total >= MAX_BYTES) { controller.abort(); break; }
      }
      xml = Buffer.concat(chunks).toString('utf8');
    } finally {
      clearTimeout(timeout);
    }
  } catch (err) {
    if (err.name !== 'AbortError' || !xml) {
      logger.error(`Admitad feed fetch failed: ${err.message}`);
      return null;
    }
    // AbortError after we intentionally stopped streaming — xml is populated, continue
  }

  const offers = parseOffers(xml);
  logger.info(`Admitad: parsed ${offers.length} offers`);

  if (offers.length === 0) return null;

  // Sort by commissionRate descending, take top 5, pick one at random
  offers.sort((a, b) => b.commissionRate - a.commissionRate);
  const top5 = offers.slice(0, 5);
  const picked = top5[Math.floor(Math.random() * top5.length)];
  logger.info(`Admitad selected: "${picked.name}" (commission ${picked.commissionRate}%)`);
  return picked;
}

/**
 * Parses YML/XML catalog format. Each <offer> element is extracted with
 * lightweight regex — no XML parser dependency needed.
 */
function parseOffers(xml) {
  const offers = [];
  // Match each <offer ...>...</offer> block (non-greedy, dotall)
  const offerRegex = /<offer\s[^>]*id="([^"]*)"[^>]*>([\s\S]*?)<\/offer>/g;
  let match;
  while ((match = offerRegex.exec(xml)) !== null) {
    const id = match[1];
    const body = match[2];
    try {
      const offer = parseOfferBlock(id, body);
      if (offer) offers.push(offer);
    } catch {
      // Skip malformed offers
    }
  }
  return offers;
}

function parseOfferBlock(id, body) {
  const name = extractTag(body, 'name');
  const url = extractTag(body, 'url');
  const price = parseFloat(extractTag(body, 'price') || '0');
  const currency = extractTag(body, 'currencyId') || 'USD';
  const description = extractTag(body, 'description') || name || '';

  if (!url || !name) return null;
  try { new URL(url); } catch { return null; }

  // First <picture> tag
  const imageUrl = extractTag(body, 'picture') || null;

  // <param name="commissionRate">value</param>
  const commissionRate = parseFloat(extractParam(body, 'commissionRate') || '0');
  const discount = extractParam(body, 'discount') || null;

  return {
    id,
    name: name.trim(),
    description: description.trim(),
    siteUrl: url.trim(),
    imageUrl,
    price,
    currency,
    commissionRate,
    discount,
    source: 'admitad',
  };
}

function extractTag(xml, tag) {
  const m = xml.match(new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>|<${tag}[^>]*>([^<]*)<\\/${tag}>`));
  if (!m) return null;
  return (m[1] !== undefined ? m[1] : m[2] || '').trim() || null;
}

function extractParam(xml, name) {
  const m = xml.match(new RegExp(`<param[^>]+name="${name}"[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/param>|<param[^>]+name="${name}"[^>]*>([^<]*)<\\/param>`));
  if (!m) return null;
  return (m[1] !== undefined ? m[1] : m[2] || '').trim() || null;
}
