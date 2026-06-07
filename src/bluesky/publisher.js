import { getBskyAgent, invalidateAgent } from './client.js';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

function isValidHttpUrl(str) {
  try {
    const u = new URL(str);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

function buildAltText(product) {
  if (!product) return 'Product image';
  const parts = [];
  if (product.name)        parts.push(product.name.trim());
  if (product.category && product.category !== product.name)
                           parts.push(product.category.trim());
  if (product.price)       parts.push(`$${product.price} ${product.currency || 'USD'}`);
  if (product.description && product.description !== product.name)
                           parts.push(product.description.trim().slice(0, 120));
  return parts.join(' · ').slice(0, 999) || 'Product image';
}

async function uploadImageBlob(agentRef, imageBuffer, altText) {
  try {
    const upload = await agentRef.uploadBlob(imageBuffer, { encoding: 'image/png' });
    logger.info(`Image blob uploaded: ${upload.data.blob.ref}`);
    return { $type: 'app.bsky.embed.images', images: [{ image: upload.data.blob, alt: altText }] };
  } catch (err) {
    if (!/deleted|revoked|expired/i.test(err.message)) {
      logger.warn(`Image upload failed: ${err.message}. Posting without image.`);
      return null;
    }
    logger.warn(`Image upload session error: ${err.message} — re-authenticating`);
    invalidateAgent();
    try {
      const fresh = await getBskyAgent();
      const upload = await fresh.uploadBlob(imageBuffer, { encoding: 'image/png' });
      logger.info(`Image blob uploaded after re-auth: ${upload.data.blob.ref}`);
      return { $type: 'app.bsky.embed.images', images: [{ image: upload.data.blob, alt: altText }] };
    } catch (err2) {
      logger.warn(`Image upload failed after re-auth: ${err2.message}. Posting without image.`);
      return null;
    }
  }
}

function buildPostRecord(text, deeplink, maxLen) {
  const combined      = `${text}\n\n${deeplink}`;
  const combinedBytes = Buffer.from(combined, 'utf8');
  const truncated     = combinedBytes.slice(0, maxLen).toString('utf8');
  const prefixBytes   = Buffer.byteLength(text + '\n\n', 'utf8');
  const linkStart     = prefixBytes;
  const linkEnd       = Math.min(prefixBytes + Buffer.byteLength(deeplink, 'utf8'), Buffer.byteLength(truncated, 'utf8'));
  return {
    $type: 'app.bsky.feed.post',
    text: truncated,
    createdAt: new Date().toISOString(),
    facets: linkStart < linkEnd
      ? [{ index: { byteStart: linkStart, byteEnd: linkEnd }, features: [{ $type: 'app.bsky.richtext.facet#link', uri: deeplink }] }]
      : [],
  };
}

async function postWithRetry(record) {
  let currentAgent = await getBskyAgent();
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const result = await currentAgent.post(record);
      logger.info(`Post published: ${result.uri}`);
      return result.uri;
    } catch (err) {
      logger.warn(`Bluesky post attempt ${attempt} failed: ${err.message}`);
      if (/deleted|revoked|expired/i.test(err.message)) {
        invalidateAgent();
        try { currentAgent = await getBskyAgent(); } catch {}
      }
      if (attempt < 3) await sleep(attempt * 2000);
      else throw err;
    }
  }
}

export async function publishPost(text, deeplink, imageBuffer, product) {
  const productName = typeof product === 'string' ? product : product?.name;
  const altText = typeof product === 'object' ? buildAltText(product) : `${productName || 'Product image'}`;

  if (!isValidHttpUrl(deeplink)) {
    throw new Error(`publishPost: deeplink is not a valid URL: ${deeplink}`);
  }

  const maxLen = parseInt(process.env.MAX_POST_LENGTH || '300', 10);
  const record = buildPostRecord(text, deeplink, maxLen);

  if (imageBuffer) {
    const agent = await getBskyAgent();
    const embed = await uploadImageBlob(agent, imageBuffer, altText);
    if (embed) record.embed = embed;
  }

  return postWithRetry(record);
}
