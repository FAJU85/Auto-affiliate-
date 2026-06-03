import { getBskyAgent } from './client.js';
import { logger } from '../utils/logger.js';

/**
 * Publishes an affiliate post to Bluesky.
 * Uploads image blob if provided, then creates the post record.
 * Returns the published post URI.
 */
export async function publishPost(text, deeplink, imageBuffer) {
  const agent = await getBskyAgent();
  const maxLen = parseInt(process.env.MAX_POST_LENGTH || '300', 10);

  // Truncate text to leave room for URL
  const urlDisplay = deeplink.length > 30 ? deeplink.slice(0, 27) + '...' : deeplink;
  const bodyText = `${text}\n\n${urlDisplay}`.slice(0, maxLen);
  const fullText = `${text}\n\n${deeplink}`;

  // Build facets for the URL (rich text link)
  const linkStart = Buffer.byteLength(text + '\n\n', 'utf8');
  const linkEnd = Buffer.byteLength(fullText, 'utf8');

  const postRecord = {
    $type: 'app.bsky.feed.post',
    text: fullText.slice(0, maxLen),
    createdAt: new Date().toISOString(),
    facets: [
      {
        index: { byteStart: linkStart, byteEnd: Math.min(linkEnd, Buffer.byteLength(fullText.slice(0, maxLen), 'utf8')) },
        features: [{ $type: 'app.bsky.richtext.facet#link', uri: deeplink }],
      },
    ],
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
            alt: 'Product image',
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
