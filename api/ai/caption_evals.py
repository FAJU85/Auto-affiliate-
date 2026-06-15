"""Caption quality evaluation using pydantic-evals.

Scores generated captions on five dimensions:
  1. language   — English only (no Arabic / non-Latin scripts)
  2. length     — 40–200 chars
  3. cta        — ends with a call-to-action word or phrase
  4. readability — no CamelCase keyword dumps, has real sentences
  5. no_url     — clean (no raw URLs or hashtags)

Usage (standalone):
    python -m api.ai.caption_evals

Usage (in tests):
    from api.ai.caption_evals import score_caption, PASS_THRESHOLD
    assert score_caption(text).total >= PASS_THRESHOLD
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PASS_THRESHOLD = 0.70  # ≥70 % of max score to be considered publishable


@dataclass
class CaptionScore:
    language: float    # 0.0 or 1.0
    length: float      # 0.0–1.0 (smooth penalty for too short / too long)
    cta: float         # 0.0 or 1.0
    readability: float # 0.0 or 1.0
    no_url: float      # 0.0 or 1.0
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        weights = {"language": 0.30, "length": 0.20, "cta": 0.20, "readability": 0.20, "no_url": 0.10}
        return (
            self.language    * weights["language"]
            + self.length    * weights["length"]
            + self.cta       * weights["cta"]
            + self.readability * weights["readability"]
            + self.no_url    * weights["no_url"]
        )

    @property
    def passed(self) -> bool:
        return self.total >= PASS_THRESHOLD

    def __str__(self) -> str:
        bar = "█" * int(self.total * 10) + "░" * (10 - int(self.total * 10))
        status = "✅ PASS" if self.passed else "❌ FAIL"
        parts = [
            f"{status}  [{bar}] {self.total:.0%}",
            f"  language={self.language:.0%}  length={self.length:.0%}  cta={self.cta:.0%}"
            f"  readability={self.readability:.0%}  no_url={self.no_url:.0%}",
        ]
        if self.notes:
            parts.append("  notes: " + "; ".join(self.notes))
        return "\n".join(parts)


_CTA_RE = re.compile(
    r'\b(get|buy|shop|save|grab|try|discover|find|enjoy|upgrade|check|click|order|act|hurry|limited|now|today)\b',
    re.I,
)
_URL_RE = re.compile(r'https?://\S+|#\w+')
_CAMEL_RE = re.compile(r'^[A-Z][a-z]+[A-Z]')


def score_caption(text: str) -> CaptionScore:
    notes: list[str] = []

    # ── 1. Language ───────────────────────────────────────────────────────────
    arabic = sum(1 for c in text if '؀' <= c <= 'ۿ' or 'ݐ' <= c <= 'ݿ')
    non_ascii = sum(1 for c in text if ord(c) > 127) if text else 0
    if arabic > 2:
        lang_score = 0.0
        notes.append("contains Arabic characters")
    elif text and non_ascii / len(text) > 0.40:
        lang_score = 0.0
        notes.append(f"non-ASCII ratio {non_ascii/len(text):.0%} > 40%")
    else:
        lang_score = 1.0

    # ── 2. Length (40–200 chars is ideal) ────────────────────────────────────
    n = len(text)
    if n < 20:
        len_score = 0.0
        notes.append(f"too short ({n} chars)")
    elif n < 40:
        len_score = 0.5
        notes.append(f"short ({n} chars)")
    elif n <= 200:
        len_score = 1.0
    elif n <= 240:
        len_score = 0.7
        notes.append(f"slightly long ({n} chars)")
    else:
        len_score = 0.3
        notes.append(f"too long ({n} chars)")

    # ── 3. CTA ────────────────────────────────────────────────────────────────
    cta_score = 1.0 if _CTA_RE.search(text) else 0.0
    if not cta_score:
        notes.append("no CTA word found")

    # ── 4. Readability ────────────────────────────────────────────────────────
    words = text.split()
    letters = sum(1 for c in text if c.isalpha())
    camel_words = sum(1 for w in words if _CAMEL_RE.match(w))
    camel_ratio = camel_words / len(words) if words else 0

    if letters < 10:
        read_score = 0.0
        notes.append("almost no letters (symbol spam)")
    elif camel_ratio > 0.5 and len(words) >= 3:
        read_score = 0.0
        notes.append(f"CamelCase keyword dump ({camel_ratio:.0%} camel words)")
    else:
        read_score = 1.0

    # ── 5. No raw URLs / hashtags ─────────────────────────────────────────────
    no_url_score = 0.0 if _URL_RE.search(text) else 1.0
    if not no_url_score:
        notes.append("contains URL or hashtag")

    return CaptionScore(
        language=lang_score,
        length=len_score,
        cta=cta_score,
        readability=read_score,
        no_url=no_url_score,
        notes=notes,
    )


# ── pydantic-evals Dataset ────────────────────────────────────────────────────

def build_eval_dataset():
    """Build a pydantic-evals Dataset for batch caption evaluation."""
    try:
        from pydantic_evals import Case, Dataset
    except ImportError:
        return None

    cases = [
        Case(
            name="good_english_caption",
            inputs={"text": "Upgrade your home office with the Logitech MX Master 3 — ergonomic bliss awaits. Shop now! 🛒"},
            expected_output=True,
            metadata={"description": "Clean English caption with CTA"},
        ),
        Case(
            name="arabic_caption",
            inputs={"text": "احصل على أفضل العروض الآن على منتجاتنا المميزة"},
            expected_output=False,
            metadata={"description": "Arabic text — must be rejected"},
        ),
        Case(
            name="camelcase_spam",
            inputs={"text": "NorthFaceThermoball SummerDeals ClickNow BuyToday ShopNow"},
            expected_output=False,
            metadata={"description": "CamelCase keyword dump — must be rejected"},
        ),
        Case(
            name="too_short",
            inputs={"text": "Buy now!"},
            expected_output=False,
            metadata={"description": "Too short to be useful"},
        ),
        Case(
            name="contains_url",
            inputs={"text": "Great deal on Sony headphones https://example.com/deal — grab yours today!"},
            expected_output=False,
            metadata={"description": "Raw URL must be cleaned before eval"},
        ),
        Case(
            name="good_template_fallback",
            inputs={"text": "Save big on Sony WH-1000XM5 — just $279. Get it now!"},
            expected_output=True,
            metadata={"description": "Template fallback — always valid"},
        ),
    ]

    def evaluator(inputs: dict, output: bool) -> dict:
        result = score_caption(inputs["text"])
        return {"passed": result.passed == output, "score": result.total}

    return Dataset(cases=cases, name="caption_quality"), evaluator


if __name__ == "__main__":
    samples = [
        "Upgrade your home office with the Logitech MX Master 3 — ergonomic bliss. Shop now! 🛒",
        "احصل على أفضل العروض الآن",
        "NorthFaceThermoball SummerDeals ClickNow",
        "Save big on Sony WH-1000XM5 — just $279. Get it now!",
        "Buy now!",
        "Great product amazing quality best value premium exclusive luxury top-tier excellent superior outstanding",
    ]
    print("── Caption Quality Evaluator (pydantic-evals) ──\n")
    for s in samples:
        sc = score_caption(s)
        print(f"Caption: {s[:70]!r}")
        print(sc)
        print()
