import fetch from 'node-fetch';
import { logger } from '../utils/logger.js';

const EXA_API = 'https://api.exa.ai/search';

/**
 * Searches Exa for product highlights — real reviews, key features, selling points.
 * Returns a short enrichment string (≤300 chars) to append to the AI prompt,
 * or null if EXA_API_KEY is not set or the search fails.
 */
function safeQuery(name, category) {
  const clean = String(name || '').replace(/[^\w\s\-]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);
  return category && category !== name
    ? `${clean} ${category} review features benefits`
    : `${clean} review features why buy`;
}

export async function getProductHighlights(productName, category) {
  const apiKey = process.env.EXA_API_KEY;
  if (!apiKey) return null;

  const query = safeQuery(productName, category);

  try {
    const res = await fetch(EXA_API, {
      method: 'POST',
      headers: {
        'x-api-key': apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        type: 'auto',
        numResults: 3,
        contents: {
          highlights: true,
        },
      }),
      signal: AbortSignal.timeout(10_000),
    });

    if (!res.ok) {
      const text = await res.text();
      logger.warn(`Exa search failed ${res.status}: ${text.slice(0, 100)}`);
      return null;
    }

    const data = await res.json();
    const highlights = (data.results || [])
      .flatMap(r => r.highlights || [])
      .filter(h => h && typeof h === 'string' && h.length > 20)
      .slice(0, 3)
      .join(' ');

    if (!highlights) return null;

    const trimmed = highlights.slice(0, 300);
    logger.info(`Exa highlights for "${productName}": ${trimmed.slice(0, 80)}…`);
    return trimmed;
  } catch (err) {
    logger.warn(`Exa search error: ${err.message}`);
    return null;
  }
}
