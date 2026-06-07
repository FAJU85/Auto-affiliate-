import Parser from 'rss-parser';
import { logger } from '../utils/logger.js';

const parser = new Parser({ timeout: 10_000 });

export async function getTopTrends(limit = 5) {
  const url = process.env.TRENDS_RSS_URL || 'https://trends.google.com/trending/rss?geo=US';

  try {
    const feed = await parser.parseURL(url);
    const items = (feed.items || [])
      .slice(0, limit)
      .map(item => ({
        title: (item.title || '').slice(0, 100),
        traffic: item['ht:approx_traffic'] || item.content || '',
      }))
      .filter(item => item.title.length > 0);
    logger.info(`Trends fetched: ${items.map(i => i.title).join(', ')}`);
    return items;
  } catch (err) {
    logger.warn(`Trends fetch failed: ${err.message}. Proceeding without trend context.`);
    return [];
  }
}
