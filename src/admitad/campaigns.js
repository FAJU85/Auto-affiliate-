import fetch from 'node-fetch';
import { getAdmitadToken, invalidateAdmitadToken } from './auth.js';
import { logger } from '../utils/logger.js';
import { normaliseAliExpressUrl, isAliExpressUrl } from '../utils/aliexpress-url.js';
import { sleepRetryAfter } from '../utils/rate-limit.js';

const API_BASE = 'https://api.admitad.com';

/**
 * Fetches campaigns via Admitad OAuth API.
 * Returns one product in the unified feed interface.
 */
export async function getAdmitadApiProduct() {
  const websiteId = process.env.ADMITAD_WEBSITE_ID;

  // Without ADMITAD_WEBSITE_ID we cannot generate affiliate deeplinks,
  // so there is no point fetching campaigns — plain site_url earns no commission.
  if (!websiteId) {
    throw new Error('ADMITAD_WEBSITE_ID not set — skipping admitad-api (no deeplink possible)');
  }

  const token = await getAdmitadToken();

  // Global endpoint only — website-scoped requires advcampaigns_for_website scope
  const endpoint = `${API_BASE}/advcampaigns/?limit=50&order_by=-ecpc`;

  let res = await fetch(endpoint, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(20_000),
  });

  // Refresh token once on 401 (token may have expired mid-use despite local TTL)
  if (res.status === 401) {
    logger.warn('Admitad campaigns: 401 — refreshing token and retrying');
    invalidateAdmitadToken();
    const freshToken = await getAdmitadToken();
    res = await fetch(endpoint, { headers: { Authorization: `Bearer ${freshToken}` }, signal: AbortSignal.timeout(20_000) });
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Admitad campaigns API failed ${res.status}: ${text}`);
  }

  const data = await res.json();
  const campaigns = (data.results || []).filter(c => c.site_url && parseFloat(c.avg_ecpc || 0) > 0);

  if (campaigns.length === 0) throw new Error('No valid campaigns from Admitad API');

  // Shuffle fully so all campaigns rotate over time
  campaigns.sort(() => Math.random() - 0.5);
  const c = campaigns[0];

  logger.info(`Admitad API campaign selected: ${c.name} (ecpc: ${c.avg_ecpc})`);

  // Deeplink is mandatory — plain site_url is not an affiliate link
  const siteUrl = await generateDeeplink(token, websiteId, c.id, c.site_url);

  return {
    id:             String(c.id),
    name:           String(c.name || '').trim(),
    description:    String(c.description || c.name || '').trim(),
    siteUrl,
    imageUrl:       null, // brand logos are not product images
    price:          null,
    currency:       String(c.currency || 'USD'),
    commissionRate: parseFloat(c.avg_ecpc || 0),
    source:         'admitad-api',
  };
}

async function generateDeeplink(token, websiteId, campaignId, targetUrl) {
  // Normalise AliExpress URLs so the app opens to the correct product page
  const ulp = isAliExpressUrl(targetUrl) ? normaliseAliExpressUrl(targetUrl) : targetUrl;
  if (ulp !== targetUrl) logger.info(`AliExpress URL normalised for app compatibility`);

  const params = new URLSearchParams({
    ulp,
    subid: `auto-${Date.now()}`,
  });

  let res = await fetch(
    `${API_BASE}/deeplink/${websiteId}/advcampaign/${campaignId}/?${params}`,
    { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(20_000) },
  );

  if (res.status === 429) {
    await sleepRetryAfter(res.headers.get('Retry-After'), { name: 'Admitad deeplink', fallbackMs: 10_000 });
    res = await fetch(
      `${API_BASE}/deeplink/${websiteId}/advcampaign/${campaignId}/?${params}`,
      { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(20_000) },
    );
  }

  if (!res.ok) throw new Error(`Deeplink API ${res.status}`);

  const data = await res.json();
  const link = data?.results?.[0]?.deeplink;
  if (!link) throw new Error('Empty deeplink response');

  logger.info(`Admitad deeplink generated for campaign ${campaignId}`);
  return link;
}
