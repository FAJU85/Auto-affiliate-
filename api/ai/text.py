"""Caption generation: Groq -> Mistral -> template fallback.

Env: GROQ_API_KEY, MISTRAL_API_KEY
"""

import os
import random

import httpx

from ..utils import logger, settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small-latest"

MAX_CHARS = 200


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
    user = s["postUserTemplate"].format(
        name=product.get("name", "this product"),
        category=product.get("category", "general"),
        description=product.get("description", product.get("name", "")),
        price=_fmt_price(product) or "great value",
        trend=trend,
    )
    return s["postSystemPrompt"], user


def _clean(text: str) -> str:
    text = (text or "").strip().strip('"').strip()
    if len(text) > MAX_CHARS:
        text = text[: MAX_CHARS - 1].rsplit(" ", 1)[0].rstrip() + "…"
    return text


async def _chat(url: str, key: str, model: str, system: str, user: str) -> str | None:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 60,
        "temperature": 0.85,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        logger.warn(f"AI {model} HTTP {r.status_code}: {r.text[:120]}")
        return None
    return r.json()["choices"][0]["message"]["content"]


async def _try_groq(system: str, user: str) -> str | None:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    try:
        return await _chat(GROQ_URL, key, GROQ_MODEL, system, user)
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Groq failed: {err}")
        return None


async def _try_mistral(system: str, user: str) -> str | None:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        return None
    try:
        return await _chat(MISTRAL_URL, key, MISTRAL_MODEL, system, user)
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Mistral failed: {err}")
        return None


def _template(product: dict, trends: list) -> str:
    name = product.get("name", "this find")
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
            logger.info(f"Caption via {provider.__name__.replace('_try_', '')}")
            return _clean(out)
    logger.warn("AI providers unavailable — using template caption")
    return _template(product, trends)
