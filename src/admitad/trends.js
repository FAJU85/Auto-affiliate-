import Parser from 'rss-parser';
import { logger } from '../utils/logger.js';

const parser = new Parser();

export async function getTopTrends(limit = 5) {
  const url = process.env.TRENDS_RSS_URL || 'https://trends.google.com/trending/rss?geo=US';

  try {
    const feed = await parser.parseURL(url);
    const items = (feed.items || []).slice(0, limit).map(item => ({
      title: item.title,
      traffic: item['ht:approx_traffic'] || item.content || '',
    }));
    logger.info(`Trends fetched: ${items.map(i => i.title).join(', ')}`);
    return items;
  } catch (err) {
    logger.warn(`Trends fetch failed: ${err.message}. Proceeding without trend context.`);
    return [];
  }
}
