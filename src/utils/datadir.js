import path from 'path';

// Use /data (HF Spaces persistent storage) when running in HF Spaces,
// fall back to ./data for local development.
const BASE = process.env.SPACE_ID ? '/data' : path.resolve('data');

export function dataPath(...parts) {
  return path.join(BASE, ...parts);
}
