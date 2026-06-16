import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.currency_converter as m
    importlib.reload(m)
    return m


def test_convert_same_currency(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.convert(100.0, "USD", "USD") == 100.0


def test_convert_usd_to_eur(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.convert(100.0, "USD", "EUR")
    assert result > 0
    assert result < 100.0  # EUR weaker than USD in defaults


def test_convert_eur_to_usd(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.convert(92.0, "EUR", "USD")
    assert abs(result - 100.0) < 1.0


def test_convert_unknown_from(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        m.convert(100.0, "XYZ", "USD")


def test_convert_unknown_to(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        m.convert(100.0, "USD", "XYZ")


def test_set_and_get_rate(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.set_rate("TST", 2.0)
    assert m.get_rate("TST") == 2.0


def test_get_rate_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_rate("UNKNOWN") is None


def test_custom_rate_used_in_convert(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.set_rate("TST", 2.0)
    result = m.convert(100.0, "USD", "TST")
    assert result == 200.0


def test_format_price_usd(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.format_price(19.99, "USD") == "$19.99"


def test_format_price_eur(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.format_price(9.99, "EUR") == "€9.99"


def test_format_price_jpy_no_decimals(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.format_price(1000, "JPY") == "¥1,000"


def test_convert_and_format(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.convert_and_format(10.0, "USD", "USD")
    assert result == "$10.00"


def test_list_currencies(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    currencies = m.list_currencies()
    assert "USD" in currencies
    assert "EUR" in currencies
    assert currencies == sorted(currencies)


def test_rates_summary(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.rates_summary()
    assert s["base"] == "USD"
    assert s["currencies"] >= 14
    assert "USD" in s["rates"]
