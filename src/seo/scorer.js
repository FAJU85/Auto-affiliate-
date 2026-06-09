/**
 * Caption SEO Scorer
 *
 * Grades a Bluesky post caption on several SEO/engagement signals.
 * Returns a 0-100 score with a breakdown so the pipeline can
 * decide whether to retry generation or accept the caption.
 */

const POWER_WORDS = [
  'best', 'top', 'deal', 'sale', 'off', 'free', 'save', 'limited', 'exclusive',
  'new', 'must-have', 'perfect', 'ultimate', 'essential', 'upgrade', 'cheap',
  'affordable', 'premium', 'unbeatable', 'amazing', 'incredible', 'hot',
];

const CTA_PATTERNS = [
  /shop\s*now/i, /get\s+yours/i, /buy\s+now/i, /grab\s+(it|yours)/i,
  /check\s+it\s+out/i, /don'?t\s+miss/i, /link\s+in\s+bio/i, /tap\s+to/i,
  /order\s+now/i, /discover/i, /→/,
];

const SPAM_PATTERNS = [
  /\$\$\$/i, /click\s+here/i, /act\s+now/i, /limited\s+time\s+offer.*\!/i,
  /!!!/, /100%\s+free/i, /make\s+money/i,
];

/**
 * Scores a caption for SEO/engagement quality.
 * @param {string} caption
 * @param {string[]} keywords - trending keyword strings to check for inclusion
 * @returns {{ score: number, grade: string, breakdown: object, issues: string[] }}
 */
export function scoreCaption(caption, keywords = []) {
  const text = caption || '';
  const lower = text.toLowerCase();
  const words = lower.split(/\s+/).filter(Boolean);
  const charCount = text.length;
  const issues = [];
  const breakdown = {};

  // 1. Length (ideal 140-280 chars for Bluesky)
  if (charCount >= 140 && charCount <= 280) {
    breakdown.length = 20;
  } else if (charCount >= 100 && charCount < 140) {
    breakdown.length = 12;
    issues.push('Caption a bit short — aim for 140+ chars');
  } else if (charCount > 280 && charCount <= 300) {
    breakdown.length = 15;
    issues.push('Caption slightly over 280 chars');
  } else if (charCount < 100) {
    breakdown.length = 5;
    issues.push('Caption too short (under 100 chars)');
  } else {
    breakdown.length = 5;
    issues.push('Caption too long (over 300 chars)');
  }

  // 2. CTA presence (0 or 20 points)
  const hasCTA = CTA_PATTERNS.some(p => p.test(text));
  breakdown.cta = hasCTA ? 20 : 0;
  if (!hasCTA) issues.push('No clear call-to-action detected');

  // 3. Power words (up to 20 points)
  const pwMatches = POWER_WORDS.filter(pw => lower.includes(pw));
  breakdown.powerWords = Math.min(pwMatches.length * 5, 20);
  if (!pwMatches.length) issues.push('No persuasive power words');

  // 4. Hashtags (up to 15 points)
  const hashtags = (text.match(/#\w+/g) || []);
  if (hashtags.length >= 2 && hashtags.length <= 5) {
    breakdown.hashtags = 15;
  } else if (hashtags.length === 1) {
    breakdown.hashtags = 8;
    issues.push('Only 1 hashtag — aim for 2-5');
  } else if (hashtags.length > 5) {
    breakdown.hashtags = 5;
    issues.push('Too many hashtags (>5) can hurt reach');
  } else {
    breakdown.hashtags = 0;
    issues.push('No hashtags — add 2-3 relevant ones');
  }

  // 5. Keyword inclusion (up to 15 points)
  const kwHits = keywords.filter(kw =>
    kw.toLowerCase().split(/\s+/).some(w => w.length > 3 && lower.includes(w))
  );
  breakdown.keywords = Math.min(kwHits.length * 5, 15);
  if (!kwHits.length && keywords.length > 0) {
    issues.push('No trending keywords in caption');
  }

  // 6. Spam/quality penalty
  const spamHits = SPAM_PATTERNS.filter(p => p.test(text));
  breakdown.spamPenalty = -(spamHits.length * 10);
  if (spamHits.length) issues.push('Spam-like patterns detected');

  // 7. Readability bonus: not all-caps, contains punctuation
  const allCapsWords = words.filter(w => w.length > 3 && w === w.toUpperCase()).length;
  const allCapsRatio = words.length ? allCapsWords / words.length : 0;
  if (allCapsRatio > 0.3) {
    breakdown.readability = -5;
    issues.push('Too many ALL-CAPS words');
  } else {
    breakdown.readability = 10;
  }

  const total = Object.values(breakdown).reduce((s, v) => s + v, 0);
  const score = Math.max(0, Math.min(100, total));

  const grade = score >= 80 ? 'A'
    : score >= 65 ? 'B'
    : score >= 50 ? 'C'
    : score >= 35 ? 'D'
    : 'F';

  return { score, grade, breakdown, issues };
}

/**
 * Minimum acceptable score before the pipeline retries text generation.
 * Can be overridden via SEO_MIN_SCORE env var.
 */
export function getMinScore() {
  return parseInt(process.env.SEO_MIN_SCORE || '50', 10);
}
