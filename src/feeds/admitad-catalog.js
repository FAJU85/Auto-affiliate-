import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';
import { normaliseAliExpressUrl } from '../utils/aliexpress-url.js';

/**
 * Fetches one of the two Admitad Catalog export formats:
 *   - XLSX binary (catalog.store.admitad.com exports)
 *   - XML <advcampaigns> feed (same host, different hash)
 *
 * Env vars:
 *   ADMITAD_CATALOG_URL_1  — first catalog export URL
 *   ADMITAD_CATALOG_URL_2  — second catalog export URL
 *
 * Returns a unified product object or null.
 */
function pickCatalogUrl() {
  return [1, 2, 3, 4, 5]
    .map(n => process.env[`ADMITAD_CATALOG_URL_${n}`])
    .filter(Boolean);
}

async function parseCatalogResponse(res, url) {
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('json')) return parseJsonCatalog(await res.json(), url);

  const text = await res.text();
  if (text.trimStart().startsWith('<?xml') || text.includes('<advcampaigns>')) return parseCampaignXml(text);
  if (text.includes('<yml_catalog') || text.includes('<offers>')) return parseYmlCatalog(text);

  try {
    return parseJsonCatalog(JSON.parse(text), url);
  } catch {
    logger.warn(`Admitad catalog: unrecognised format from ${url.slice(0, 60)}`);
    return null;
  }
}

export async function getAdmitadCatalogProduct() {
  const urls = pickCatalogUrl();
  if (urls.length === 0) return null;

  const url = urls[Math.floor(Math.random() * urls.length)];
  logger.info(`Fetching Admitad catalog: ${url.slice(0, 80)}`);

  try {
    const res = await fetch(url, {
      headers: { Accept: 'application/json, text/xml, */*' },
      signal: AbortSignal.timeout(30_000),
    });
    if (!res.ok) {
      logger.warn(`Admitad catalog HTTP ${res.status} for ${url.slice(0, 60)}`);
      return null;
    }
    return parseCatalogResponse(res, url);
  } catch (err) {
    logger.warn(`Admitad catalog fetch failed: ${err.message}`);
    return null;
  }
}

// ── JSON API parser ───────────────────────────────────────────────────────────

function parseJsonCatalog(data, url) {
  const items = data?.results || data?.data || data?.offers || (Array.isArray(data) ? data : null);
  if (!items || items.length === 0) {
    logger.warn(`Admitad catalog: no items in JSON from ${url.slice(0, 60)}`);
    return null;
  }

  logger.info(`Admitad catalog JSON: ${items.length} offers`);

  const valid = items.filter(o => {
    const link = o.goto_link || o.gotolink || o.affiliate_url || o.url;
    if (!link) return false;
    try { new URL(link); return true; } catch { return false; }
  });

  if (valid.length === 0) {
    logger.warn('Admitad catalog JSON: no offers with valid affiliate links');
    return null;
  }

  // Shuffle fully so all products rotate over time
  valid.sort(() => Math.random() - 0.5);
  const item = valid[0];

  const siteUrl  = normaliseAliExpressUrl(item.goto_link || item.gotolink || item.affiliate_url || item.url);
  const imageUrl = item.picture || item.image || item.image_url || null;

  logger.info(`Admitad catalog JSON selected: "${item.name || item.title}"`);
  return {
    id:             String(item.id || item.product_id || ''),
    name:           String(item.name || item.title || '').trim(),
    description:    String(item.description || item.name || item.title || '').trim(),
    siteUrl,
    imageUrl:       imageUrl && /^https?:\/\//.test(imageUrl) && !/\blogo\b|sprite|placeholder/i.test(imageUrl) ? imageUrl : null,
    price:          parseFloat(item.price || 0) || null,
    currency:       String(item.currency || item.currencyId || 'USD'),
    commissionRate: parseFloat(item.commission || 0),
    source:         'admitad-catalog',
  };
}

// ── XML <advcampaigns> parser ─────────────────────────────────────────────────

function parseCampaignXml(xml) {
  const campaigns = [];
  const re = /<advcampaign>([\s\S]*?)<\/advcampaign>/g;
  let m;
  while ((m = re.exec(xml)) !== null) {
    const body = m[1];
    const id          = extractXmlTag(body, 'id');
    const name        = extractXmlTag(body, 'name');
    const siteUrl     = extractXmlTag(body, 'site_url');
    const gotolink    = extractXmlTag(body, 'gotolink');
    const logo        = extractXmlTag(body, 'logo');
    const description = extractXmlTag(body, 'description');

    // gotolink is the affiliate tracking URL — skip entries that only have a plain site_url
    if (!name || !gotolink) continue;
    try { new URL(gotolink); } catch { continue; }

    // logo is a brand icon, not a product image — leave imageUrl null so the
    // pipeline falls back to og:image scraped from the product page
    campaigns.push({ id, name, siteUrl: normaliseAliExpressUrl(gotolink), imageUrl: null, description: description?.slice(0, 300) || name });
  }

  logger.info(`Admitad catalog XML: ${campaigns.length} campaigns`);
  if (campaigns.length === 0) return null;

  const picked = campaigns[Math.floor(Math.random() * campaigns.length)];
  logger.info(`Admitad catalog XML selected: "${picked.name}"`);

  return {
    id:             String(picked.id || ''),
    name:           picked.name.trim(),
    description:    picked.description.trim(),
    siteUrl:        picked.siteUrl,
    imageUrl:       picked.imageUrl,
    price:          null,
    currency:       'USD',
    commissionRate: 0,
    source:         'admitad-catalog',
  };
}

// ── YML catalog parser (same logic as feeds/admitad.js) ───────────────────────

function parseYmlCatalog(xml) {
  const offerRe = /<offer\s[^>]*id="([^"]*)"[^>]*>([\s\S]*?)<\/offer>/g;
  const offers = [];
  let m;
  while ((m = offerRe.exec(xml)) !== null) {
    const body = m[2];
    const name     = extractXmlTag(body, 'name');
    const url      = extractXmlTag(body, 'url');
    const picture  = extractXmlTag(body, 'picture');
    const desc     = extractXmlTag(body, 'description') || name || '';
    const price    = parseFloat(extractXmlTag(body, 'price') || '0');
    const currency = extractXmlTag(body, 'currencyId') || 'USD';
    if (!url || !name) continue;
    try { new URL(url); } catch { continue; }
    offers.push({ id: m[1], name, siteUrl: normaliseAliExpressUrl(url), imageUrl: picture || null, description: desc, price, currency });
  }

  logger.info(`Admitad catalog YML: ${offers.length} offers`);
  if (offers.length === 0) return null;

  const picked = offers[Math.floor(Math.random() * offers.length)];
  logger.info(`Admitad catalog YML selected: "${picked.name}"`);

  return { ...picked, commissionRate: 0, source: 'admitad-catalog' };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractXmlTag(xml, tag) {
  const m = xml.match(new RegExp(
    `<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>|<${tag}[^>]*>([^<]*)<\\/${tag}>`
  ));
  if (!m) return null;
  return (m[1] !== undefined ? m[1] : m[2] || '').replace(/\r\n|\r/g, ' ').trim() || null;
}
