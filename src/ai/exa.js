import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const EXA_API = 'https://api.exa.ai/search';

/**
 * Search Exa for URLs matching the product name.
 * Returns up to numResults page URLs, or [] on failure.
 * Used by imagesearch.js to find canonical product pages for og:image scraping.
 */
export async function searchProductUrls(productName, numResults = 3) {
  const apiKey = process.env.EXA_API_KEY;
  if (!apiKey) return [];

  const query = String(productName || '')
    .replace(/[^\w\s\-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80) + ' product page';

  try {
    const res = await fetch(EXA_API, {
      method: 'POST',
      headers: { 'x-api-key': apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        type: 'auto',
        numResults,
        contents: { text: false },
      }),
      signal: AbortSignal.timeout(10_000),
    });

    if (!res.ok) {
      logger.warn(`Exa search failed ${res.status}`);
      return [];
    }

    const data = await res.json();
    const urls = (data.results || []).map(r => r.url).filter(u => u?.startsWith('https://'));
    logger.info(`Exa found ${urls.length} URLs for "${productName.slice(0, 40)}"`);
    return urls;
  } catch (err) {
    logger.warn(`Exa search error: ${err.message}`);
    return [];
  }
}
