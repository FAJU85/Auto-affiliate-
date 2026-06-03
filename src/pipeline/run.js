import fetch from 'node-fetch';
import { getTopProduct, buildDeeplink } from '../admitad/products.js';
import { getTopTrends } from '../admitad/trends.js';
import { generatePostText } from '../ai/text.js';
import { findProductImage } from '../ai/imagesearch.js';
import { upscaleImage } from '../ai/upscale.js';
import { publishPost } from '../bluesky/publisher.js';
import { getBskyAgent } from '../bluesky/client.js';
import { recordRun } from '../utils/metrics.js';
import { getDailySpend } from '../utils/budget.js';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

const RATE_LIMIT_WAIT_MS = 2 * 60 * 1000; // 2-minute wait between feed fetch and text gen

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
    // Phase 1 — Fetch product + trends in parallel (canvas phases 2-5)
    const [product, trends] = await Promise.all([
      getTopProduct(),
      getTopTrends(5),
    ]);

    // Payload starts here — single accumulating object (canvas Section 3)
    let payload = {
      ...product,
      _fetchedCount: product._fetchedCount,
      _filteredCount: product._filteredCount,
    };

    runMeta.product = payload.name;
    runMeta.productsFetched = payload._fetchedCount ?? 0;
    runMeta.productsFiltered = payload._filteredCount ?? 0;

    // Phase 2 — Merge trend context (canvas phase 6)
    const trend = trends[0]?.title || '';
    payload = { ...payload, trend };
    runMeta.trend = trend;

    // Phase 3 — Rate limit wait (canvas phase 7: 2-minute delay)
    logger.info(`Rate limit wait: ${RATE_LIMIT_WAIT_MS / 1000}s before text generation`);
    await sleep(RATE_LIMIT_WAIT_MS);

    // Phase 4 — Build deeplink (canvas: tracked affiliate link already in feed)
    const deeplink = await buildDeeplink(payload);
    payload = { ...payload, deeplink };
    logger.info(`Deeplink: ${deeplink}`);

    // Phase 5 — Text generation via DeepSeek (canvas phase 8)
    const caption = await generatePostText(payload, trends);
    payload = { ...payload, caption };
    runMeta.caption = caption;
    runMeta.captionChars = caption.length;

    // Phase 6 — Image acquisition (canvas phases 10-12)
    // Branch: has Admitad logo → use it directly; else → LangSearch / og:image fallback
    let imageBuffer = null;
    let imageSource = 'none';

    const admitadImageUrl = payload.logoUrl;

    if (admitadImageUrl) {
      logger.info(`Direct image: ${admitadImageUrl.slice(0, 80)}`);
      imageBuffer = await downloadImage(admitadImageUrl);
      if (imageBuffer) imageSource = 'admitad';
    }

    if (!imageBuffer) {
      logger.info('No Admitad image — trying LangSearch / og:image fallback');
      const fallbackUrl = await findProductImage(payload.name, payload.siteUrl);
      if (fallbackUrl) {
        imageBuffer = await downloadImage(fallbackUrl);
        if (imageBuffer) imageSource = 'langsearch';
      }
    }

    payload = { ...payload, imageBuffer, imageSource };
    runMeta.imageSource = imageSource;

    // Phase 7 — HuggingFace upscaling (canvas phase 13)
    if (imageBuffer) {
      imageBuffer = await upscaleImage(imageBuffer);
      payload = { ...payload, imageBuffer };
    }

    runMeta.imageGenerated = imageBuffer !== null;

    // Phase 8 — Bluesky auth (force refresh every run — canvas phase 14)
    await getBskyAgent(true);

    // Phase 9 — Blob upload + publish (canvas phases 15-17)
    const uri = await publishPost(caption, deeplink, imageBuffer, payload.name);
    payload = { ...payload, postUri: uri };

    runMeta.postUri = uri;
    runMeta.success = true;
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
