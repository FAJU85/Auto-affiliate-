/**
 * SOVRN Commerce (VigLink) feed + link monetizer.
 *
 * SOVRN Commerce wraps any merchant URL into a tracked affiliate link.
 * This module does two things:
 *
 * 1. monetizeUrl(url)  — converts any merchant URL to a SOVRN affiliate link
 * 2. getSovrnProduct() — picks a curated product URL and returns it monetized,
 *                        for use in the pipeline when SOVRN_API_KEY is set.
 *
 * Env vars:
 *   SOVRN_API_KEY  — your SOVRN/VigLink publisher key
 */

import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const VIGLINK_KEY = () => process.env.SOVRN_API_KEY || '';
const API_BASE    = 'https://api.viglink.com/api';

// ── Curated rotating product list ─────────────────────────────────────────────
// Popular merchant URLs that SOVRN supports well. The pipeline picks one at
// random on each run, then wraps it through the SOVRN API to get a tracked link.

const PRODUCT_POOL = [
  // Electronics
  { name: 'Sony WH-1000XM5 Noise Cancelling Headphones',     url: 'https://www.amazon.com/dp/B09XS7JWHH',   price: 279.99, currency: 'USD', category: 'Electronics', imageSearch: 'Sony WH-1000XM5 headphones' },
  { name: 'Apple AirPods Pro (2nd Generation)',               url: 'https://www.amazon.com/dp/B0BDHWDR12',   price: 189.99, currency: 'USD', category: 'Electronics', imageSearch: 'Apple AirPods Pro 2nd gen' },
  { name: 'Anker 737 Power Bank 24000mAh',                    url: 'https://www.amazon.com/dp/B09VPHVT2Z',   price: 75.99,  currency: 'USD', category: 'Electronics', imageSearch: 'Anker 737 power bank' },
  { name: 'Logitech MX Master 3S Wireless Mouse',             url: 'https://www.amazon.com/dp/B09HM94VDS',   price: 89.99,  currency: 'USD', category: 'Electronics', imageSearch: 'Logitech MX Master 3S mouse' },
  { name: 'Samsung T7 Portable SSD 1TB',                      url: 'https://www.amazon.com/dp/B0874XN4D8',   price: 89.99,  currency: 'USD', category: 'Electronics', imageSearch: 'Samsung T7 portable SSD' },
  { name: 'Kindle Paperwhite 16GB E-Reader',                  url: 'https://www.amazon.com/dp/B09TMF6742',   price: 139.99, currency: 'USD', category: 'Electronics', imageSearch: 'Kindle Paperwhite e-reader' },
  { name: 'Philips Hue Smart Bulb Starter Kit',               url: 'https://www.amazon.com/dp/B07353SKDD',   price: 69.99,  currency: 'USD', category: 'Smart Home',   imageSearch: 'Philips Hue starter kit' },
  // Beauty & Health
  { name: 'CeraVe Moisturising Cream 454g',                   url: 'https://www.amazon.com/dp/B00TTD9BRC',   price: 19.99,  currency: 'USD', category: 'Beauty',       imageSearch: 'CeraVe moisturizing cream' },
  { name: 'Dyson Airwrap Multi-Styler',                        url: 'https://www.amazon.com/dp/B07G5B76KP',   price: 549.99, currency: 'USD', category: 'Beauty',       imageSearch: 'Dyson Airwrap multi-styler' },
  { name: 'Oral-B Smart 5000 Electric Toothbrush',            url: 'https://www.amazon.com/dp/B00V6NHQKQ',   price: 89.99,  currency: 'USD', category: 'Health',       imageSearch: 'Oral-B electric toothbrush' },
  // Home & Kitchen
  { name: 'Instant Pot Duo 7-in-1 Pressure Cooker 6qt',       url: 'https://www.amazon.com/dp/B00FLYWNYQ',   price: 79.99,  currency: 'USD', category: 'Home',         imageSearch: 'Instant Pot Duo 7-in-1' },
  { name: 'Ninja AF101 Air Fryer 4qt',                         url: 'https://www.amazon.com/dp/B07FDJMC9Q',   price: 79.99,  currency: 'USD', category: 'Home',         imageSearch: 'Ninja air fryer' },
  { name: 'Ring Video Doorbell (4th Gen)',                     url: 'https://www.amazon.com/dp/B08N5NQ869',   price: 99.99,  currency: 'USD', category: 'Smart Home',   imageSearch: 'Ring video doorbell 4th gen' },
  // Fashion
  { name: 'Levi\'s 501 Original Fit Jeans',                   url: 'https://www.amazon.com/dp/B0079E7N4A',   price: 59.99,  currency: 'USD', category: 'Fashion',      imageSearch: "Levi's 501 original fit jeans" },
  { name: 'Under Armour Men\'s Tech 2.0 Short Sleeve T-Shirt',url: 'https://www.amazon.com/dp/B01N39FHYB',   price: 25.99,  currency: 'USD', category: 'Fashion',      imageSearch: 'Under Armour tech shirt' },
  // Fitness
  { name: 'Fitbit Charge 6 Fitness Tracker',                  url: 'https://www.amazon.com/dp/B0CLKTSSZ4',   price: 149.95, currency: 'USD', category: 'Fitness',      imageSearch: 'Fitbit Charge 6 fitness tracker' },
  { name: 'Hydro Flask 32oz Water Bottle',                     url: 'https://www.amazon.com/dp/B01ACAX6WI',   price: 44.95,  currency: 'USD', category: 'Fitness',      imageSearch: 'Hydro Flask water bottle' },
];

