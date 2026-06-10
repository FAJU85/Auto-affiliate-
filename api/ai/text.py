"""Caption generation: Groq -> Mistral -> template fallback.

Env: GROQ_API_KEY, MISTRAL_API_KEY

Reliability:
  - Circuit breakers per provider (open after 5 failures, recover after 60s)
  - Retry on 429 (rate-limit) with Retry-After respect
  - Timeout: 20s per call
  - Template fallback always succeeds
"""

import asyncio
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
TEMPERATURE  = 0.55  # lower = more predictable English output


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


def _looks_usable(text: str) -> bool:
    """Reject clearly broken AI output before returning it."""
    import re
    if not text or len(text) < 20:
        return False
    # Reject non-English: >40% non-ASCII chars
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if non_ascii / len(text) > 0.40:
        return False
    # Reject if almost no actual letters (symbol/punctuation spam)
    letters = sum(1 for c in text if c.isalpha())
    if letters < 10:
        return False
    # Reject CamelCase keyword-list spam (e.g. "NorthFaceThermoball SummerDeals ClickNow")
    # Real sentences have spaces between lower-case words; keyword dumps are CamelCase runs
    words = text.split()
    if len(words) >= 4:
        camel_words = sum(1 for w in words if re.match(r'^[A-Z][a-z]+[A-Z]', w))
        if camel_words / len(words) > 0.5:
            return False
    # Reject if the text has no verb-like words and no punctuation (likely a title/tag list)
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
    # Strip markdown bold/italic/headers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    # Strip URLs
    text = re.sub(r"https?://\S+", "", text).strip()
    # Strip hashtags (AI adds them despite instruction)
    text = re.sub(r"#\w+", "", text).strip()
    # Collapse multiple spaces/newlines
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n+", " ", text).strip()
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
        "max_tokens": 80,
        "temperature": TEMPERATURE,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # Up to 3 attempts with exponential backoff on 429
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
                logger.info(f"Caption via {provider.__name__.replace('_try_', '')}: {cleaned[:80]}…")
                return cleaned
            logger.warn(f"AI caption rejected (unusable): {repr(cleaned[:80])}")
    logger.warn("AI providers unavailable or unusable — using template")
    return _template(product, trends)
