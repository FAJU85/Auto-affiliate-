/**
 * Normalises AliExpress URLs buried inside Admitad redirect chains so they
 * open correctly in the AliExpress mobile app.
 *
 * Real URL structure seen in the wild:
 *   rzekl.com/g/...?ulp=
 *     s.click.aliexpress.com/deep_link.htm?aff_short_key=...&dl_target_url=
 *       www.aliexpress.com/item/ITEM_ID.html?pdp_npi=6...
 *
 * The AliExpress app intercepts s.click.aliexpress.com as a universal link
 * but chokes on deep_link.htm + pdp_npi tracking params → blank screen.
 *
 * Fix: unwrap all layers, extract the item ID, rebuild a clean
 * www.aliexpress.com/item/ITEM_ID.html?sourceType=620 URL, then re-wrap
 * it inside the rzekl.com deeplink so Admitad attribution is preserved.
 */

const AE_HOSTS    = /(?:^|\.)aliexpress\.com$/i;
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
 * Extracts a clean www.aliexpress.com/item/ITEM_ID.html?sourceType=620 URL
 * from any of the known AliExpress URL formats:
 *   - www.aliexpress.com/item/ITEM_ID.html  (direct product page)
 *   - s.click.aliexpress.com/deep_link.htm?dl_target_url=...  (AE affiliate)
 *
 * Returns null if no item ID can be found.
 */
function extractCleanAeUrl(url) {
  try {
    const u = new URL(url);
    if (!AE_HOSTS.test(u.hostname)) return null;

    // s.click.aliexpress.com/deep_link.htm → unwrap dl_target_url
    if (u.searchParams.has('dl_target_url')) {
      const inner = u.searchParams.get('dl_target_url'); // auto-decoded
      return extractCleanAeUrl(inner);
    }

    // Extract item ID from path  /item/1234567890.html
    const pathMatch = u.pathname.match(/\/item\/(\d+)/i);
    const itemId = pathMatch?.[1]
      || u.searchParams.get('productId')
      || u.searchParams.get('item_id')
      || u.searchParams.get('id');

    if (!itemId) return null;

    return `https://www.aliexpress.com/item/${itemId}.html?sourceType=620`;
  } catch {
    return null;
  }
}

/**
 * Normalises any URL that leads to an AliExpress product:
 *
 * - If it's an Admitad redirect (rzekl.com / admitad.com), the ulp param
 *   is unwrapped, cleaned, and re-wrapped so Admitad attribution is kept.
 * - If it's a direct AliExpress or s.click URL, it's cleaned in place.
 * - Non-AliExpress, non-Admitad URLs are returned unchanged.
 */
export function normaliseAliExpressUrl(rawUrl) {
  try {
    // ── Admitad wrapper (rzekl.com / ad.admitad.com) ─────────────────────────
    if (isAdmitadUrl(rawUrl)) {
      const u = new URL(rawUrl);
      const ulp = u.searchParams.get('ulp');
      if (!ulp) return rawUrl;

      const clean = extractCleanAeUrl(ulp);
      if (!clean || clean === ulp) return rawUrl;

      u.searchParams.set('ulp', clean);
      return u.toString();
    }

    // ── Direct AliExpress / s.click URL ──────────────────────────────────────
    if (isAliExpressUrl(rawUrl)) {
      return extractCleanAeUrl(rawUrl) || rawUrl;
    }

    return rawUrl;
  } catch {
    return rawUrl;
  }
}
