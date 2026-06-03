import { getBskyAgent } from './client.js';
import { logger } from '../utils/logger.js';

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

export async function publishPost(text, deeplink, imageBuffer, productName) {
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
        images: [
          {
            image: upload.data.blob,
            alt: productName ? `Product image: ${productName}`.slice(0, 300) : 'Product image',
          },
        ],
      };
      logger.info(`Image blob uploaded: ${upload.data.blob.ref}`);
    } catch (err) {
      logger.warn(`Image upload failed: ${err.message}. Posting without image.`);
    }
  }

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const result = await agent.post(postRecord);
      logger.info(`Post published: ${result.uri}`);
      return result.uri;
    } catch (err) {
      logger.warn(`Bluesky post attempt ${attempt} failed: ${err.message}`);
      if (attempt < 3) await sleep(attempt * 2000);
      else throw err;
    }
  }
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
