import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

/**
 * Attempts to find a product image via LangSearch API, og:image, or first img tag.
 * Returns an HTTPS image URL string, or null if all steps fail.
 */
export async function findProductImage(productName, siteUrl) {
  try {
    // Step 1: LangSearch API
    const apiKey = process.env.LANGSEARCH_API_KEY;
    if (apiKey) {
      try {
        const q = encodeURIComponent(productName + ' product');
        const res = await fetch(`https://langsearch.com/api/v1/search?q=${q}&count=3`, {
          headers: { Authorization: `Bearer ${apiKey}` },
        });
        if (res.ok) {
          const data = await res.json();
          const first = data?.results?.[0];
          const imgUrl = first?.image || first?.url;
          if (imgUrl && typeof imgUrl === 'string' && imgUrl.startsWith('https://')) {
            logger.info(`LangSearch image found for "${productName}": ${imgUrl.slice(0, 80)}`);
            return imgUrl;
          }
        }
      } catch (err) {
        logger.warn(`LangSearch fetch failed: ${err.message}`);
      }
    }

    // Step 2 & 3: Scrape og:image or first img from siteUrl
    if (siteUrl) {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15_000);
        let html;
        try {
          const res = await fetch(siteUrl, { signal: controller.signal });
          html = res.ok ? await res.text() : null;
        } finally {
          clearTimeout(timeout);
        }

        if (html) {
          // Step 2: og:image meta tag
          const ogMatch = html.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i)
            || html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i);
          if (ogMatch?.[1]) {
            logger.info(`og:image found for "${productName}": ${ogMatch[1].slice(0, 80)}`);
            return ogMatch[1];
          }

          // Step 3: first https img src
          const imgMatch = html.match(/<img[^>]+src=["'](https:\/\/[^"']+)["']/i);
          if (imgMatch?.[1]) {
            logger.info(`First img src found for "${productName}": ${imgMatch[1].slice(0, 80)}`);
            return imgMatch[1];
          }
        }
      } catch (err) {
        logger.warn(`Site image scrape failed for ${siteUrl}: ${err.message}`);
      }
    }

    return null;
  } catch (err) {
    logger.warn(`findProductImage unexpected error: ${err.message}`);
    return null;
  }
}
