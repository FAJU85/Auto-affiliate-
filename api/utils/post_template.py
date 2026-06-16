import re

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

_BUILTIN_TEMPLATES: dict[str, str] = {
    "standard": "🛍️ {{ title }} — {{ price }}\n{{ description }}\n👉 {{ url }}",
    "deal": "🔥 DEAL: {{ title }}\nWas {{ old_price }}, now {{ price }}!\n{{ url }}",
    "minimal": "{{ title }} — {{ price }}\n{{ url }}",
    "question": "Looking for {{ category }}? Check out {{ title }} at {{ price }}!\n{{ url }}",
    "story": "I found {{ title }} for only {{ price }}. {{ description }}\n{{ url }}",
}


def render(template: str, variables: dict) -> str:
    def _replace(m: re.Match) -> str:
        key = m.group(1)
        return str(variables.get(key, f"{{{{{key}}}}}"))
    return _VAR_RE.sub(_replace, template)


def render_named(name: str, variables: dict) -> str:
    tpl = _builtin_templates().get(name)
    if tpl is None:
        raise KeyError(f"Unknown template: {name!r}")
    return render(tpl, variables)


def _builtin_templates() -> dict[str, str]:
    return dict(_BUILTIN_TEMPLATES)


def list_templates() -> list[str]:
    return sorted(_BUILTIN_TEMPLATES.keys())


def extract_vars(template: str) -> list[str]:
    return sorted(set(_VAR_RE.findall(template)))


def missing_vars(template: str, variables: dict) -> list[str]:
    return [v for v in extract_vars(template) if v not in variables]
