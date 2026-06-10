"""Caption generation: Groq -> Mistral -> template fallback.

Env: GROQ_API_KEY, MISTRAL_API_KEY

Reliability:
  - Circuit breakers per provider (open after 5 failures, recover after 60s)
  - Retry on 429 (rate-limit) with Retry-After respect
  - Timeout: 20s per call
  - Template fallback always succeeds
"""

import os
import random

import httpx

from ..utils import logger, settings
from ..utils.circuit_breaker import groq_cb, mistral_cb
from ..utils.telemetry import Timer, record_saturation

GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"
MISTRAL_URL  = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small-latest"

MAX_CHARS    = 200
API_TIMEOUT  = 20   # seconds


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
    # Safely format — unknown keys fall back to empty string
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
    return s.get("postSystemPrompt", "Write a short affiliate post."), user


def _clean(text: str) -> str:
    text = (text or "").strip().strip('"').strip()
    # Strip any URLs the AI may have snuck in
    import re
    text = re.sub(r"https?://\S+", "", text).strip()
    if len(text) > MAX_CHARS:
        text = text[: MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip() + "…"
    return text


async def _chat(url: str, key: str, model: str, system: str, user: str) -> str | None:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": 60,
        "temperature": 0.85,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.post(url, json=payload, headers=headers)

    if r.status_code == 429:
        record_saturation(model)
        retry_after = int(r.headers.get("Retry-After", 5))
        logger.warn(f"AI {model} rate-limited (429) — Retry-After: {retry_after}s")
        raise RuntimeError(f"rate_limited:{retry_after}")

    if r.status_code != 200:
        logger.warn(f"AI {model} HTTP {r.status_code}: {r.text[:120]}")
        return None

    content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    return content or None


async def _try_groq(system: str, user: str) -> str | None:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    if groq_cb.is_open():
        logger.warn("Groq circuit breaker OPEN — skipping")
        return None
    try:
        with Timer("groq_chat"):
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
    name  = product.get("name", "this find")
    price = _fmt_price(product)
    hooks = [
        f"✨ Spotted: {name}",
        f"\U0001f525 Deal alert — {name}",
        f"Don't sleep on {name}",
        f"Obsessed with {name} rn",
    ]
    tail = f" for just {price}." if price else "."
    return _clean(random.choice(hooks) + tail + " Grab yours \U0001f447")


async def generate_post_text(product: dict, trends: list | None = None) -> str:
    trends = trends or []
    system, user = _build_prompts(product, trends)
    for provider in (_try_groq, _try_mistral):
        out = await provider(system, user)
        if out and out.strip():
            cleaned = _clean(out)
            if len(cleaned) >= 20:
                logger.info(f"Caption via {provider.__name__.replace('_try_', '')}: {cleaned[:60]}…")
                return cleaned
    logger.warn("AI providers unavailable or responses too short — using template")
    return _template(product, trends)
