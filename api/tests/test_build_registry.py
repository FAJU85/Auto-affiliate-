"""Tests for api/utils/build_registry.py"""

from api.utils.build_registry import get_build, get_builds


def test_get_builds_returns_list():
    result = get_builds()
    assert isinstance(result, list)
    assert len(result) > 0


def test_all_builds_have_required_keys():
    required = {"number", "title", "description", "files_added", "test_count"}
    for build in get_builds():
        assert required.issubset(build.keys()), f"Build {build.get('number')} missing keys"


def test_build_numbers_are_unique():
    numbers = [b["number"] for b in get_builds()]
    assert len(numbers) == len(set(numbers))


def test_total_build_count():
    assert len(get_builds()) == 30


def test_get_build_returns_correct_build():
    build = get_build(1)
    assert build is not None
    assert build["number"] == 1


def test_get_build_missing_returns_none():
    assert get_build(999) is None


def test_builds_sorted_by_number():
    numbers = [b["number"] for b in get_builds()]
    assert numbers == sorted(numbers)


def test_build_30_exists():
    build = get_build(30)
    assert build is not None
    assert "build history" in build["description"].lower() or "registry" in build["description"].lower()
