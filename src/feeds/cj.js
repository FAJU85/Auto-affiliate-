import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://link-search.api.cj.com/v2/link-search';

function getCredentials() {
  const apiKey    = process.env.CJ_API_KEY;
  const websiteId = process.env.CJ_WEBSITE_ID;
  return { apiKey, websiteId, ready: !!(apiKey && websiteId) };
}

async function fetchLinks(apiKey, websiteId) {
  // Randomise page to spread across the catalogue over successive runs
  const page = Math.ceil(Math.random() * 5);
  const params = new URLSearchParams({
    'website-id':        websiteId,
    'advertiser-ids':    'joined',   // only advertisers you are already joined with
    'records-per-page':  '100',
    'page-number':       String(page),
  });

  const res = await fetch(`${API_BASE}?${params}`, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      Accept: 'application/json',
    },
    signal: AbortSignal.timeout(30_000),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`CJ API ${res.status}: ${text.slice(0, 200)}`);
  }

  const data = await res.json();
  // Response: { links: { link: [...] } }  (array or single object if one result)
  const raw = data?.links?.link ?? [];
  return Array.isArray(raw) ? raw : [raw];
}

function pickLink(links) {
  const valid = links.filter(l => {
    const url = l.destination || l['destination'];
    if (!url) return false;
    try { new URL(url); return true; } catch { return false; }
  });

  if (valid.length === 0) return null;
  valid.sort(() => Math.random() - 0.5);
  return valid[0];
}

function buildProduct(link) {
  const siteUrl  = link.destination;
  const name     = String(link['link-name'] || link['@advertiser-name'] || '').trim();
  const desc     = String(link.description || name).trim().slice(0, 300);
  const imageUrl = link['image-url'] || null;
  const commStr  = link['click-commission'] || link['sale-commission'] || '0';
  const commission = parseFloat(commStr.replace('%', '')) || 0;

  logger.info(`CJ link selected: "${name}" (${link['@advertiser-name']}) → ${siteUrl.slice(0, 60)}`);

  return {
    id:             String(link['@id'] || link['link-id'] || ''),
    name,
    description:    desc,
    siteUrl,
    imageUrl:       imageUrl && /^https?:\/\//.test(imageUrl) ? imageUrl : null,
    price:          null,
    currency:       'USD',
    commissionRate: commission,
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
