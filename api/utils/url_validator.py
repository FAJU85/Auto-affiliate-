import re
from urllib.parse import urlparse, parse_qs

_URL_RE = re.compile(
    r"^https?://"
    r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}"
    r"(?:/[^\s]*)?"
    r"$"
)

_REQUIRED_ADMITAD_PARAM = "aff_short_key"
_ADMITAD_WRAPPER = "rzekl.com"


def is_valid_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    return bool(_URL_RE.match(url.strip()))


def parse_url(url: str) -> dict:
    try:
        parsed = urlparse(url)
        return {
            "scheme": parsed.scheme,
            "host": parsed.netloc,
            "path": parsed.path,
            "params": parse_qs(parsed.query),
            "fragment": parsed.fragment,
        }
    except Exception:
        return {}


def check_admitad_link(url: str) -> dict:
    issues = []
    if not is_valid_url(url):
        issues.append("invalid_url")
    if _ADMITAD_WRAPPER not in url:
        issues.append("missing_rzekl_wrapper")
    parsed = parse_url(url)
    params = parsed.get("params", {})
    if _REQUIRED_ADMITAD_PARAM not in params:
        issues.append("missing_aff_short_key")
    return {
        "url": url,
        "valid": len(issues) == 0,
        "issues": issues,
    }


def validate_batch(urls: list[str]) -> list[dict]:
    return [{"url": u, "valid": is_valid_url(u)} for u in urls]


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\)\]\"'>]+", text)


def has_tracking_params(url: str) -> bool:
    tracking = {"utm_source", "utm_medium", "utm_campaign", "ref", "aff_short_key", "click_id"}
    parsed = parse_url(url)
    return bool(set(parsed.get("params", {}).keys()) & tracking)


def url_summary(urls: list[str]) -> dict:
    valid = [u for u in urls if is_valid_url(u)]
    return {
        "total": len(urls),
        "valid": len(valid),
        "invalid": len(urls) - len(valid),
        "with_tracking": sum(1 for u in valid if has_tracking_params(u)),
    }
