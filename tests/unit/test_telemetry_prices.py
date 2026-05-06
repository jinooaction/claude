"""Tests for `auto_invest.telemetry.prices` (T121)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.telemetry.prices import PriceTableError, load_prices


@pytest.fixture
def tmp_prices(tmp_path: Path) -> Path:
    p = tmp_path / "prices.toml"
    p.write_text(
        """
["claude-opus-4-7"]
usd_per_million_input_tokens = 15.0
usd_per_million_output_tokens = 75.0
usd_per_million_cache_read_tokens = 1.5
usd_per_million_cache_write_tokens = 18.75
""",
        encoding="utf-8",
    )
    return p


def test_load_default_table_succeeds():
    table = load_prices(Path("config/llm_prices.toml"))
    assert "claude-opus-4-7" in table.entries
    assert "claude-sonnet-4-6" in table.entries
    assert "claude-haiku-4-5-20251001" in table.entries
    assert table.sha256 != ""


def test_unknown_model_returns_none(tmp_prices: Path):
    table = load_prices(tmp_prices)
    cost = table.compute_cost(
        "claude-fictional-1-0",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    assert cost is None


def test_zero_tokens_returns_zero(tmp_prices: Path):
    table = load_prices(tmp_prices)
    cost = table.compute_cost(
        "claude-opus-4-7",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    assert cost == Decimal("0.000000")


def test_cache_read_uses_cache_read_price(tmp_prices: Path):
    table = load_prices(tmp_prices)
    # 1_000_000 cache_read tokens at $1.5/MTok = $1.50
    cost = table.compute_cost(
        "claude-opus-4-7",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=1_000_000,
        cache_write_tokens=0,
    )
    assert cost == Decimal("1.500000")


def test_mixed_costs(tmp_prices: Path):
    table = load_prices(tmp_prices)
    # 1_000_000 input ($15) + 500_000 output ($37.5) = $52.5
    cost = table.compute_cost(
        "claude-opus-4-7",
        input_tokens=1_000_000,
        output_tokens=500_000,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    assert cost == Decimal("52.500000")


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(PriceTableError):
        load_prices(tmp_path / "nope.toml")


def test_negative_price_rejected(tmp_path: Path):
    p = tmp_path / "bad.toml"
    p.write_text(
        """
["m"]
usd_per_million_input_tokens = -1.0
usd_per_million_output_tokens = 1.0
usd_per_million_cache_read_tokens = 1.0
usd_per_million_cache_write_tokens = 1.0
""",
        encoding="utf-8",
    )
    with pytest.raises(PriceTableError):
        load_prices(p)


def test_empty_table_rejected(tmp_path: Path):
    p = tmp_path / "empty.toml"
    p.write_text("", encoding="utf-8")
    with pytest.raises(PriceTableError):
        load_prices(p)
