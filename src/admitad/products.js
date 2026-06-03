import fetch from 'node-fetch';
import { getAdmitadToken } from './auth.js';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://api.admitad.com';

/**
 * Fetches product/campaign feed from Admitad and applies filtering logic:
 * - Minimum commission rate (default 10%)
 * - Valid affiliate URL
 * - Sort by margin descending, return top 1
 */
export async function getTopProduct() {
  const token = await getAdmitadToken();
  const minEcpc = parseFloat(process.env.MIN_COMMISSION_RATE || '0.10');

  const params = new URLSearchParams({
    limit: '50',
    offset: '0',
    order_by: '-ecpc',
  });

  const res = await fetch(`${API_BASE}/advcampaigns/?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Admitad products fetch failed ${res.status}: ${text}`);
  }

  const data = await res.json();
  const campaigns = data.results || [];
  logger.info(`Admitad: fetched ${campaigns.length} campaigns`);

  const filtered = campaigns.filter(c => {
    const hasUrl = !!c.site_url;
    const ecpc = parseFloat(c.avg_ecpc || 0);
    return hasUrl && ecpc >= minEcpc;
  });

  logger.info(`After filter (minEcpc=${minEcpc}): ${filtered.length} campaigns`);

  // Sort by highest ecpc (margin proxy), pick top
  filtered.sort((a, b) => parseFloat(b.avg_ecpc || 0) - parseFloat(a.avg_ecpc || 0));

  const top = filtered[0];
  if (!top) throw new Error('No valid products found after filtering');

  logger.info(`Selected campaign: ${top.name} (ecpc: ${top.avg_ecpc})`);
  const product = normalizeCampaign(top);
  product._fetchedCount = campaigns.length;
  product._filteredCount = filtered.length;
  return product;
}

function normalizeCampaign(c) {
  const id = String(c.id || '');
  const name = String(c.name || '').trim() || 'Unknown Product';
  const siteUrl = isValidHttpUrl(c.site_url) ? c.site_url : null;
  if (!siteUrl) throw new Error(`Campaign ${id} has invalid site_url: ${c.site_url}`);
  return {
    id,
    name,
    description: String(c.description || c.name || name).trim(),
    siteUrl,
    logoUrl: c.logo || null,
    category: String(c.categories?.[0]?.name || 'Product').trim(),
    ecpc: parseFloat(c.avg_ecpc || 0),
    currency: String(c.currency || 'USD'),
  };
}

function isValidHttpUrl(str) {
  try {
    const u = new URL(str);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

export async function buildDeeplink(product) {
  const token = await getAdmitadToken();

  const body = new URLSearchParams({
    campaign_id: product.id,
    url: product.siteUrl,
    advcampaign_id: product.id,
    subid: `auto-${Date.now()}`,
  });

  const res = await fetch(`${API_BASE}/deeplink/get/`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  });

  if (!res.ok) {
    logger.warn(`Deeplink generation failed ${res.status}, using site URL as fallback`);
    return product.siteUrl;
  }

  const data = await res.json();
  const deeplink = data.deeplink;
  if (deeplink && isValidHttpUrl(deeplink)) return deeplink;
  logger.warn('Deeplink API returned invalid or empty URL, falling back to siteUrl');
  return product.siteUrl;
}
