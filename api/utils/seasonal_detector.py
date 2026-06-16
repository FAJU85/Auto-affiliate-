from datetime import datetime, timezone


_SEASONS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "spring": ((3, 1), (5, 31)),
    "summer": ((6, 1), (8, 31)),
    "autumn": ((9, 1), (11, 30)),
    "winter": ((12, 1), (2, 28)),
}

_HOLIDAYS: dict[str, tuple[int, int, int, int]] = {
    "christmas": (12, 1, 12, 31),
    "black_friday": (11, 20, 11, 30),
    "valentines": (2, 1, 2, 14),
    "halloween": (10, 15, 10, 31),
    "easter": (3, 15, 4, 30),
    "mothers_day": (5, 1, 5, 15),
    "fathers_day": (6, 1, 6, 21),
    "back_to_school": (8, 1, 9, 15),
    "new_year": (12, 26, 1, 5),
    "cyber_monday": (11, 25, 12, 5),
}

_SEASON_KEYWORDS: dict[str, list[str]] = {
    "spring": ["spring", "garden", "outdoor", "fresh", "floral"],
    "summer": ["summer", "beach", "pool", "sunscreen", "bbq", "grill", "travel"],
    "autumn": ["autumn", "fall", "halloween", "cozy", "harvest"],
    "winter": ["winter", "christmas", "holiday", "snow", "warm", "gift"],
}

_HOLIDAY_KEYWORDS: dict[str, list[str]] = {
    "christmas": ["christmas", "xmas", "gift", "holiday", "santa"],
    "black_friday": ["black friday", "deal", "sale", "discount", "offer"],
    "valentines": ["valentine", "love", "romantic", "heart", "couple"],
    "halloween": ["halloween", "spooky", "costume", "trick", "treat"],
    "easter": ["easter", "spring", "egg", "bunny"],
    "back_to_school": ["school", "backpack", "student", "college", "notebook"],
    "cyber_monday": ["cyber", "deal", "online", "tech", "electronics"],
}


def current_season(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    m, d = now.month, now.day
    for season, ((sm, sd), (em, ed)) in _SEASONS.items():
        if sm <= em:
            if (m, d) >= (sm, sd) and (m, d) <= (em, ed):
                return season
        else:
            if (m, d) >= (sm, sd) or (m, d) <= (em, ed):
                return season
    return "winter"


def active_holidays(now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    m, d = now.month, now.day
    active = []
    for holiday, (sm, sd, em, ed) in _HOLIDAYS.items():
        if sm <= em:
            if (m, d) >= (sm, sd) and (m, d) <= (em, ed):
                active.append(holiday)
        else:
            if (m, d) >= (sm, sd) or (m, d) <= (em, ed):
                active.append(holiday)
    return active


def is_seasonal(product: dict, now: datetime | None = None) -> bool:
    text = f"{product.get('name', '')} {product.get('description', '')} {product.get('category', '')}".lower()
    season = current_season(now)
    if any(kw in text for kw in _SEASON_KEYWORDS.get(season, [])):
        return True
    for holiday in active_holidays(now):
        if any(kw in text for kw in _HOLIDAY_KEYWORDS.get(holiday, [])):
            return True
    return False


def seasonal_context(now: datetime | None = None) -> dict:
    return {
        "season": current_season(now),
        "active_holidays": active_holidays(now),
    }


def boost_seasonal(products: list[dict], now: datetime | None = None) -> list[dict]:
    seasonal, other = [], []
    for p in products:
        (seasonal if is_seasonal(p, now) else other).append(p)
    return seasonal + other
