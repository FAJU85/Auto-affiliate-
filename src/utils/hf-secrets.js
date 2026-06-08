/**
 * Read/write HuggingFace Space secrets via API.
 * Used to persist OAuth session and settings across Space rebuilds
 * without requiring persistent storage to be manually enabled.
 *
 * Requires HF_TOKEN (or HF_API_TOKEN) with write access to the Space.
 * SPACE_ID is injected automatically by HF Spaces (format: "owner/space-name").
 */

import fetch from 'node-fetch';
import { logger } from './logger.js';

const HF_API = 'https://huggingface.co/api';

function getSpaceId() { return process.env.SPACE_ID || null; }
function getToken()   { return process.env.HF_TOKEN || process.env.HF_API_TOKEN || null; }

export async function writeSecret(key, value) {
  const spaceId = getSpaceId();
  const token   = getToken();
  if (!spaceId || !token) return false;

  try {
    const res = await fetch(`${HF_API}/spaces/${spaceId}/secrets`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ key, value }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) {
      const text = await res.text();
      logger.warn(`HF secret write failed for ${key}: ${res.status} ${text.slice(0, 100)}`);
      return false;
    }
    logger.info(`HF secret saved: ${key}`);
    return true;
  } catch (err) {
    logger.warn(`HF secret write error for ${key}: ${err.message}`);
    return false;
  }
}

export async function deleteSecret(key) {
  const spaceId = getSpaceId();
  const token   = getToken();
  if (!spaceId || !token) return;
  try {
    await fetch(`${HF_API}/spaces/${spaceId}/secrets`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ key }),
      signal: AbortSignal.timeout(10_000),
    });
  } catch {}
}
