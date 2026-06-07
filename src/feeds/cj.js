import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';
import { sleepRetryAfter } from '../utils/rate-limit.js';

const API_BASE = 'https://link-search.api.cj.com/v2/link-search';

function getCredentials() {
  const apiKey    = process.env.CJ_API_KEY;
  const websiteId = process.env.CJ_WEBSITE_ID;
  return { apiKey, websiteId, ready: !!(apiKey && websiteId) };
}

const SEARCH_KEYWORDS = [
  'sale', 'discount', 'deal', 'offer', 'promo', 'clearance',
  'new arrival', 'best seller', 'limited', 'exclusive',
  'free shipping', 'bundle', 'gift', 'seasonal',
];

async function fetchLinks(apiKey, websiteId) {
  // Randomise page to spread across the catalogue over successive runs
  const page = Math.ceil(Math.random() * 5);
  const keyword = SEARCH_KEYWORDS[Math.floor(Math.random() * SEARCH_KEYWORDS.length)];
  const params = new URLSearchParams({
    'website-id':        websiteId,
    'advertiser-ids':    'joined',   // only advertisers you are already joined with
    'records-per-page':  '100',
    'page-number':       String(page),
    'keywords':          keyword,
  });

  const res = await fetch(`${API_BASE}?${params}`, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      Accept: 'application/json',
    },
    signal: AbortSignal.timeout(30_000),
  });

  if (res.status === 429) {
    await sleepRetryAfter(res.headers.get('Retry-After'), { name: 'CJ Affiliate', fallbackMs: 10_000 });
    const res2 = await fetch(`${API_BASE}?${params}`, {
      headers: { Authorization: `Bearer ${apiKey}`, Accept: 'application/json' },
      signal: AbortSignal.timeout(30_000),
    });
    if (!res2.ok) throw new Error(`CJ API ${res2.status} (retry)`);
    const data2 = await res2.json();
    const raw2 = data2?.links?.link ?? [];
    return Array.isArray(raw2) ? raw2 : [raw2];
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`CJ API ${res.status}: ${text.slice(0, 200)}`);
  }

  const data = await res.json();
  // Response: { links: { link: [...] } }  (array or single object if one result)
  const raw = data?.links?.link ?? [];
  return Array.isArray(raw) ? raw : [raw];
}

function isLatinName(str) {
  if (!str || str.length < 3) return true;
  const nonLatin = (str.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
  return nonLatin / str.length < 0.4;
}

function pickLink(links) {
  const valid = links.filter(l => {
    const url = l.destination || l['destination'];
    if (!url) return false;
    const name = String(l['link-name'] || l['@advertiser-name'] || '');
    if (!isLatinName(name)) return false;
    try { new URL(url); return true; } catch { return false; }
  });

  if (valid.length === 0) return null;
  // Prefer links with commission > 0
  const withCommission = valid.filter(l => {
    const commStr = l['click-commission'] || l['sale-commission'] || '0';
    return parseFloat(commStr.replace('%', '')) > 0;
  });
  const pool = withCommission.length > 0 ? withCommission : valid;
  pool.sort(() => Math.random() - 0.5);
  return pool[0];
}

function buildProduct(link) {
  const siteUrl  = link.destination;
  const name     = String(link['link-name'] || link['@advertiser-name'] || '').trim();
  const desc     = String(link.description || name).trim().slice(0, 300);
  const imageUrl = link['image-url'] || null;
  const commStr  = link['click-commission'] || link['sale-commission'] || '0';
  const commission = parseFloat(commStr.replace('%', '')) || 0;

  const advertiserName = String(link['@advertiser-name'] || '').trim();
  logger.info(`CJ link selected: "${name}" (${advertiserName}) → ${siteUrl.slice(0, 60)}`);

  return {
    id:             String(link['@id'] || link['link-id'] || ''),
    name,
    description:    desc,
    siteUrl,
    imageUrl:       imageUrl && /^https?:\/\//.test(imageUrl) ? imageUrl : null,
    price:          null,
    currency:       'USD',
    commissionRate: commission,
    category:       String(link['link-type'] || link['category'] || advertiserName || '').trim() || null,
    source:         'cj',
  };
}

export async function getCJProduct() {
  const { apiKey, websiteId, ready } = getCredentials();
  if (!ready) return null;

  logger.info('Fetching CJ Affiliate links…');
  try {
    const links = await fetchLinks(apiKey, websiteId);
    logger.info(`CJ Affiliate: ${links.length} links returned`);
    if (links.length === 0) return null;

    const link = pickLink(links);
    if (!link) { logger.warn('CJ Affiliate: no links with valid destination URLs'); return null; }

    return buildProduct(link);
  } catch (err) {
    logger.warn(`CJ Affiliate fetch failed: ${err.message}`);
    return null;
  }
}
