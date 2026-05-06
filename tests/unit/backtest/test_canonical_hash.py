"""T011 — canonical TOML hashing must be insensitive to whitespace,
key order, and decimal formatting (FR-B-001)."""

from __future__ import annotations

from auto_invest.backtest.determinism import (
    canonicalise,
    config_hash,
    data_pin_hash,
    run_id,
)


def test_key_order_invariance() -> None:
    a = """
    [section]
    b = "v_b"
    a = "v_a"
    """
    b = """
    [section]
    a = "v_a"
    b = "v_b"
    """
    assert config_hash(a) == config_hash(b)


def test_whitespace_invariance() -> None:
    a = '[s]\nx = "1.0"\n'
    b = '\n\n[s]\n\n  x   =   "1.0"  \n'
    assert config_hash(a) == config_hash(b)


def test_decimal_format_invariance() -> None:
    # Decimal-as-string normalisation: "1.0" / "1.00" / "1" all hash same.
    a = '[s]\nx = "1.0"\n'
    b = '[s]\nx = "1.00"\n'
    c = '[s]\nx = "1"\n'
    assert config_hash(a) == config_hash(b) == config_hash(c)


def test_decimal_negative_normalisation() -> None:
    a = '[s]\nx = "-2.500"\n'
    b = '[s]\nx = "-2.5"\n'
    assert config_hash(a) == config_hash(b)


def test_distinct_values_produce_distinct_hashes() -> None:
    a = '[s]\nx = "1.0"\n'
    b = '[s]\nx = "2.0"\n'
    assert config_hash(a) != config_hash(b)


def test_canonicalise_is_deterministic() -> None:
    text = '[s]\nx = "1.0"\ny = "2.0"\n'
    assert canonicalise(text) == canonicalise(text)


def test_run_id_is_short_and_stable() -> None:
    rid = run_id(
        rule_hash="sha256:abc",
        config_hash_="sha256:def",
        data_pin_hash="sha256:ghi",
    )
    assert len(rid) == 12
    assert run_id(rule_hash="sha256:abc", config_hash_="sha256:def", data_pin_hash="sha256:ghi") == rid


def test_run_id_changes_when_inputs_change() -> None:
    a = run_id(rule_hash="r1", config_hash_="c1", data_pin_hash="d1")
    b = run_id(rule_hash="r1", config_hash_="c1", data_pin_hash="d2")
    assert a != b


def test_data_pin_hash_is_order_invariant() -> None:
    pins_a = [
        {"asset_class": "equity", "venue": "nasdaq", "symbol": "AAPL", "vendor": "kis", "as_of_ts_pin_utc": "2026-05-06T00:00:00Z"},
        {"asset_class": "crypto", "venue": "binance", "symbol": "BTC-USD", "vendor": "crypto_public", "as_of_ts_pin_utc": "2026-05-06T00:00:00Z"},
    ]
    pins_b = list(reversed(pins_a))
    assert data_pin_hash(pins_a) == data_pin_hash(pins_b)
