"""Geo-targeting filter for affiliate products."""

COUNTRY_TLD_MAP: dict[str, str] = {
    "UK": ".co.uk",
    "DE": ".de",
    "FR": ".fr",
    "AU": ".com.au",
    "CA": ".ca",
    "US": ".com",
    "IT": ".it",
    "ES": ".es",
    "NL": ".nl",
    "BR": ".com.br",
}

# Reverse map: TLD -> country code, ordered longest first to avoid .com shadowing .com.au
_TLD_TO_COUNTRY: dict[str, str] = dict(
    sorted(
        ((tld, code) for code, tld in COUNTRY_TLD_MAP.items()),
        key=lambda x: -len(x[0]),
    )
)


def detect_product_region(product: dict) -> str | None:
    """Infer region from product 'region' field or URL TLD."""
    region = product.get("region")
    if region:
        return region.upper()

    url = product.get("url", "")
    if not url:
        return None

    # Strip query/fragment to check TLD
    path = url.split("?")[0].split("#")[0]
    # Extract domain portion
    try:
        domain = path.split("//", 1)[1].split("/")[0].lower()
    except IndexError:
        domain = path.lower()

    for tld, code in _TLD_TO_COUNTRY.items():
        if domain.endswith(tld) or ("." + domain.split(".", 1)[-1]).endswith(tld):
            return code

    return None


def is_allowed_region(product: dict, allowed: list[str]) -> bool:
    """Return True if product region is in allowed list, or allowed is empty, or region is unknown."""
    if not allowed:
        return True
    region = detect_product_region(product)
    if region is None:
        return True
    return region.upper() in [a.upper() for a in allowed]


def filter_by_region(products: list[dict], allowed: list[str]) -> list[dict]:
    """Return only products passing is_allowed_region."""
    return [p for p in products if is_allowed_region(p, allowed)]
