import fetch from 'node-fetch';
import { getProduct } from '../feeds/index.js';
import { getTopTrends } from '../admitad/trends.js';
import { generatePostText } from '../ai/text.js';
import { findProductImage } from '../ai/imagesearch.js';
import { upscaleImage } from '../ai/upscale.js';
import { optimiseImage } from '../ai/imageoptim.js';
import { publishPost } from '../bluesky/publisher.js';
import { getBskyAgent } from '../bluesky/client.js';
import { recordRun, wasRecentlyPosted, recordEngagement } from '../utils/metrics.js';
import { getDailySpend } from '../utils/budget.js';
import { logger } from '../utils/logger.js';
import { getProductHighlights } from '../ai/exa.js';

async function downloadImage(url) {
  try {
    const controller = new AbortController();
    const timeout    = setTimeout(() => controller.abort(), 30_000);
    let res;
    try {
      res = await fetch(url, { signal: controller.signal });
    } finally {
      clearTimeout(timeout);
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const ct = res.headers.get('content-type') || '';
    if (!ct.startsWith('image/')) throw new Error(`Not an image (content-type: ${ct})`);
    const buf = Buffer.from(await res.arrayBuffer());
    logger.info(`Image downloaded: ${buf.length} bytes (${ct}) from ${url.slice(0, 60)}`);
    return buf;
  } catch (err) {
    logger.warn(`Image download failed (${url.slice(0, 60)}): ${err.message}`);
    return null;
  }
}

async function acquireImage(payload) {
  const feedUrl = payload.imageUrl || null;
  if (feedUrl) {
    logger.info(`Direct image from feed: ${feedUrl.slice(0, 80)}`);
    const buf = await downloadImage(feedUrl);
    if (buf) return { imageBuffer: buf, imageSource: payload.source || 'feed' };
  }
  logger.info('No feed image — trying og:image from product page');
  const fallbackUrl = await findProductImage(payload.name, payload.siteUrl, payload.source);
  if (fallbackUrl) {
    const buf = await downloadImage(fallbackUrl);
    if (buf) return { imageBuffer: buf, imageSource: 'og:image' };
  }
  return { imageBuffer: null, imageSource: 'none' };
}

function initRunMeta() {
  return {
    success: false, error: null, errorStack: null,
    product: null, productSource: null, trend: null, caption: null, captionChars: 0,
    postUri: null, deeplink: null, imageSource: 'none', imageGenerated: false,
    durationMs: 0, dailySpendUsd: 0, productsFetched: 0, productsFiltered: 0,
  };
}

async function executePost(runMeta) {
  const [product, trends] = await Promise.all([getProduct(wasRecentlyPosted), getTopTrends(5)]);
  let payload = { ...product, trend: trends[0]?.title || '', deeplink: product.siteUrl };
  runMeta.product       = payload.name;
  runMeta.productSource = payload.source || null;
  runMeta.trend         = payload.trend;
  runMeta.productsFetched  = 1;
  runMeta.productsFiltered = 1;
  logger.info(`Affiliate URL (deeplink): ${payload.deeplink}`);

  const exaHighlights = await getProductHighlights(payload.name, payload.category);
  if (exaHighlights) payload = { ...payload, exaHighlights };

  const caption = await generatePostText(payload, trends);
  payload = { ...payload, caption };
  runMeta.caption      = caption;
  runMeta.captionChars = caption.length;
  logger.info(`Caption (${caption.length} chars): ${caption.slice(0, 100)}${caption.length > 100 ? '…' : ''}`);

  const { imageBuffer: rawImage, imageSource } = await acquireImage(payload);
  const upscaled    = rawImage ? await upscaleImage(rawImage) : null;
  const imageBuffer = upscaled ? await optimiseImage(upscaled) : null;
  runMeta.imageSource    = imageSource;
  runMeta.imageGenerated = imageBuffer !== null;

  await getBskyAgent();
  const uri = await publishPost(caption, payload.deeplink, imageBuffer, payload);
  runMeta.postUri  = uri;
  runMeta.deeplink = payload.deeplink;
  runMeta.success  = true;
  logger.info(`=== Pipeline v2 complete. Post: ${uri} ===`);
}

const PIPELINE_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes max per run

export async function runPipeline() {
  const startTime = Date.now();
  const runMeta   = initRunMeta();
  logger.info('=== Pipeline v2 run starting ===');
  try {
    await Promise.race([
      executePost(runMeta),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Pipeline timeout after 5 minutes')), PIPELINE_TIMEOUT_MS)
      ),
    ]);
  } catch (err) {
    runMeta.error      = err.message;
    runMeta.errorStack = err.stack?.split('\n').slice(0, 5).join(' | ') || null;
    logger.error(`Pipeline failed: ${err.message}`);
  }
  runMeta.durationMs    = Date.now() - startTime;
  runMeta.dailySpendUsd = getDailySpend();
  recordRun(runMeta);
  notifyWebhook(runMeta);
  if (runMeta.success && runMeta.postUri) {
    // Fire-and-forget engagement poll after 30 min
    pollEngagement(runMeta.postUri).catch(() => {});
  }
  return runMeta;
}

async function pollEngagement(uri) {
  if (!uri) return;
  // Wait 30 minutes then check likes/reposts once
  await new Promise(r => setTimeout(r, 30 * 60 * 1000));
  try {
    const agent = await getBskyAgent();
    // getPostThread returns the post with like/repost counts
    const thread = await agent.getPostThread({ uri, depth: 0 });
    const post = thread?.data?.thread?.post;
    if (post) {
      const likes   = post.likeCount   || 0;
      const reposts = post.repostCount || 0;
      recordEngagement(uri, likes, reposts);
      logger.info(`Engagement for ${uri.slice(-20)}: ${likes} likes, ${reposts} reposts`);
    }
  } catch (err) {
    logger.warn(`Engagement poll failed for ${uri.slice(-20)}: ${err.message}`);
  }
}

function notifyWebhook(runMeta) {
  const url = process.env.WEBHOOK_URL;
  if (!url) return;
  const payload = {
    success: runMeta.success,
    product: runMeta.product,
    source:  runMeta.productSource,
    postUri: runMeta.postUri,
    error:   runMeta.error || null,
    durationMs: runMeta.durationMs,
    ts: new Date().toISOString(),
  };
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(10_000),
  }).then(r => {
    if (!r.ok) logger.warn(`Webhook delivery failed: HTTP ${r.status}`);
    else logger.info(`Webhook delivered: ${url.slice(0, 60)}`);
  }).catch(err => {
    logger.warn(`Webhook error: ${err.message}`);
  });
}
