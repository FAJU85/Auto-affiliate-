/**
 * Normalises AliExpress URLs buried inside Admitad redirect chains so they
 * open correctly in the AliExpress mobile app.
 *
 * Real URL structure from the Admitad catalog:
 *   rzekl.com/g/...?ulp=
 *     s.click.aliexpress.com/deep_link.htm?aff_short_key=XXX&dl_target_url=
 *       www.aliexpress.com/item/ITEM_ID.html?pdp_npi=6%40dis...
 *
 * Why the app shows blank:
 *   s.click.aliexpress.com is registered as an AliExpress universal link so
 *   the app intercepts it correctly. BUT deep_link.htm passes dl_target_url
 *   full of pdp_npi / tracking junk that the app can't resolve → blank screen.
 *
 * Fix: keep the s.click.aliexpress.com/deep_link.htm layer (the app needs it
 * to open) and keep aff_short_key (AliExpress affiliate attribution), but
 * replace dl_target_url with a clean /item/ITEM_ID.html URL — no extra params.
 */

const AE_HOSTS      = /(?:^|\.)aliexpress\.com$/i;
const ADMITAD_HOSTS = /(?:^|\.)(?:rzekl\.com|admitad\.com)$/i;

export function isAliExpressUrl(url) {
  try { return AE_HOSTS.test(new URL(url).hostname); }
  catch { return false; }
}

function isAdmitadUrl(url) {
  try { return ADMITAD_HOSTS.test(new URL(url).hostname); }
  catch { return false; }
}

/**
 * Extracts the numeric AliExpress item ID from any known URL format.
 */
function extractItemId(url) {
  try {
    const u = new URL(url);

    // Recurse into dl_target_url (s.click.aliexpress.com/deep_link.htm)
    if (u.searchParams.has('dl_target_url')) {
      return extractItemId(u.searchParams.get('dl_target_url'));
    }

    // /item/1234567890.html
    const pathMatch = u.pathname.match(/\/item\/(\d+)/i);
    if (pathMatch) return pathMatch[1];

    return u.searchParams.get('productId')
        || u.searchParams.get('item_id')
        || u.searchParams.get('id')
        || null;
  } catch {
    return null;
  }
}

/**
 * Normalises the ulp inside an Admitad (rzekl.com) redirect:
 *
 * Case A — ulp is s.click.aliexpress.com/deep_link.htm:
 *   Keep the deep_link.htm handler (needed for app to open) and aff_short_key
 *   (AliExpress affiliate attribution), but replace dl_target_url with a clean
 *   /item/ID.html — strips pdp_npi and other junk that causes blank screen.
 *
 * Case B — ulp is a direct aliexpress.com product URL:
 *   Rebuild as clean /item/ID.html (no tracking params).
 *
 * Non-AliExpress ulp values are left unchanged.
 */
function normaliseUlp(ulp) {
  try {
    const u = new URL(ulp);
    if (!AE_HOSTS.test(u.hostname)) return ulp;

    const itemId = extractItemId(ulp);
    if (!itemId) return ulp;

    const cleanTarget = `https://www.aliexpress.com/item/${itemId}.html`;

    // Case A: s.click deep_link.htm — rebuild keeping aff_short_key
    if (u.searchParams.has('dl_target_url')) {
      const rebuilt = new URL('https://s.click.aliexpress.com/deep_link.htm');
      const affKey = u.searchParams.get('aff_short_key');
      if (affKey) rebuilt.searchParams.set('aff_short_key', affKey);
      rebuilt.searchParams.set('dl_target_url', cleanTarget);
      return rebuilt.toString();
    }

    // Case B: direct aliexpress.com URL
    return cleanTarget;
  } catch {
    return ulp;
  }
}

/**
 * Main entry point. Pass any URL — Admitad wrapper, s.click, or direct.
 * Returns the normalised URL safe for both browser and AliExpress app.
 */
export function normaliseAliExpressUrl(rawUrl) {
  try {
    if (isAdmitadUrl(rawUrl)) {
      const u = new URL(rawUrl);
      const ulp = u.searchParams.get('ulp');
      if (!ulp) return rawUrl;

      const fixed = normaliseUlp(ulp);
      if (fixed === ulp) return rawUrl;

      u.searchParams.set('ulp', fixed);
      return u.toString();
    }

    if (isAliExpressUrl(rawUrl)) {
      return normaliseUlp(rawUrl);
    }

    return rawUrl;
  } catch {
    return rawUrl;
  }
}
