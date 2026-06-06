import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';
import { read as xlsxRead, utils as xlsxUtils } from 'xlsx';

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
export async function getAdmitadCatalogProduct() {
  const urls = [
    process.env.ADMITAD_CATALOG_URL_1,
    process.env.ADMITAD_CATALOG_URL_2,
  ].filter(Boolean);

  if (urls.length === 0) return null;

  // Shuffle so both URLs get used over time
  const url = urls[Math.floor(Math.random() * urls.length)];

  logger.info(`Fetching Admitad catalog: ${url.slice(0, 80)}`);

  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(30_000) });
    if (!res.ok) {
      logger.warn(`Admitad catalog HTTP ${res.status} for ${url.slice(0, 60)}`);
      return null;
    }

    const contentType = res.headers.get('content-type') || '';

    // XLSX binary export
    if (
      contentType.includes('spreadsheetml') ||
      contentType.includes('octet-stream') ||
      contentType.includes('zip')
    ) {
      return await parseXlsx(res, url);
    }

    // XML advcampaigns feed (served as text/html by Admitad but is XML)
    const text = await res.text();
    if (text.trimStart().startsWith('<?xml') || text.includes('<advcampaigns>')) {
      return parseCampaignXml(text);
    }

    // YML product catalog (same as ADMITAD_FEED_URL but via this path)
    if (text.includes('<yml_catalog') || text.includes('<offers>')) {
      return parseYmlCatalog(text);
    }

    logger.warn(`Admitad catalog: unrecognised format from ${url.slice(0, 60)}`);
    return null;
  } catch (err) {
    logger.warn(`Admitad catalog fetch failed: ${err.message}`);
    return null;
  }
}

// ── XLSX parser ──────────────────────────────────────────────────────────────

async function parseXlsx(res, url) {
  try {
    const buf = Buffer.from(await res.arrayBuffer());
    const wb = xlsxRead(buf, { type: 'buffer' });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    const rows = xlsxUtils.sheet_to_json(sheet, { defval: '' });

    if (rows.length === 0) {
      logger.warn('Admitad catalog XLSX: no rows');
      return null;
    }

    logger.info(`Admitad catalog XLSX: ${rows.length} rows`);

    // Normalise column names to lowercase for resilience
    const normalised = rows.map(r => {
      const out = {};
      for (const [k, v] of Object.entries(r)) out[k.toLowerCase().trim()] = v;
      return out;
    });

    // Filter rows that have at least a name and a URL
    const candidates = normalised.filter(r => {
      const hasUrl = r.url || r.link || r['site url'] || r['product url'] || r.deeplink;
      const hasName = r.name || r['product name'] || r.title;
      return hasUrl && hasName;
    });

    if (candidates.length === 0) {
      logger.warn('Admitad catalog XLSX: no usable rows');
      return null;
    }

    // Pick one at random from the top 20
    const pool = candidates.slice(0, 20);
    const row = pool[Math.floor(Math.random() * pool.length)];

    const name        = String(row.name || row['product name'] || row.title || '').trim();
    const siteUrl     = String(row.url || row.link || row['site url'] || row['product url'] || row.deeplink || '').trim();
    const imageUrl    = String(row.image || row['image url'] || row.picture || row.photo || '').trim() || null;
    const description = String(row.description || row.desc || row.category || name).trim();
    const price       = parseFloat(row.price || row.cost || '0') || null;
    const currency    = String(row.currency || row.currencyid || 'USD').trim();

    if (!siteUrl || !name) return null;
    try { new URL(siteUrl); } catch { return null; }

    logger.info(`Admitad catalog XLSX selected: "${name}"`);
    return {
      id:             String(row.id || row.offer_id || Math.random()),
      name,
      description,
      siteUrl,
      imageUrl: imageUrl && imageUrl.startsWith('http') ? imageUrl : null,
      price,
      currency,
      commissionRate: parseFloat(row.commission || row.commissionrate || '0') || 0,
      source:         'admitad-catalog',
    };
  } catch (err) {
    logger.warn(`Admitad catalog XLSX parse error: ${err.message}`);
    return null;
  }
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
    campaigns.push({ id, name, siteUrl: gotolink, imageUrl: null, description: description?.slice(0, 300) || name });
  }

  logger.info(`Admitad catalog XML: ${campaigns.length} campaigns`);
  if (campaigns.length === 0) return null;

  const picked = campaigns[Math.floor(Math.random() * Math.min(10, campaigns.length))];
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
    offers.push({ id: m[1], name, siteUrl: url, imageUrl: picture || null, description: desc, price, currency });
  }

  logger.info(`Admitad catalog YML: ${offers.length} offers`);
  if (offers.length === 0) return null;

  const pool = offers.slice(0, 5);
  const picked = pool[Math.floor(Math.random() * pool.length)];
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
