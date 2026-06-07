/**
 * Normalises an AliExpress product URL so it opens correctly in both
 * the mobile app and the browser.
 *
 * Problem: Admitad redirect chains end on an aliexpress.com URL that
 * contains affiliate/tracking query params. iOS/Android hands those
 * URLs to the AliExpress app via universal links, but the app only
 * recognises a small set of its own parameters — extra ones cause a
 * blank screen.
 *
 * Fix: rebuild the URL as a clean /item/ITEM_ID.html path with only
 * the parameters AliExpress's app needs, then re-wrap in Admitad's
 * deeplink so affiliate attribution is preserved.
 */

const AE_HOSTS = /(?:^|\.)aliexpress\.com$/i;

/**
 * Returns true if url is an AliExpress product page.
 */
export function isAliExpressUrl(url) {
  try {
    return AE_HOSTS.test(new URL(url).hostname);
  } catch {
    return false;
  }
}

/**
 * Normalises an AliExpress URL for app-compatible deep linking.
 * - Extracts the item ID from any known URL format
 * - Rebuilds as https://www.aliexpress.com/item/ITEM_ID.html
 * - Adds sourceType=620 (tells the app it's a direct product link)
 * - Strips all other tracking / affiliate parameters that confuse the app
 *
 * If the item ID cannot be extracted the original URL is returned unchanged.
 */
export function normaliseAliExpressUrl(url) {
  if (!isAliExpressUrl(url)) return url;

  try {
    const u = new URL(url);

    // Extract item ID from path: /item/1234567890.html
    let itemId = null;

    const pathMatch = u.pathname.match(/\/item\/(\d+)(?:\.html)?/i);
    if (pathMatch) {
      itemId = pathMatch[1];
    }

    // Fallback: some URLs carry the ID in a query param
    if (!itemId) {
      itemId = u.searchParams.get('productId') ||
               u.searchParams.get('item_id') ||
               u.searchParams.get('id');
    }

    if (!itemId) {
      // Can't extract ID — return as-is, just switch to www
      u.hostname = 'www.aliexpress.com';
      return u.toString();
    }

    // Rebuild clean product URL — the only param the app needs is sourceType
    return `https://www.aliexpress.com/item/${itemId}.html?sourceType=620`;
  } catch {
    return url;
  }
}
