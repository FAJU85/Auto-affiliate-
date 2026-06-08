import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';
import { searchProductUrls } from './exa.js';

// Patterns that indicate a logo, icon, QR code, or other non-product image
const BAD_URL_PATTERNS = [
  /qr[_\-.]?code/i, /barcode/i, /captcha/i,
  /\blogo\b/i, /sprite/i, /icon\.(png|svg|gif|webp)$/i,
  /placeholder/i, /default[-_]image/i, /no[-_]image/i, /blank/i,
  /selene-static/i, /data:image/i,
  /\bfavicon\b/i, /\.ico$/i, /banner/i, /thumb.*background/i,
  /social[-_]share/i, /og[-_]default/i,
  /avatar/i, /profile[-_]pic/i, /user[-_]image/i,
  /1x1\.(gif|png|jpg)/i, /pixel\.(gif|png)/i, /tracking/i,
  /header[-_]bg/i, /bg[-_]image/i, /hero[-_]bg/i,
  // SaaS brand generic images — always return their marketing banner, never a product
  /cdn\.shopify\.com\/s\/files\/1\/\d+\/\d+\/files/i, // Shopify brand CDN
  /shopify\.com.*shopify[-_]logo/i,
  /burst\.shopifycdn/i,
];

// Sites whose og:image is always a brand/marketing image, never a specific product
const BRAND_SITE_PATTERNS = [
  // Flight booking
  /aviasales/i, /skyscanner/i, /kayak/i, /expedia/i, /booking\.com/i,
  // SaaS platforms — they promote THEMSELVES as a product, not physical goods
  /shopify\.com/i, /squarespace\.com/i, /wix\.com/i, /wordpress\.com/i,
  /fiverr\.com/i, /upwork\.com/i, /canva\.com/i,
];

// Flight booking sites whose og:image is always a generic site logo, not a product image
const FLIGHT_SITE_PATTERNS = [/aviasales/i, /skyscanner/i, /kayak/i, /expedia/i, /booking\.com/i];

function isBadImageUrl(url) {
  if (!url || typeof url !== 'string') return true;
  if (!url.startsWith('http')) return true;
  return BAD_URL_PATTERNS.some(p => p.test(url));
}

function resolveUrl(url, siteUrl) {
  if (!url) return null;
  return url.startsWith('http') ? url : new URL(url, siteUrl).href;
}

function extractMetaImage(html, siteUrl) {
  const candidates = [
    // og:image (property before content)
    html.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i)?.[1],
    // og:image (content before property)
    html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i)?.[1],
    // twitter:image
    html.match(/<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)["']/i)?.[1],
    html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+name=["']twitter:image["']/i)?.[1],
    // link rel="image_src"
    html.match(/<link[^>]+rel=["']image_src["'][^>]+href=["']([^"']+)["']/i)?.[1],
  ];

  for (const url of candidates) {
    if (!url) continue;
    const resolved = resolveUrl(url, siteUrl);
    if (resolved && !isBadImageUrl(resolved)) return resolved;
  }
  return null;
}

async function scrapeMetaImage(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      redirect: 'follow',
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; bot/1.0)', 'Accept': 'text/html' },
    });
    const html = res.ok ? await res.text() : null;
    return html ? extractMetaImage(html, url) : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Find a product image. Search order:
 *
 *  1. Scrape og:image / twitter:image directly from the affiliate siteUrl.
 *     This gives the exact product image when the URL is a real product page.
 *
 *  2. Exa semantic search (EXA_API_KEY required) — finds the canonical product
 *     page for the product name (retailer, manufacturer, review site) and
 *     scrapes its og:image. This succeeds where step 1 fails, e.g. tracking
 *     redirect URLs that return no HTML of their own.
 *
 * The affiliate link itself is NEVER changed — only the image is sourced from Exa.
 */
export async function findProductImage(productName, siteUrl, source) {
  try {
    // Sites whose og:image is always a brand/marketing banner — skip entirely
    if (source === 'travelpayouts' || (siteUrl && BRAND_SITE_PATTERNS.some(p => p.test(siteUrl)))) {
      logger.info(`Skipping image scrape for brand/flight source: ${source} (${siteUrl?.slice(0,40)})`);
      return null;
    }

    // Step 1: scrape affiliate URL directly
    if (siteUrl) {
      const img = await scrapeMetaImage(siteUrl);
      if (img) {
        logger.info(`Affiliate URL image for "${productName}": ${img.slice(0, 80)}`);
        return img;
      }
    }

    // Step 2: Exa semantic search → og:image from canonical product page
    if (process.env.EXA_API_KEY && productName) {
      const urls = await searchProductUrls(productName, 3);
      for (const url of urls) {
        const img = await scrapeMetaImage(url);
        if (img) {
          logger.info(`Exa image for "${productName}": ${img.slice(0, 80)}`);
          return img;
        }
      }
    }

    logger.info(`No image found for "${productName}"`);
    return null;
  } catch (err) {
    logger.warn(`findProductImage error: ${err.message}`);
    return null;
  }
}
