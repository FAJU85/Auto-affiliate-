"""Caption generation: Groq -> Mistral -> template fallback.

Env: GROQ_API_KEY, MISTRAL_API_KEY

Reliability:
  - Circuit breakers per provider (open after 5 failures, recover after 60s)
  - Retry on 429 (rate-limit) with Retry-After respect
  - Timeout: 20s per call
  - Template fallback always succeeds

pydantic-ai is used for structured output: the AI must return a CaptionResult
with a `text` field, guaranteeing a parseable response even on quirky models.
"""

import asyncio
import os
import random

import httpx
from pydantic import BaseModel, Field

from ..utils import logger, settings
from ..utils.circuit_breaker import groq_cb, mistral_cb
from ..utils.telemetry import Timer, record_saturation

GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = "llama-3.3-70b-versatile"
MISTRAL_URL   = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small-latest"

MAX_CHARS    = 200
API_TIMEOUT  = 20   # seconds
TEMPERATURE  = 0.55  # lower = more predictable English output


# ── Structured output schema (pydantic-ai) ────────────────────────────────────

class CaptionResult(BaseModel):
    """Structured caption returned by the AI."""
    text: str = Field(description="The affiliate post caption in English, max 200 chars, ending with a CTA.")


# ── Prompt helpers ────────────────────────────────────────────────────────────

def _fmt_price(product: dict) -> str:
    price = product.get("price")
    if price is None:
        return ""
    cur = product.get("currency", "USD")
    sym = {"USD": "$", "EUR": "€", "GBP": "£"}.get(cur, "")
    return f"{sym}{price}" if sym else f"{price} {cur}"


def _build_prompts(product: dict, trends: list) -> tuple[str, str]:
    s = settings.get_settings()
    trend = (trends[0] if trends else product.get("category", "trending"))

    cta_phrases: list[str] = s.get("ctaPhrases") or []
    base_system = s.get("postSystemPrompt", "Write a short affiliate post.")
    if not base_system.lower().startswith("you must"):
        base_system = "You must respond in English only, regardless of the product name or description language. " + base_system
    if cta_phrases:
        cta_examples = "  " + "\n  ".join(cta_phrases[:6])
        cta_instruction = (
            f"\n\nCTA RULE: End your post with exactly ONE short, psychology-driven CTA phrase "
            f"(max 6 words + optional emoji). Pick the angle that best fits this specific product — "
            f"urgency for deals, aspiration for fashion/beauty, curiosity for tech, pain-relief for health. "
            f"Use one of these examples verbatim, or craft a stronger one in the same style:\n{cta_examples}"
        )
    else:
        cta_instruction = (
            "\n\nEnd with exactly one short, punchy CTA phrase (max 6 words + emoji). "
            "Match the psychological angle to the product type."
        )
    system = base_system + cta_instruction

    template = s.get("postUserTemplate", "{name}")
    try:
        user = template.format(
            name=product.get("name", "this product"),
            category=product.get("category", "general"),
            description=product.get("description", product.get("name", ""))[:200],
            price=_fmt_price(product) or "great value",
            trend=trend,
            highlights="",
        )
    except KeyError:
        user = f"Product: {product.get('name', 'this product')}. Write a short affiliate post."
    return system, user


# ── Quality gate ──────────────────────────────────────────────────────────────

def _looks_usable(text: str) -> bool:
    """Reject clearly broken AI output before returning it."""
    import re
    if not text or len(text) < 20:
        return False
    arabic_chars = sum(1 for c in text if '؀' <= c <= 'ۿ' or 'ݐ' <= c <= 'ݿ')
    if arabic_chars > 2:
        return False
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if non_ascii / len(text) > 0.40:
        return False
    letters = sum(1 for c in text if c.isalpha())
    if letters < 10:
        return False
    words = text.split()
    if len(words) >= 3:
        camel_words = sum(1 for w in words if re.match(r'^[A-Z][a-z]+[A-Z]', w))
        if camel_words / len(words) > 0.5:
            return False
    has_verb = bool(re.search(
        r'\b(get|buy|shop|save|grab|try|discover|find|enjoy|upgrade|love|perfect|great|best|top|now|today)\b',
        text, re.I
    ))
    has_punctuation = bool(re.search(r'[.,!?—]', text))
    if not has_verb and not has_punctuation and len(words) > 6:
        return False
    return True


