_REGION_COUNTRIES: dict[str, list[str]] = {
    "eu": ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
            "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"],
    "nordics": ["DK", "FI", "IS", "NO", "SE"],
    "latam": ["AR", "BO", "BR", "CL", "CO", "CR", "CU", "DO", "EC", "SV", "GT", "HN",
               "MX", "NI", "PA", "PY", "PE", "PR", "UY", "VE"],
    "apac": ["AU", "CN", "HK", "IN", "ID", "JP", "KR", "MY", "NZ", "PH", "SG", "TW", "TH", "VN"],
    "mena": ["AE", "BH", "EG", "IL", "IQ", "IR", "JO", "KW", "LB", "LY", "MA", "OM", "QA",
              "SA", "SY", "TN", "TR", "YE"],
}


def _normalize(code: str) -> str:
    return code.strip().upper()


def expand_regions(targets: list[str]) -> list[str]:
    codes: list[str] = []
    for t in targets:
        key = t.lower()
        if key in _REGION_COUNTRIES:
            codes.extend(_REGION_COUNTRIES[key])
        else:
            codes.append(_normalize(t))
    return list(dict.fromkeys(codes))


def is_allowed(
    country: str,
    allow: list[str] | None = None,
    block: list[str] | None = None,
) -> bool:
    code = _normalize(country)
    if block:
        blocked = expand_regions(block)
        if code in blocked:
            return False
    if allow:
        allowed = expand_regions(allow)
        return code in allowed
    return True


def filter_products(
    products: list[dict],
    country_field: str = "country",
    allow: list[str] | None = None,
    block: list[str] | None = None,
) -> list[dict]:
    result = []
    for p in products:
        country = p.get(country_field, "")
        if not country:
            result.append(p)
            continue
        if is_allowed(str(country), allow=allow, block=block):
            result.append(p)
    return result


def geo_summary(countries: list[str]) -> dict:
    counts: dict[str, int] = {}
    for c in countries:
        code = _normalize(c)
        counts[code] = counts.get(code, 0) + 1
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return {
        "unique_countries": len(counts),
        "top_countries": [{"country": c, "count": n} for c, n in top[:5]],
        "counts": counts,
    }
