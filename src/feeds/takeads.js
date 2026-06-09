import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://api.takeads.com/v3';

async function fetchPrograms(apiKey) {
  // Try /v3/programs (plural REST convention) then /v3/program (legacy path)
  const paths = ['/programs', '/program'];
  const query = '?limit=50&programStatus=active&sortBy=avgCommission&sortOrder=desc';
  for (const p of paths) {
    const res = await fetch(`${API_BASE}${p}${query}`, {
      headers: { Authorization: `Bearer ${apiKey}`, Accept: 'application/json' },
      signal: AbortSignal.timeout(30_000),
    });
    if (res.status === 404) {
      logger.warn(`Takeads ${p} returned 404 — trying next path`);
      continue;
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Takeads programs API ${res.status}: ${text.slice(0, 200)}`);
    }
    const data = await res.json();
    logger.info(`Takeads: fetched programs via ${p}`);
    return data.data || [];
  }
  throw new Error('Takeads: all program endpoints returned 404');
}

export async function getTakeadsProduct() {
  const apiKey = process.env.TAKEADS_API_KEY;
  if (!apiKey) return null;

  logger.info('Fetching Takeads product…');
  try {
    const raw = await fetchPrograms(apiKey);
    const programs = raw.filter(p => {
      if (!p.websiteUrl || p.avgCommission <= 0) return false;
      const name = String(p.name || '');
      const nonLatin = (name.match(/[^ -ɏ\s\d\p{P}]/gu) || []).length;
      return nonLatin / (name.length || 1) < 0.4;
    });
    logger.info(`Takeads: ${programs.length} active programs`);
    if (programs.length === 0) return null;

    // Pick top 10 by avgCommission, random pick for variety
    programs.sort((a, b) => (b.avgCommission || 0) - (a.avgCommission || 0));
    const top10 = programs.slice(0, 10);
    const program = top10[Math.floor(Math.random() * top10.length)];
    logger.info(`Takeads program selected: ${program.name} (avgCommission: ${program.avgCommission})`);

    // Resolve to affiliate tracking link
    const trackingLink = await resolveLink(apiKey, program.websiteUrl);

    const name = String(program.name || '').trim();
    const description = (program.description || program.shortDescription || name).trim().slice(0, 300);
    return {
      id:             String(program.id || program.merchantId || ''),
      name,
      description,
      siteUrl:        trackingLink || program.websiteUrl,
      imageUrl:       program.imageUrl || program.logoUrl || null,
      price:          null,
      currency:       'USD',
      commissionRate: parseFloat(program.avgCommission || 0),
      category:       program.category || program.verticalName || null,
      source:         'takeads',
    };
  } catch (err) {
    logger.warn(`Takeads fetch failed: ${err.message}`);
    return null;
  }
}

async function resolveLink(apiKey, url) {
  // Try POST /v3/links first (Postman collection "create-affiliate-links"),
  // then fall back to PUT /v3/resolve (original endpoint).
  const attempts = [
    { method: 'POST', path: '/links' },
    { method: 'PUT',  path: '/resolve' },
  ];

  for (const { method, path } of attempts) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          iris: [url],
          subId: `auto-${Date.now()}`,
          withImages: false,
        }),
        signal: AbortSignal.timeout(15_000),
      });

      if (!res.ok) {
        logger.warn(`Takeads ${method} ${path} returned ${res.status} — trying next`);
        continue;
      }
      const data = await res.json();
      const link = data?.data?.[0]?.trackingLink || data?.links?.[0]?.trackingLink;
      if (link) {
        logger.info(`Takeads tracking link resolved via ${method} ${path}`);
        return link;
      }
    } catch (err) {
      logger.warn(`Takeads resolveLink ${method} ${path} failed: ${err.message}`);
    }
  }
  return null;
}