// ── Link monetizer ─────────────────────────────────────────────────────────────

/**
 * Converts any merchant URL to a SOVRN/VigLink affiliate link.
 * Returns original URL if the API call fails or key is not set.
 */
export async function monetizeUrl(merchantUrl) {
  const key = VIGLINK_KEY();
  if (!key || !merchantUrl) return merchantUrl;

  try {
    const encoded = encodeURIComponent(merchantUrl);
    const apiUrl  = `${API_BASE}/link?key=${key}&u=${encoded}&ref=https%3A%2F%2Fbluesky.app`;
    const res = await fetch(apiUrl, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(8_000),
    });

    if (!res.ok) {
      logger.warn(`SOVRN link API ${res.status} for ${merchantUrl.slice(0, 60)}`);
      return merchantUrl;
    }

    const data = await res.json();
    const monetized = data?.url || merchantUrl;
    logger.info(`SOVRN monetized: ${merchantUrl.slice(0, 50)} → ${monetized.slice(0, 60)}`);
    return monetized;
  } catch (err) {
    logger.warn(`SOVRN monetize failed: ${err.message}`);
    return merchantUrl;
  }
}

/**
 * Returns a monetized product from the SOVRN curated pool.
 * Used as a standalone feed in the pipeline.
 */
export async function getSovrnProduct() {
  const key = VIGLINK_KEY();
  if (!key) return null;

  // Pick a random product, shuffled to avoid repetition
  const product = PRODUCT_POOL[Math.floor(Math.random() * PRODUCT_POOL.length)];

  logger.info(`SOVRN Commerce: monetizing "${product.name}"`);

  const deeplink = await monetizeUrl(product.url);
  if (!deeplink || deeplink === product.url) {
    // VigLink returned the same URL — still usable as organic link
    logger.warn(`SOVRN: link unchanged for "${product.name}" — using original`);
  }

  return {
    id:           `sovrn-${Buffer.from(product.url).toString('base64').slice(0, 16)}`,
    name:         product.name,
    description:  product.name,
    siteUrl:      deeplink,
    deeplink,
    imageUrl:     null,
    imageSearch:  product.imageSearch,
    price:        product.price,
    currency:     product.currency,
    category:     product.category,
    source:       'sovrn',
  };
}
