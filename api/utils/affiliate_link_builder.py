import re
from urllib.parse import urlencode, urlparse, parse_qs


_NETWORKS = {
    "admitad": {
        "wrapper": "rzekl.com",
        "required_params": ["aff_short_key"],
    },
    "sovrn": {
        "wrapper": "redirect.viglink.com",
        "required_params": ["key", "u"],
    },
    "takeads": {
        "wrapper": "takeads.com",
        "required_params": [],
    },
    "travelpayouts": {
        "wrapper": "tp.media",
        "required_params": ["marker"],
    },
}


def add_utm(url: str, source: str, medium: str = "social", campaign: str = "affiliate") -> str:
    separator = "&" if "?" in url else "?"
    params = urlencode({"utm_source": source, "utm_medium": medium, "utm_campaign": campaign})
    return f"{url}{separator}{params}"


def detect_network(url: str) -> str | None:
    url_lower = url.lower()
    for network, cfg in _NETWORKS.items():
        if cfg["wrapper"] in url_lower:
            return network
    return None


def validate_admitad(url: str) -> dict:
    parsed = urlparse(url)
    has_wrapper = "rzekl.com" in url
    params = parse_qs(parsed.query)
    has_key = "aff_short_key" in params
    issues = []
    if not has_wrapper:
        issues.append("missing rzekl.com wrapper")
    if not has_key:
        issues.append("missing aff_short_key param")
    return {"valid": len(issues) == 0, "issues": issues}


def build_admitad(target_url: str, aff_short_key: str, campaign: str = "affiliate") -> str:
    base = f"https://rzekl.com/g/1e8d114494b4b6a5bf/?aff_short_key={aff_short_key}&ulp="
    encoded = target_url.replace(":", "%3A").replace("/", "%2F").replace("?", "%3F").replace("&", "%26").replace("=", "%3D")
    return f"{base}{encoded}"


def build_utm_url(url: str, platform: str, campaign: str = "affiliate") -> str:
    return add_utm(url, source=platform, medium="social", campaign=campaign)


def strip_utm(url: str) -> str:
    utm_pattern = re.compile(r"[&?]utm_[^&]+")
    cleaned = utm_pattern.sub("", url)
    if cleaned.endswith("?"):
        cleaned = cleaned[:-1]
    return cleaned


def is_affiliate_url(url: str) -> bool:
    return detect_network(url) is not None


def link_summary(url: str) -> dict:
    network = detect_network(url)
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    utm_keys = [k for k in params if k.startswith("utm_")]
    return {
        "url": url,
        "network": network,
        "domain": parsed.netloc,
        "has_utm": len(utm_keys) > 0,
        "utm_params": {k: params[k][0] for k in utm_keys},
        "is_affiliate": network is not None,
    }
