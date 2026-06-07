import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://api.impact.com';

function getCredentials() {
  const accountSid = process.env.IMPACT_ACCOUNT_SID;
  const authToken  = process.env.IMPACT_AUTH_TOKEN;
  return { accountSid, authToken, ready: !!(accountSid && authToken) };
}

function basicAuth(accountSid, authToken) {
  return 'Basic ' + Buffer.from(`${accountSid}:${authToken}`).toString('base64');
}

async function fetchAds(accountSid, authToken) {
  // Try up to 3 random pages to get variety
  const page = Math.ceil(Math.random() * 3);
  const params = new URLSearchParams({ PageSize: '100', Page: String(page) });
  const res = await fetch(
    `${API_BASE}/Mediapartners/${accountSid}/Ads?${params}`,
    {
      headers: {
        Authorization: basicAuth(accountSid, authToken),
        Accept: 'application/json',
      },
      signal: AbortSignal.timeout(30_000),
    }
  );

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Impact API ${res.status}: ${text.slice(0, 200)}`);
  }

  const data = await res.json();
  const ads = data.Ads || [];
  // If this page is empty and it wasn't page 1, fall back to page 1
  if (ads.length === 0 && page > 1) {
    const res1 = await fetch(
      `${API_BASE}/Mediapartners/${accountSid}/Ads?PageSize=100&Page=1`,
      { headers: { Authorization: basicAuth(accountSid, authToken), Accept: 'application/json' }, signal: AbortSignal.timeout(30_000) }
    );
    if (res1.ok) return (await res1.json()).Ads || [];
  }
  return ads;
}

function pickAd(ads) {
  const valid = ads.filter(ad => {
    const link = ad.TrackingLink || ad.LandingPageUrl;
    if (!link) return false;
    try { new URL(link); return true; } catch { return false; }
  });

  if (valid.length === 0) return null;

  // Prefer ads with a product image URL
  const withImage = valid.filter(ad => ad.ImageUrl && /^https?:\/\//.test(ad.ImageUrl));
  const pool = withImage.length > 0 ? withImage : valid;
  pool.sort(() => Math.random() - 0.5);
  return pool[0];
}

function buildProduct(ad) {
  const siteUrl = ad.TrackingLink || ad.LandingPageUrl;
  const name    = String(ad.Name || ad.CampaignName || '').trim();
  const desc    = String(ad.Description || name).trim().slice(0, 300);
  const imageUrl = ad.ImageUrl || null;

  logger.info(`Impact.com ad selected: "${name}" → ${siteUrl.slice(0, 60)}`);

  return {
    id:             String(ad.Id || ''),
    name,
    description:    desc,
    siteUrl,
    imageUrl:       imageUrl && /^https?:\/\//.test(imageUrl) ? imageUrl : null,
    price:          null,
    currency:       'USD',
    commissionRate: 0,
    category:       String(ad.Type || ad.AdType || ad.CampaignName || '').trim() || null,
    source:         'impact',
  };
}

export async function getImpactProduct() {
  const { accountSid, authToken, ready } = getCredentials();
  if (!ready) return null;

  logger.info('Fetching Impact.com ads…');
  try {
    const ads = await fetchAds(accountSid, authToken);
    logger.info(`Impact.com: ${ads.length} ads returned`);
    if (ads.length === 0) return null;

    const ad = pickAd(ads);
    if (!ad) { logger.warn('Impact.com: no ads with valid tracking links'); return null; }

    return buildProduct(ad);
  } catch (err) {
    logger.warn(`Impact.com fetch failed: ${err.message}`);
    return null;
  }
}
