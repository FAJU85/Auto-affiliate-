import re
import unicodedata

_TRANSLITERATE: dict[str, str] = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "à": "a", "á": "a", "â": "a", "ã": "a", "å": "a",
    "è": "e", "é": "e", "ê": "e", "ë": "e",
    "ì": "i", "í": "i", "î": "i", "ï": "i",
    "ò": "o", "ó": "o", "ô": "o", "õ": "o",
    "ù": "u", "ú": "u", "û": "u",
    "ñ": "n", "ç": "c", "ý": "y",
    "æ": "ae", "ø": "o", "þ": "th", "ð": "d",
}

_NOISE = re.compile(r"[^\w\s-]")
_SPACES = re.compile(r"\s+")


def _strip_accents(text: str) -> str:
    result = []
    for ch in text:
        lower = ch.lower()
        if lower in _TRANSLITERATE:
            result.append(_TRANSLITERATE[lower] if ch == lower else _TRANSLITERATE[lower].upper())
        else:
            nfd = unicodedata.normalize("NFD", ch)
            ascii_ch = nfd.encode("ascii", "ignore").decode()
            result.append(ascii_ch if ascii_ch else ch)
    return "".join(result)


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = _strip_accents(name)
    name = _NOISE.sub(" ", name)
    name = _SPACES.sub(" ", name).strip().lower()
    return name


def names_match(a: str, b: str, threshold: float = 0.85) -> bool:
    na, nb = normalize_name(a), normalize_name(b)
    if na == nb:
        return True
    longer = max(len(na), len(nb))
    if longer == 0:
        return True
    shorter = min(len(na), len(nb))
    ratio = shorter / longer
    return ratio >= threshold and (na in nb or nb in na)


def normalize_product(product: dict) -> dict:
    if "name" not in product:
        return product
    return {**product, "name": normalize_name(product["name"]), "_original_name": product["name"]}
