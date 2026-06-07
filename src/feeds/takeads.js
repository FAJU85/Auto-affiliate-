import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const API_BASE = 'https://api.takeads.com/monetize-api/v2';

export async function getTakeadsProduct() {
  const apiKey = process.env.TAKEADS_API_KEY;
  if (!apiKey) return null;

  logger.info('Fetching Takeads product…');
  try {
    // 1. Get list of active programs sorted by avgCommission
    const res = await fetch(
      `${API_BASE}/program?limit=50&programStatus=active`,
      {
        headers: { Authorization: `Bearer ${apiKey}`, Accept: 'application/json' },
        signal: AbortSignal.timeout(30_000),
      }
    );

    if (!res.ok) {
      const text = await res.text();
      logger.warn(`Takeads API error ${res.status}: ${text.slice(0, 200)}`);
      return null;
    }

    const data = await res.json();
    const programs = (data.data || []).filter(p => p.websiteUrl && p.avgCommission > 0);
    logger.info(`Takeads: ${programs.length} active programs`);
    if (programs.length === 0) return null;

    // Pick top 5 by avgCommission, random pick
    programs.sort((a, b) => (b.avgCommission || 0) - (a.avgCommission || 0));
    const top5 = programs.slice(0, 5);
    const program = top5[Math.floor(Math.random() * top5.length)];
    logger.info(`Takeads program selected: ${program.name} (avgCommission: ${program.avgCommission})`);

    // 2. Resolve to affiliate tracking link
    const trackingLink = await resolveLink(apiKey, program.websiteUrl);

    return {
      id:             String(program.id || program.merchantId || ''),
      name:           String(program.name || '').trim(),
      description:    String(program.name || '').trim(),
      siteUrl:        trackingLink || program.websiteUrl,
      imageUrl:       program.imageUrl || null,
      price:          null,
      currency:       'USD',
      commissionRate: parseFloat(program.avgCommission || 0),
      source:         'takeads',
    };
  } catch (err) {
    logger.warn(`Takeads fetch failed: ${err.message}`);
    return null;
  }
}

async function resolveLink(apiKey, url) {
  try {
    const res = await fetch(`${API_BASE}/resolve`, {
      method: 'PUT',
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

    if (!res.ok) return null;
    const data = await res.json();
    const link = data?.data?.[0]?.trackingLink;
    if (link) logger.info(`Takeads tracking link resolved for ${url}`);
    return link || null;
  } catch {
    return null;
  }
}
