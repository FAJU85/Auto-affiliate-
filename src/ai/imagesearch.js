import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

// Patterns that indicate a logo, icon, QR code, or other non-product image
const BAD_URL_PATTERNS = [
  /qr[_\-.]?code/i, /barcode/i, /captcha/i,
  /\blogo\b/i, /sprite/i, /icon\.(png|svg|gif|webp)$/i,
  /placeholder/i, /default[-_]image/i, /no[-_]image/i, /blank/i,
  /selene-static/i, /data:image/i,
];

// Flight booking sites whose og:image is always a generic site logo, not a product image
const FLIGHT_SITE_PATTERNS = [/aviasales/i, /skyscanner/i, /kayak/i, /expedia/i, /booking\.com/i];

function isBadImageUrl(url) {
  if (!url || typeof url !== 'string') return true;
  if (!url.startsWith('http')) return true;
  return BAD_URL_PATTERNS.some(p => p.test(url));
}

/**
 * Returns an image URL scraped directly from the product's own siteUrl.
 * We only use the page's own og:image/twitter:image so the image always
 * matches what the user sees when they click the affiliate link.
 * Third-party image search is intentionally excluded — it returns images
 * for similarly-named products that may differ from the linked product.
 */
export async function findProductImage(productName, siteUrl, source) {
  try {
    if (!siteUrl) return null;

    // Flight booking pages always return a site logo, not a useful product image
    if (source === 'travelpayouts' || FLIGHT_SITE_PATTERNS.some(p => p.test(siteUrl))) {
      logger.info(`Skipping image scrape for flight site: ${siteUrl.slice(0, 60)}`);
      return null;
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15_000);
    let html;
    try {
      const res = await fetch(siteUrl, {
        signal: controller.signal,
        headers: { 'User-Agent': 'Mozilla/5.0 (compatible; bot/1.0)' },
      });
      html = res.ok ? await res.text() : null;
    } finally {
      clearTimeout(timeout);
    }

    if (!html) return null;

    // og:image is set explicitly by the site for its own content
    const ogMatch = html.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i)
      || html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i);
    const ogUrl = ogMatch?.[1];
    if (ogUrl && !isBadImageUrl(ogUrl)) {
      const resolved = ogUrl.startsWith('http') ? ogUrl : new URL(ogUrl, siteUrl).href;
      logger.info(`og:image for "${productName}": ${resolved.slice(0, 80)}`);
      return resolved;
    }

    // twitter:image as secondary fallback
    const twMatch = html.match(/<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)["']/i)
      || html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+name=["']twitter:image["']/i);
    const twUrl = twMatch?.[1];
    if (twUrl && !isBadImageUrl(twUrl)) {
      const resolved = twUrl.startsWith('http') ? twUrl : new URL(twUrl, siteUrl).href;
      logger.info(`twitter:image for "${productName}": ${resolved.slice(0, 80)}`);
      return resolved;
    }

    logger.info(`No usable image found for "${productName}" at ${siteUrl.slice(0, 60)}`);
    return null;
  } catch (err) {
    logger.warn(`findProductImage error for ${siteUrl?.slice(0, 60)}: ${err.message}`);
    return null;
  }
}
