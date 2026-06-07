import { getBskyAgent, invalidateAgent } from './client.js';
import { logger } from '../utils/logger.js';
import { sleep } from '../utils/sleep.js';

/**
 * Publishes an affiliate post to Bluesky.
 * Uploads image blob if provided, then creates the post record.
 * Returns the published post URI.
 */
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

export async function publishPost(text, deeplink, imageBuffer, product) {
  // Accept either a product object or a plain name string (backwards compat)
  const productName = typeof product === 'string' ? product : product?.name;
  const altText = typeof product === 'object' ? buildAltText(product) : `${productName || 'Product image'}`;

  if (!isValidHttpUrl(deeplink)) {
    throw new Error(`publishPost: deeplink is not a valid URL: ${deeplink}`);
  }

  const agent = await getBskyAgent();
  const maxLen = parseInt(process.env.MAX_POST_LENGTH || '300', 10);

  // Build combined text, then truncate by byte length to respect Bluesky's limit
  const combined = `${text}\n\n${deeplink}`;
  const combinedBytes = Buffer.from(combined, 'utf8');
  const truncatedBytes = combinedBytes.slice(0, maxLen);
  const truncated = truncatedBytes.toString('utf8');

  // Facet indices are byte offsets into the final truncated text
  const prefixBytes = Buffer.byteLength(text + '\n\n', 'utf8');
  const linkStart = prefixBytes;
  const linkEnd = Math.min(prefixBytes + Buffer.byteLength(deeplink, 'utf8'), truncatedBytes.length);

  const postRecord = {
    $type: 'app.bsky.feed.post',
    text: truncated,
    createdAt: new Date().toISOString(),
    facets: linkStart < linkEnd
      ? [{ index: { byteStart: linkStart, byteEnd: linkEnd }, features: [{ $type: 'app.bsky.richtext.facet#link', uri: deeplink }] }]
      : [],
  };

  // Upload image if we have one
  if (imageBuffer) {
    try {
      const upload = await agent.uploadBlob(imageBuffer, { encoding: 'image/png' });
      postRecord.embed = {
        $type: 'app.bsky.embed.images',
        images: [{ image: upload.data.blob, alt: altText }],
      };
      logger.info(`Image blob uploaded: ${upload.data.blob.ref}`);
    } catch (err) {
      if (/deleted|revoked|expired/i.test(err.message)) {
        logger.warn(`Image upload session error: ${err.message} — re-authenticating`);
        invalidateAgent();
        try {
          const freshAgent = await getBskyAgent();
          const upload = await freshAgent.uploadBlob(imageBuffer, { encoding: 'image/png' });
          postRecord.embed = {
            $type: 'app.bsky.embed.images',
            images: [{ image: upload.data.blob, alt: altText }],
          };
          logger.info(`Image blob uploaded after re-auth: ${upload.data.blob.ref}`);
        } catch (err2) {
          logger.warn(`Image upload failed after re-auth: ${err2.message}. Posting without image.`);
        }
      } else {
        logger.warn(`Image upload failed: ${err.message}. Posting without image.`);
      }
    }
  }

  let currentAgent = agent;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const result = await currentAgent.post(postRecord);
      logger.info(`Post published: ${result.uri}`);
      return result.uri;
    } catch (err) {
      logger.warn(`Bluesky post attempt ${attempt} failed: ${err.message}`);
      if (/deleted|revoked|expired/i.test(err.message)) {
        // Session invalidated — clear cache and re-authenticate before retry
        invalidateAgent();
        try { currentAgent = await getBskyAgent(); } catch {}
      }
      if (attempt < 3) await sleep(attempt * 2000);
      else throw err;
    }
  }
}

