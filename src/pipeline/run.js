import fetch from 'node-fetch';
import { getProduct } from '../feeds/index.js';
import { getTopTrends } from '../admitad/trends.js';
import { generatePostText } from '../ai/text.js';
import { findProductImage } from '../ai/imagesearch.js';
import { upscaleImage } from '../ai/upscale.js';
import { publishPost } from '../bluesky/publisher.js';
import { getBskyAgent } from '../bluesky/client.js';
import { recordRun, wasRecentlyPosted } from '../utils/metrics.js';
import { getDailySpend } from '../utils/budget.js';
import { logger } from '../utils/logger.js';
import { getProductHighlights } from '../ai/exa.js';

export async function runPipeline() {
  const startTime = Date.now();
  const runMeta = {
    success: false,
    error: null,
    errorStack: null,
    product: null,
    trend: null,
    caption: null,
    captionChars: 0,
    postUri: null,
    imageSource: 'none',
    imageGenerated: false,
    durationMs: 0,
    dailySpendUsd: 0,
    productsFetched: 0,
    productsFiltered: 0,
  };

  logger.info('=== Pipeline v2 run starting ===');

  try {
    // Phase 1 — Fetch product + trends in parallel
    const [product, trends] = await Promise.all([
      getProduct(),
      getTopTrends(5),
    ]);

    // Payload starts here — single accumulating object
    let payload = { ...product };

    runMeta.product = payload.name;
    runMeta.productsFetched = 1;
    runMeta.productsFiltered = 1;

    // Phase 2 — Merge trend context
    const trend = trends[0]?.title || '';
    payload = { ...payload, trend };
    runMeta.trend = trend;

    // Phase 3 — Affiliate URL + duplicate check
    const deeplink = payload.siteUrl;
    payload = { ...payload, deeplink };
    logger.info(`Affiliate URL (deeplink): ${deeplink}`);

    if (wasRecentlyPosted(deeplink, payload.name)) {
      logger.warn(`Duplicate suppressed — "${payload.name}" was already posted in the last 60 days`);
      runMeta.error = 'duplicate_suppressed';
      runMeta.durationMs = Date.now() - startTime;
      recordRun(runMeta);
      return runMeta;
    }

    // Phase 4b — Exa product context (enriches AI caption, best-effort)
    const exaHighlights = await getProductHighlights(payload.name, payload.category);
    if (exaHighlights) payload = { ...payload, exaHighlights };

    // Phase 5 — Text generation
    const caption = await generatePostText(payload, trends);
    payload = { ...payload, caption };
    runMeta.caption = caption;
    runMeta.captionChars = caption.length;

    // Phase 6 — Image acquisition
    // Branch: has feed image → use it directly; else → og:image from product page
    let imageBuffer = null;
    let imageSource = 'none';

    const feedImageUrl = payload.imageUrl || null;

    if (feedImageUrl) {
      logger.info(`Direct image from feed: ${feedImageUrl.slice(0, 80)}`);
      imageBuffer = await downloadImage(feedImageUrl);
      if (imageBuffer) imageSource = payload.source || 'feed';
    }

    if (!imageBuffer) {
      logger.info('No feed image — trying og:image from product page');
      const fallbackUrl = await findProductImage(payload.name, payload.siteUrl, payload.source);
      if (fallbackUrl) {
        imageBuffer = await downloadImage(fallbackUrl);
        if (imageBuffer) imageSource = 'og:image';
      }
    }

    payload = { ...payload, imageBuffer, imageSource };
    runMeta.imageSource = imageSource;

    // Phase 7 — HuggingFace upscaling
    if (imageBuffer) {
      imageBuffer = await upscaleImage(imageBuffer);
      payload = { ...payload, imageBuffer };
    }

    runMeta.imageGenerated = imageBuffer !== null;

    // Phase 8 — Bluesky auth (reuse persisted session, login only when needed)
    await getBskyAgent();

    // Phase 9 — Blob upload + publish (canvas phases 15-17)
    const uri = await publishPost(caption, deeplink, imageBuffer, payload);
    payload = { ...payload, postUri: uri };

    runMeta.postUri  = uri;
    runMeta.deeplink = deeplink;
    runMeta.success  = true;
    logger.info(`=== Pipeline v2 complete. Post: ${uri} ===`);
  } catch (err) {
    runMeta.error = err.message;
    runMeta.errorStack = err.stack?.split('\n').slice(0, 5).join(' | ') || null;
    logger.error(`Pipeline failed: ${err.message}`);
  }

  runMeta.durationMs = Date.now() - startTime;
  runMeta.dailySpendUsd = getDailySpend();
  recordRun(runMeta);
  return runMeta;
}

async function downloadImage(url) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);
    let res;
    try {
      res = await fetch(url, { signal: controller.signal });
    } finally {
      clearTimeout(timeout);
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    logger.info(`Image downloaded: ${buf.length} bytes from ${url.slice(0, 60)}`);
    return buf;
  } catch (err) {
    logger.warn(`Image download failed (${url.slice(0, 60)}): ${err.message}`);
    return null;
  }
}
