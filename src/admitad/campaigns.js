import fetch from 'node-fetch';
import { getAdmitadToken } from './auth.js';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://api.admitad.com';

/**
 * Fetches campaigns via Admitad OAuth API.
 * Returns one product in the unified feed interface.
 */
export async function getAdmitadApiProduct() {
  const token = await getAdmitadToken();
  const websiteId = process.env.ADMITAD_WEBSITE_ID;

  // Global endpoint only — website-scoped requires advcampaigns_for_website scope
  const endpoint = `${API_BASE}/advcampaigns/?limit=50&order_by=-ecpc`;

  const res = await fetch(endpoint, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Admitad campaigns API failed ${res.status}: ${text}`);
  }

  const data = await res.json();
  const campaigns = (data.results || []).filter(c => c.site_url && parseFloat(c.avg_ecpc || 0) > 0);

  if (campaigns.length === 0) throw new Error('No valid campaigns from Admitad API');

  campaigns.sort((a, b) => parseFloat(b.avg_ecpc || 0) - parseFloat(a.avg_ecpc || 0));
  const top5 = campaigns.slice(0, 5);
  const c = top5[Math.floor(Math.random() * top5.length)];

  logger.info(`Admitad API campaign selected: ${c.name} (ecpc: ${c.avg_ecpc})`);

  // Generate deeplink if website ID is available
  let siteUrl = c.site_url;
  if (websiteId) {
    try {
      siteUrl = await generateDeeplink(token, websiteId, c.id, c.site_url);
    } catch (err) {
      logger.warn(`Deeplink failed, using site_url: ${err.message}`);
    }
  }

  return {
    id:             String(c.id),
    name:           String(c.name || '').trim(),
    description:    String(c.description || c.name || '').trim(),
    siteUrl,
    imageUrl:       c.logo || null,
    price:          null,
    currency:       String(c.currency || 'USD'),
    commissionRate: parseFloat(c.avg_ecpc || 0),
    source:         'admitad-api',
  };
}

async function generateDeeplink(token, websiteId, campaignId, targetUrl) {
  const params = new URLSearchParams({
    ulp: targetUrl,
    subid: `auto-${Date.now()}`,
  });

  const res = await fetch(
    `${API_BASE}/deeplink/${websiteId}/advcampaign/${campaignId}/?${params}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );

  if (!res.ok) throw new Error(`Deeplink API ${res.status}`);

  const data = await res.json();
  const link = data?.results?.[0]?.deeplink;
  if (!link) throw new Error('Empty deeplink response');

  logger.info(`Admitad deeplink generated for campaign ${campaignId}`);
  return link;
}
