import fetch from 'node-fetch';
import fs from 'fs';
import path from 'path';
import { logger } from '../utils/logger.js';
import { dataPath } from '../utils/datadir.js';

const INSIGHTS_FILE = dataPath('learned-insights.json');
const MIN_CLICKS_TO_LEARN = 5;  // need at least this many total clicks before optimizing
const MIN_INTERVAL_MS = 6 * 60 * 60 * 1000; // re-optimize at most every 6 hours

const GROQ_API   = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODEL = 'llama-3.3-70b-versatile';
const MISTRAL_API   = 'https://api.mistral.ai/v1/chat/completions';
const MISTRAL_MODEL = 'mistral-small-latest';

export function loadInsights() {
  try {
    const data = JSON.parse(fs.readFileSync(INSIGHTS_FILE, 'utf8'));
    return data;
  } catch {
    return { insights: [], summary: '', bestCategories: [], worstCategories: [], updatedAt: null };
  }
}

function saveInsights(data) {
  fs.mkdirSync(path.dirname(INSIGHTS_FILE), { recursive: true });
  const tmp = `${INSIGHTS_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify({ ...data, updatedAt: new Date().toISOString() }, null, 2));
  fs.renameSync(tmp, INSIGHTS_FILE);
}

/**
 * Analyze recent posts with click data and generate writing guidelines.
 * Runs in the background after the pipeline run.
 * @param {Array} runs - recent run records from metrics
 */
export async function maybeRunOptimizer(runs) {
  const { updatedAt } = loadInsights();
  if (updatedAt && Date.now() - new Date(updatedAt).getTime() < MIN_INTERVAL_MS) return;

  const withClicks = runs.filter(r => r.success && typeof r.clicks === 'number');
  if (withClicks.length < 10) return;

  const totalClicks = withClicks.reduce((s, r) => s + (r.clicks || 0), 0);
  if (totalClicks < MIN_CLICKS_TO_LEARN) {
    logger.info(`Optimizer: only ${totalClicks} clicks so far — skipping (need ${MIN_CLICKS_TO_LEARN})`);
    return;
  }

  logger.info(`Optimizer: analyzing ${withClicks.length} posts with ${totalClicks} total clicks`);

  const posts = withClicks.slice(-60).map(r => ({
    clicks:      r.clicks || 0,
    caption:     (r.caption || '').slice(0, 160),
    product:     (r.product || '').slice(0, 60),
    source:      r.productSource || 'unknown',
    hasImage:    !!r.imageGenerated,
    hasPrice:    /\$|€|£|\d+\.\d{2}/.test(r.caption || ''),
    hasCTA:      /\b(shop|buy|get|grab|save|check|discover|click|order)\b/i.test(r.caption || ''),
    hour:        r.timestamp ? new Date(r.timestamp).getUTCHours() : null,
    qualityScore: r.qualityScore || 0,
    captionLen:  (r.caption || '').length,
  }));

  const prompt = `You are an affiliate marketing conversion optimizer.

Here are ${posts.length} recent social media affiliate posts with their click counts (clicks = how many people clicked the affiliate link):

${JSON.stringify(posts, null, 2)}

Analyze which patterns correlate with MORE clicks. Look at: caption style, presence of price/CTA/image, product category, posting hour, caption length, source network.

Return ONLY a valid JSON object — no markdown, no explanation:
{
  "insights": ["<actionable writing rule max 90 chars>", ...],  // 4-6 rules
  "bestCategories": ["<source/category>", ...],
  "worstCategories": ["<source/category>", ...],
  "summary": "<one sentence: the single most impactful factor for clicks>"
}`;

  const result = await callLLM(prompt);
  if (!result) {
    logger.warn('Optimizer: LLM call failed');
    return;
  }

  try {
    const parsed = JSON.parse(result.replace(/^```json\s*/i, '').replace(/```\s*$/, '').trim());
    if (!Array.isArray(parsed.insights) || !parsed.insights.length) throw new Error('no insights array');
    saveInsights(parsed);
    logger.info(`Optimizer: saved ${parsed.insights.length} insights. Summary: ${parsed.summary}`);
  } catch (err) {
    logger.warn(`Optimizer: failed to parse LLM response: ${err.message}`);
  }
}

async function callLLM(prompt) {
  const providers = [
    { key: process.env.GROQ_API_KEY,    url: GROQ_API,    model: GROQ_MODEL,    name: 'Groq' },
    { key: process.env.MISTRAL_API_KEY, url: MISTRAL_API, model: MISTRAL_MODEL, name: 'Mistral' },
  ];
  for (const p of providers) {
    if (!p.key) continue;
    try {
      const res = await fetch(p.url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${p.key}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: p.model,
          messages: [{ role: 'user', content: prompt }],
          max_tokens: 400,
          temperature: 0.3,
        }),
        signal: AbortSignal.timeout(30_000),
      });
      if (!res.ok) continue;
      const data = await res.json();
      const text = data?.choices?.[0]?.message?.content;
      if (text) return text;
    } catch (err) {
      logger.warn(`Optimizer ${p.name} failed: ${err.message}`);
    }
  }
  return null;
}
