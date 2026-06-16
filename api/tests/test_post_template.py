from api.utils.post_template import render, render_named, list_templates, extract_vars, missing_vars
import pytest


def test_render_simple():
    assert render("Hello {{ name }}!", {"name": "World"}) == "Hello World!"


def test_render_multiple_vars():
    result = render("{{ a }} + {{ b }}", {"a": "1", "b": "2"})
    assert result == "1 + 2"


def test_render_missing_var_preserved():
    result = render("{{ title }} — {{ price }}", {"title": "Item"})
    assert "{{price}}" in result or "{{ price }}" in result


def test_render_extra_vars_ignored():
    result = render("{{ title }}", {"title": "T", "extra": "X"})
    assert result == "T"


def test_render_empty_template():
    assert render("", {"a": "b"}) == ""


def test_render_no_vars():
    assert render("plain text", {}) == "plain text"


def test_render_named_standard():
    result = render_named("standard", {"title": "Hat", "price": "$10", "description": "Nice", "url": "https://x.com"})
    assert "Hat" in result
    assert "$10" in result


def test_render_named_minimal():
    result = render_named("minimal", {"title": "T", "price": "$5", "url": "https://x.com"})
    assert "T" in result
    assert "https://x.com" in result


def test_render_named_unknown_raises():
    with pytest.raises(KeyError):
        render_named("nonexistent", {})


def test_list_templates_returns_list():
    assert isinstance(list_templates(), list)


def test_list_templates_includes_standard():
    assert "standard" in list_templates()


def test_list_templates_sorted():
    t = list_templates()
    assert t == sorted(t)


def test_extract_vars_empty():
    assert extract_vars("no vars here") == []


def test_extract_vars_finds_all():
    vars_ = extract_vars("{{ title }} costs {{ price }} at {{ url }}")
    assert sorted(vars_) == ["price", "title", "url"]


def test_extract_vars_deduplicates():
    vars_ = extract_vars("{{ a }} and {{ a }}")
    assert vars_ == ["a"]


def test_missing_vars_all_present():
    assert missing_vars("{{ title }}", {"title": "T"}) == []


def test_missing_vars_detects_missing():
    missing = missing_vars("{{ title }} — {{ price }}", {"title": "T"})
    assert "price" in missing