def _clean(text: str) -> str:
    import re
    text = (text or "").strip().strip('"').strip()
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"https?://\S+", "", text).strip()
    text = re.sub(r"#\w+", "", text).strip()
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n+", " ", text).strip()
    if len(text) > MAX_CHARS:
        text = text[: MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip() + "…"
    return text


# ── Raw HTTP chat (circuit-breaker wrapped) ───────────────────────────────────

async def _chat(url: str, key: str, model: str, system: str, user: str) -> str | None:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": 80,
        "temperature": TEMPERATURE,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    for attempt in range(3):
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            r = await client.post(url, json=payload, headers=headers)

        if r.status_code == 429:
            record_saturation(model)
            retry_after = int(r.headers.get("Retry-After", 2 ** attempt * 5))
            logger.warn(f"AI {model} rate-limited (429) — waiting {retry_after}s (attempt {attempt+1}/3)")
            if attempt < 2:
                await asyncio.sleep(min(retry_after, 30))
                continue
            raise RuntimeError(f"rate_limited:{retry_after}")

        if r.status_code != 200:
            logger.warn(f"AI {model} HTTP {r.status_code}: {r.text[:120]}")
            return None

        content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return content or None

    return None


# ── pydantic-ai structured generation ────────────────────────────────────────

async def _chat_structured(url: str, key: str, model: str, system: str, user: str) -> CaptionResult | None:
    """Call the chat API requesting JSON output matching CaptionResult schema."""
    import json as _json
    schema = CaptionResult.model_json_schema()
    structured_system = (
        system
        + f'\n\nRespond ONLY with a JSON object matching this schema (no markdown, no extra keys):\n{_json.dumps(schema, indent=2)}'
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": structured_system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": 120,
        "temperature": TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            r = await client.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            return None
        content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        data = _json.loads(content)
        return CaptionResult(**data)
    except Exception:  # noqa: BLE001
        return None


async def _try_groq(system: str, user: str) -> str | None:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    if groq_cb.is_open():
        logger.warn("Groq circuit breaker OPEN — skipping")
        return None
    try:
        with Timer("groq_chat"):
            # Try structured output first; fall back to plain chat
            structured = await _chat_structured(GROQ_URL, key, GROQ_MODEL, system, user)
            if structured:
                return structured.text
            result = await groq_cb.call(_chat, GROQ_URL, key, GROQ_MODEL, system, user)
        return result
    except RuntimeError as e:
        if "rate_limited" in str(e):
            return None
        logger.warn(f"Groq failed: {e}")
        return None
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Groq failed: {err}")
        return None


async def _try_mistral(system: str, user: str) -> str | None:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        return None
    if mistral_cb.is_open():
        logger.warn("Mistral circuit breaker OPEN — skipping")
        return None
    try:
        with Timer("mistral_chat"):
            structured = await _chat_structured(MISTRAL_URL, key, MISTRAL_MODEL, system, user)
            if structured:
                return structured.text
            result = await mistral_cb.call(_chat, MISTRAL_URL, key, MISTRAL_MODEL, system, user)
        return result
    except RuntimeError as e:
        if "rate_limited" in str(e):
            return None
        logger.warn(f"Mistral failed: {e}")
        return None
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Mistral failed: {err}")
        return None


def _template(product: dict, trends: list) -> str:
    name  = product.get("name", "this product")
    price = _fmt_price(product)
    cat   = product.get("category", "")
    hooks = [
        f"Upgrade your {cat.lower() if cat else 'life'} with {name}",
        f"Save big on {name}",
        f"{name} — top-rated and worth every penny",
        f"Grab the {name} while it lasts",
        f"Best value on {name} right now",
    ]
    tail = f" — just {price}. Get it now!" if price else ". Get it now!"
    return _clean(random.choice(hooks) + tail)


async def generate_post_text(product: dict, trends: list | None = None) -> str:
    trends = trends or []
    system, user = _build_prompts(product, trends)
    for provider in (_try_groq, _try_mistral):
        out = await provider(system, user)
        if out and out.strip():
            cleaned = _clean(out)
            if _looks_usable(cleaned):
                logger.info(f"Caption ({len(cleaned)} chars): {cleaned[:80]}…")
                return cleaned
            logger.warn(f"AI caption rejected (unusable): {repr(cleaned[:80])}")
    logger.warn("AI providers unavailable or unusable — using template")
    return _template(product, trends)
