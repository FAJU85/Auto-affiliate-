import { getTopProduct, buildDeeplink } from '../admitad/products.js';
import { getTopTrends } from '../admitad/trends.js';
import { generatePostText } from '../ai/text.js';
import { generateProductImage } from '../ai/image.js';
import { publishPost } from '../bluesky/publisher.js';
import { recordRun } from '../utils/metrics.js';
import { getDailySpend } from '../utils/budget.js';
import { logger } from '../utils/logger.js';

export async function runPipeline() {
  const startTime = Date.now();
  const runMeta = {
    success: false,
    error: null,
    product: null,
    postUri: null,
    durationMs: 0,
    dailySpendUsd: 0,
    productsFetched: 0,
    productsFiltered: 0,
    imageGenerated: false,
  };

  logger.info('=== Pipeline run starting ===');

  try {
    // 1. Fetch product + trends in parallel
    const [product, trends] = await Promise.all([
      getTopProduct(),
      getTopTrends(5),
    ]);
    runMeta.product = product.name;
    runMeta.productsFiltered = product._filteredCount ?? 0;
    runMeta.productsFetched = product._fetchedCount ?? 0;

    // 2. Build trackable deeplink
    const deeplink = await buildDeeplink(product);
    logger.info(`Deeplink: ${deeplink}`);

    // 3. Generate text (Llama 3 / HF)
    const postText = await generatePostText(product, trends);

    // 4. Generate image (DALL-E 3) — non-blocking on failure
    const imageBuffer = await generateProductImage(product);
    runMeta.imageGenerated = imageBuffer !== null;

    // 5. Publish to Bluesky
    const uri = await publishPost(postText, deeplink, imageBuffer, product.name);
    runMeta.postUri = uri;
    runMeta.success = true;

    logger.info(`=== Pipeline complete. Post: ${uri} ===`);
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
