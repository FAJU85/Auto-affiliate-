from api.utils.config_validator import validate, required_keys, schema_keys


def test_validate_empty_is_valid():
    r = validate({})
    assert r["valid"] is True
    assert r["errors"] == []


def test_validate_structure():
    r = validate({})
    for key in ("valid", "errors", "warnings", "error_count", "warning_count"):
        assert key in r


def test_validate_wrong_type():
    r = validate({"postIntervalMinutes": "not_an_int"})
    assert r["valid"] is False
    assert r["error_count"] >= 1


def test_validate_below_min():
    r = validate({"postIntervalMinutes": 0})
    assert r["valid"] is False


def test_validate_above_max():
    r = validate({"maxDailyPosts": 999})
    assert r["valid"] is False


def test_validate_valid_int_in_range():
    r = validate({"postIntervalMinutes": 60})
    assert r["valid"] is True


def test_validate_valid_string():
    r = validate({"bskyHandle": "user.bsky.social"})
    assert r["valid"] is True


def test_validate_float_budget():
    r = validate({"dailyBudgetUsd": 5.0})
    assert r["valid"] is True


def test_validate_int_coerced_to_float():
    r = validate({"dailyBudgetUsd": 5})
    assert r["valid"] is True


def test_validate_negative_budget():
    r = validate({"dailyBudgetUsd": -1.0})
    assert r["valid"] is False


def test_validate_unknown_key_warning():
    r = validate({"unknownField": "foo"})
    assert r["warning_count"] >= 1
    assert any("unknownField" in w for w in r["warnings"])


def test_validate_list_type():
    r = validate({"enabledPlatforms": ["bluesky", "x"]})
    assert r["valid"] is True


def test_validate_list_wrong_type():
    r = validate({"enabledPlatforms": "bluesky"})
    assert r["valid"] is False


def test_required_keys_is_list():
    assert isinstance(required_keys(), list)


def test_schema_keys_nonempty():
    assert len(schema_keys()) > 10


def test_schema_keys_includes_bluesky():
    assert "bskyHandle" in schema_keys()
