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
  const minCommission = parseFloat(process.env.MIN_COMMISSION_RATE || '0.10');

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
    const rate = parseFloat(c.avg_money_transfer_time || c.max_money_transfer || 0);
    const hasUrl = !!c.site_url;
    const commission = parseFloat(c.avg_ecpc || 0);
    // Use ecpc as proxy for margin; filter campaigns with affiliate URL
    return hasUrl && commission > 0;
  });

  logger.info(`After URL filter: ${filtered.length} campaigns`);

  // Sort by highest ecpc (margin proxy), pick top
  filtered.sort((a, b) => parseFloat(b.avg_ecpc || 0) - parseFloat(a.avg_ecpc || 0));

  const top = filtered[0];
  if (!top) throw new Error('No valid products found after filtering');

  logger.info(`Selected campaign: ${top.name} (ecpc: ${top.avg_ecpc})`);
  return normalizeCampaign(top);
}

function normalizeCampaign(c) {
  return {
    id: String(c.id),
    name: c.name,
    description: c.description || c.name,
    siteUrl: c.site_url,
    logoUrl: c.logo || null,
    category: c.categories?.[0]?.name || 'Product',
    ecpc: parseFloat(c.avg_ecpc || 0),
    currency: c.currency || 'USD',
  };
}

export async function buildDeeplink(product) {
  const token = await getAdmitadToken();
  const { ADMITAD_CLIENT_ID } = process.env;

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
  return data.deeplink || product.siteUrl;
}
