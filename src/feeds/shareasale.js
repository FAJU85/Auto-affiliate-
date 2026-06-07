import fetch from 'node-fetch';
import crypto from 'crypto';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://api.shareasale.com/x.cfm';

function getCredentials() {
  const token       = process.env.SHAREASALE_TOKEN;
  const secret      = process.env.SHAREASALE_SECRET;
  const affiliateId = process.env.SHAREASALE_AFFILIATE_ID;
  return { token, secret, affiliateId, ready: !!(token && secret && affiliateId) };
}

function buildAuthHeaders(token, secret, action) {
  const date = new Date().toUTCString();
  const sigInput = `${token}:${date}:${action}:${secret}`;
  const sig = crypto.createHash('sha256').update(sigInput).digest('hex');
  return {
    'x-ShareASale-Date':           date,
    'x-ShareASale-Authentication': sig,
  };
}

async function searchProducts(token, secret, affiliateId) {
  const action = 'productSearch';
  const params = new URLSearchParams({
    action,
    affiliateId,
    token,
    version:   '2.8',
    XMLFormat: '1',
    joined:    '1',   // only merchants you have joined
    pageSize:  '100',
    page:      String(Math.ceil(Math.random() * 5)),
  });

  const res = await fetch(`${API_BASE}?${params}`, {
    headers: {
      ...buildAuthHeaders(token, secret, action),
      Accept: 'application/xml, text/xml',
    },
    signal: AbortSignal.timeout(30_000),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`ShareASale API ${res.status}: ${text.slice(0, 200)}`);
  }

  return res.text();
}

function extractXmlValue(xml, tag) {
  const m = xml.match(new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>|<${tag}[^>]*>([^<]*)<\\/${tag}>`));
  if (!m) return '';
  return (m[1] !== undefined ? m[1] : m[2] || '').trim();
}

function parseProducts(xml) {
  const products = [];
  const re = /<product>([\s\S]*?)<\/product>/g;
  let m;
  while ((m = re.exec(xml)) !== null) {
    const body       = m[1];
    const affiliateUrl = extractXmlValue(body, 'AffiliateURL') || extractXmlValue(body, 'affiliateurl');
    const name         = extractXmlValue(body, 'Name')         || extractXmlValue(body, 'name');
    if (!affiliateUrl || !name) continue;
    try { new URL(affiliateUrl); } catch { continue; }

    products.push({
      id:             extractXmlValue(body, 'SKU') || extractXmlValue(body, 'sku') || '',
      name:           name.trim(),
      description:    (extractXmlValue(body, 'Description') || name).trim().slice(0, 300),
      siteUrl:        affiliateUrl,
      imageUrl:       extractXmlValue(body, 'ImageURL') || extractXmlValue(body, 'imageurl') || null,
      price:          parseFloat(extractXmlValue(body, 'Price') || '0') || null,
      currency:       'USD',
      commissionRate: parseFloat(extractXmlValue(body, 'Commission') || '0'),
      source:         'shareasale',
    });
  }
  return products;
}

export async function getShareASaleProduct() {
  const { token, secret, affiliateId, ready } = getCredentials();
  if (!ready) return null;

  logger.info('Fetching ShareASale products…');
  try {
    const xml      = await searchProducts(token, secret, affiliateId);
    const products = parseProducts(xml);
    logger.info(`ShareASale: ${products.length} products parsed`);
    if (products.length === 0) return null;

    // Prefer products with commission > 0 and valid images
    const withCommission = products.filter(p => p.commissionRate > 0);
    const base = withCommission.length > 0 ? withCommission : products;
    const withImage = base.filter(p => p.imageUrl && /^https?:\/\//.test(p.imageUrl));
    const pool = withImage.length > 0 ? withImage : base;
    pool.sort(() => Math.random() - 0.5);
    const picked = pool[0];
    logger.info(`ShareASale selected: "${picked.name}" (commission: ${picked.commissionRate}%)`);
    return picked;
  } catch (err) {
    logger.warn(`ShareASale fetch failed: ${err.message}`);
    return null;
  }
}
