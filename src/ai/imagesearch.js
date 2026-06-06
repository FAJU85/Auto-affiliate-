import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

// URLs that typically return logos, QR codes, or irrelevant images
const BAD_URL_PATTERNS = [
  /qr[_\-.]?code/i, /barcode/i, /captcha/i, /logo\.(png|svg|gif)/i,
  /placeholder/i, /default[-_]image/i, /no[-_]image/i, /blank/i,
  /selene-static/i, // aviasales generic logo
  /sprite/i, /icon\.(png|svg)/i,
];

function isBadImageUrl(url) {
  return BAD_URL_PATTERNS.some(p => p.test(url));
}

// For flight products, search for destination city image instead of scraping the booking URL
function getSearchQuery(productName, source) {
  if (source === 'travelpayouts' || /flight/i.test(productName)) {
    // Extract destination: "Flight NYC → DFW" → "DFW city travel"
    const dest = productName.match(/→\s*([A-Z]{3})/)?.[1];
    return dest ? `${dest} city travel destination` : `${productName} travel`;
  }
  return `${productName} product`;
}

export async function findProductImage(productName, siteUrl, source) {
  try {
    const apiKey = process.env.LANGSEARCH_API_KEY;

    // Step 1: LangSearch with a smart query
    if (apiKey) {
      try {
        const q = encodeURIComponent(getSearchQuery(productName, source));
        const res = await fetch(`https://langsearch.com/api/v1/search?q=${q}&count=5`, {
          headers: { Authorization: `Bearer ${apiKey}` },
          signal: AbortSignal.timeout(10_000),
        });
        if (res.ok) {
          const data = await res.json();
          for (const result of (data?.results || [])) {
            const imgUrl = result?.image || result?.thumbnail;
            if (imgUrl && imgUrl.startsWith('https://') && !isBadImageUrl(imgUrl)) {
              logger.info(`LangSearch image: ${imgUrl.slice(0, 80)}`);
              return imgUrl;
            }
          }
        }
      } catch (err) {
        logger.warn(`LangSearch failed: ${err.message}`);
      }
    }

    // Step 2: og:image from siteUrl — skip for flight booking pages (just get generic logos)
    const isFlightUrl = source === 'travelpayouts' || /aviasales|skyscanner|kayak/i.test(siteUrl || '');
    if (siteUrl && !isFlightUrl) {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15_000);
        let html;
        try {
          const res = await fetch(siteUrl, { signal: controller.signal });
          html = res.ok ? await res.text() : null;
        } finally { clearTimeout(timeout); }

        if (html) {
          const ogMatch = html.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i)
            || html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i);
          const url = ogMatch?.[1];
          if (url && url.startsWith('https://') && !isBadImageUrl(url)) {
            logger.info(`og:image: ${url.slice(0, 80)}`);
            return url;
          }

          // First non-bad img
          const imgs = [...html.matchAll(/<img[^>]+src=["'](https:\/\/[^"']+)["']/gi)];
          for (const m of imgs) {
            if (!isBadImageUrl(m[1])) {
              logger.info(`img src: ${m[1].slice(0, 80)}`);
              return m[1];
            }
          }
        }
      } catch (err) {
        logger.warn(`Site image scrape failed: ${err.message}`);
      }
    }

    return null;
  } catch (err) {
    logger.warn(`findProductImage error: ${err.message}`);
    return null;
  }
}
