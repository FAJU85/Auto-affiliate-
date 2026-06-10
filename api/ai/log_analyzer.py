"""AI-driven log analysis using HuggingFace Inference API.

Model: Qwen/Qwen2.5-72B-Instruct (free serverless inference via HF_TOKEN)
Fallback: mistral-small via MISTRAL_API_KEY, then groq llama via GROQ_API_KEY
"""

import os
import httpx
from ..utils import logger as log

HF_URL   = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct/v1/chat/completions"
HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"

MISTRAL_URL   = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small-latest"

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

TIMEOUT = 30

SYSTEM_PROMPT = """You are an expert DevOps and software diagnostics AI.
You analyze application logs from an affiliate marketing bot and provide clear, actionable diagnostics.

Your response must be a JSON object with this exact structure:
{
  "status": "healthy" | "warning" | "critical",
  "summary": "one sentence overall assessment",
  "issues": [
    {
      "component": "component name",
      "severity": "error" | "warning" | "info",
      "title": "short issue title",
      "detail": "what went wrong and why",
      "fix": "specific action to fix it"
    }
  ],
  "insights": ["observation 1", "observation 2"],
  "recommendation": "the single most important action to take right now"
}

Be specific. Reference actual error messages. If logs are healthy, say so."""


def _build_prompt(logs: list[dict], last_run: dict | None) -> str:
    lines = []

    if last_run:
        lines.append(f"=== LAST PIPELINE RUN ===")
        lines.append(f"Success: {last_run.get('success')}")
        lines.append(f"Platforms: {last_run.get('platforms', [])}")
        if last_run.get('error'):
            lines.append(f"Error: {last_run['error']}")
        lines.append("")

    lines.append(f"=== RECENT LOGS ({len(logs)} entries) ===")
    # Focus on errors and warnings, but include some info for context
    errors   = [l for l in logs if l.get('level') == 'error']
    warns    = [l for l in logs if l.get('level') == 'warn']
    infos    = [l for l in logs if l.get('level') == 'info'][-10:]

    for entry in errors[-20:]:
        lines.append(f"[ERROR][{entry.get('component','?')}] {entry.get('msg','')}")
    for entry in warns[-15:]:
        lines.append(f"[WARN][{entry.get('component','?')}] {entry.get('msg','')}")
    for entry in infos:
        lines.append(f"[INFO][{entry.get('component','?')}] {entry.get('msg','')}")

    if not errors and not warns:
        lines.append("No errors or warnings found.")

    return "\n".join(lines)


async def _call_api(url: str, key: str, model: str, prompt: str) -> dict | None:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": 800,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            log.warn(f"AI log analyzer HTTP {r.status_code} from {model}: {r.text[:150]}", "ai")
            return None
        content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return None
        import json
        return json.loads(content)
    except Exception as err:
        log.warn(f"AI log analyzer error ({model}): {err}", "ai")
        return None


async def analyze_logs(logs: list[dict], last_run: dict | None = None) -> dict:
    """Run AI analysis on logs. Returns structured diagnosis dict."""
    prompt = _build_prompt(logs, last_run)

    # Try HuggingFace first (free)
    hf_key = os.environ.get("HF_TOKEN", "")
    if hf_key:
        log.info("Running AI log analysis via HuggingFace (Qwen2.5-72B)…", "ai")
        result = await _call_api(HF_URL, hf_key, HF_MODEL, prompt)
        if result:
            result["model"] = HF_MODEL
            result["provider"] = "huggingface"
            return result

    # Fallback: Mistral
    mistral_key = os.environ.get("MISTRAL_API_KEY", "")
    if mistral_key:
        log.info("HF unavailable — falling back to Mistral for log analysis", "ai")
        result = await _call_api(MISTRAL_URL, mistral_key, MISTRAL_MODEL, prompt)
        if result:
            result["model"] = MISTRAL_MODEL
            result["provider"] = "mistral"
            return result

    # Fallback: Groq
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        log.info("Mistral unavailable — falling back to Groq for log analysis", "ai")
        result = await _call_api(GROQ_URL, groq_key, GROQ_MODEL, prompt)
        if result:
            result["model"] = GROQ_MODEL
            result["provider"] = "groq"
            return result

    return {
        "status": "unknown",
        "summary": "AI analysis unavailable — no AI provider configured (set HF_TOKEN, MISTRAL_API_KEY, or GROQ_API_KEY)",
        "issues": [],
        "insights": [],
        "recommendation": "Add HF_TOKEN to your Space Secrets to enable AI log analysis.",
        "model": None,
        "provider": None,
    }
