from typing import Any

_SCHEMA: dict[str, dict] = {
    "bskyHandle":           {"type": str,  "required": False},
    "bskyAppPassword":      {"type": str,  "required": False},
    "mastodonInstance":     {"type": str,  "required": False},
    "mastodonToken":        {"type": str,  "required": False},
    "twitterApiKey":        {"type": str,  "required": False},
    "twitterApiSecret":     {"type": str,  "required": False},
    "twitterAccessToken":   {"type": str,  "required": False},
    "twitterAccessSecret":  {"type": str,  "required": False},  # pragma: allowlist secret
    "instagramToken":       {"type": str,  "required": False},
    "facebookToken":        {"type": str,  "required": False},
    "threadsToken":         {"type": str,  "required": False},
    "tumblrApiKey":         {"type": str,  "required": False},
    "tumblrApiSecret":      {"type": str,  "required": False},  # pragma: allowlist secret
    "tumblrBlogName":       {"type": str,  "required": False},
    "postIntervalMinutes":  {"type": int,  "required": False, "min": 1, "max": 1440},
    "maxDailyPosts":        {"type": int,  "required": False, "min": 1, "max": 200},
    "enabledPlatforms":     {"type": list, "required": False},
    "groqApiKey":           {"type": str,  "required": False},
    "mistralApiKey":        {"type": str,  "required": False},
    "dailyBudgetUsd":       {"type": float, "required": False, "min": 0.0},
    "monthlyBudgetUsd":     {"type": float, "required": False, "min": 0.0},
}


def _coerce(value: Any, expected_type: type) -> Any:
    if expected_type is float and isinstance(value, int):
        return float(value)
    return value


def validate(settings: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    for key, rules in _SCHEMA.items():
        value = settings.get(key)
        if value is None:
            if rules.get("required"):
                errors.append(f"{key}: required but missing")
            continue

        coerced = _coerce(value, rules["type"])
        if not isinstance(coerced, rules["type"]):
            errors.append(f"{key}: expected {rules['type'].__name__}, got {type(value).__name__}")
            continue

        if "min" in rules and coerced < rules["min"]:
            errors.append(f"{key}: value {coerced} below minimum {rules['min']}")
        if "max" in rules and coerced > rules["max"]:
            errors.append(f"{key}: value {coerced} exceeds maximum {rules['max']}")

    for key in settings:
        if key not in _SCHEMA:
            warnings.append(f"{key}: unknown key (will be ignored)")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def required_keys() -> list[str]:
    return [k for k, v in _SCHEMA.items() if v.get("required")]


def schema_keys() -> list[str]:
    return list(_SCHEMA.keys())
