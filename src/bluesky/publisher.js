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
    const upload = await agentRef.uploadBlob(imageBuffer, { encoding: 'image/jpeg' });
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
      const upload = await fresh.uploadBlob(imageBuffer, { encoding: 'image/jpeg' });
      logger.info(`Image blob uploaded after re-auth: ${upload.data.blob.ref}`);
      return { $type: 'app.bsky.embed.images', images: [{ image: upload.data.blob, alt: altText }] };
    } catch (err2) {
      logger.warn(`Image upload failed after re-auth: ${err2.message}. Posting without image.`);
      return null;
    }
  }
}

function safeByteSlice(str, maxBytes) {
  const buf = Buffer.from(str, 'utf8');
  if (buf.length <= maxBytes) return str;
  // Walk back from maxBytes until we land on a valid UTF-8 sequence boundary
  let end = maxBytes;
  while (end > 0 && (buf[end] & 0xc0) === 0x80) end--;
  return buf.slice(0, end).toString('utf8');
}

const SOURCE_EMOJI = {
  travelpayouts:    '✈️',
  temu:             '🛍️',
  cj:               '🏷️',
  shareasale:       '🎁',
  impact:           '⭐',
  takeads:          '💼',
  admitad:          '🛒',
  'admitad-catalog':'🛒',
  'admitad-api':    '🛒',
};

export function sourceEmoji(source) {
  return SOURCE_EMOJI[source] || '🔗';
}

function buildPostRecord(text, deeplink, maxLen) {
  const combined    = `${text}\n\n${deeplink}`;
  const truncated   = safeByteSlice(combined, maxLen);
  const prefixBytes = Buffer.byteLength(text + '\n\n', 'utf8');
  const linkStart   = prefixBytes;
  const linkEnd     = Math.min(prefixBytes + Buffer.byteLength(deeplink, 'utf8'), Buffer.byteLength(truncated, 'utf8'));
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
      // Bluesky rate-limit: response may include Retry-After or status 429
      const isRateLimit = /rate.?limit|429/i.test(err.message);
      const waitMs = isRateLimit ? 30_000 : attempt * 2000;
      if (attempt < 3) await sleep(waitMs);
      else throw err;
    }
  }
}

function buildExternalEmbed(product, deeplink) {
  if (typeof product !== 'object' || !product) return null;
  const priceTag = product.price ? ` — ${product.currency === 'USD' ? '$' : product.currency || ''}${product.price}` : '';
  const title = ((product.name || '') + priceTag).slice(0, 300);
  const desc  = (product.description || product.name || '').slice(0, 300);
  return {
    $type: 'app.bsky.embed.external',
    external: { uri: deeplink, title, description: desc, thumb: undefined },
  };
}

export async function publishPost(text, deeplink, imageBuffer, product) {
  const productName = typeof product === 'string' ? product : product?.name;
  const altText = typeof product === 'object' ? buildAltText(product) : `${productName || 'Product image'}`;
  const source  = typeof product === 'object' ? product?.source : null;
  const emoji   = sourceEmoji(source);
  const prefixed = text.startsWith(emoji) ? text : `${emoji} ${text}`;

  if (!isValidHttpUrl(deeplink)) {
    throw new Error(`publishPost: deeplink is not a valid URL: ${deeplink}`);
  }

  // Bluesky facet URIs have a practical length limit
  const truncatedDeeplink = deeplink.length > 2048 ? deeplink.slice(0, 2048) : deeplink;

  const maxLen = parseInt(process.env.MAX_POST_LENGTH || '300', 10);
  const record = buildPostRecord(prefixed, truncatedDeeplink, maxLen);

  if (imageBuffer) {
    const agent = await getBskyAgent();
    const embed = await uploadImageBlob(agent, imageBuffer, altText);
    if (embed) record.embed = embed;
  } else {
    const extEmbed = buildExternalEmbed(product, truncatedDeeplink);
    if (extEmbed) record.embed = extEmbed;
  }

  return postWithRetry(record);
}
