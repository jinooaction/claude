"""Data-model tests: Decimal canonicalisation + Literal strictness."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from auto_invest.backtest.data_model import (
    BacktestRun,
    OHLCVBar,
    RuleBacktestResult,
    canonicalise_decimal,
)


def test_canonicalise_decimal_pads_to_six_places():
    assert canonicalise_decimal(Decimal("1.5")) == "1.500000"
    assert canonicalise_decimal(Decimal("0")) == "0.000000"
    assert canonicalise_decimal(Decimal("-0.012")) == "-0.012000"


def test_canonicalise_decimal_accepts_string_int_float():
    assert canonicalise_decimal("1.5") == "1.500000"
    assert canonicalise_decimal(2) == "2.000000"
    # float path is allowed but operator should prefer Decimal/str.
    assert canonicalise_decimal(1.5) == "1.500000"


def test_canonicalise_uses_quantize_not_format_string_rounding():
    # 0.5 banker's rounding vs round-half-up: Decimal.quantize uses
    # ROUND_HALF_EVEN by default, which is what we want for stability.
    assert canonicalise_decimal(Decimal("0.0000005")) == "0.000000"  # half-even down
    assert canonicalise_decimal(Decimal("0.0000015")) == "0.000002"  # half-even up


def test_ohlcv_bar_rejects_negative_price():
    with pytest.raises(ValidationError):
        OHLCVBar(
            symbol="AAPL",
            session_date=date(2024, 1, 2),
            open=Decimal("-1"),
            high=Decimal("2"),
            low=Decimal("0.5"),
            close=Decimal("1.5"),
            volume=100,
            session_schedule_tag="regular",
        )


def test_ohlcv_bar_accepts_valid_row():
    bar = OHLCVBar(
        symbol="AAPL",
        session_date=date(2024, 1, 2),
        open=Decimal("185.64"),
        high=Decimal("188.44"),
        low=Decimal("183.89"),
        close=Decimal("185.64"),
        volume=82488700,
        session_schedule_tag="regular",
    )
    assert bar.symbol == "AAPL"


def test_rule_backtest_result_rejects_fill_count_exceeding_orders():
    with pytest.raises(ValidationError, match=r"fill_count 10 > order_count 5"):
        RuleBacktestResult(
            rule_id="r1",
            symbol="AAPL",
            total_return_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            sharpe_ratio=Decimal("0"),
            order_count=5,
            fill_count=10,
            notional_traded_usd=Decimal("0"),
        )


def test_backtest_run_locks_fill_model_literal():
    with pytest.raises(ValidationError):
        BacktestRun(
            run_id="r1",
            invoker="cli",
            ruleset_path=Path("/tmp/rules.toml"),
            ruleset_sha256="00" * 32,
            dataset_version="00" * 32,
            date_start=date(2024, 1, 1),
            date_end=date(2024, 12, 31),
            start_ts=datetime(2026, 5, 13, tzinfo=UTC),
            fill_model="optimistic_mid",  # type: ignore[arg-type]
        )


def test_backtest_run_locks_judgment_mode_literal():
    with pytest.raises(ValidationError):
        BacktestRun(
            run_id="r1",
            invoker="cli",
            ruleset_path=Path("/tmp/rules.toml"),
            ruleset_sha256="00" * 32,
            dataset_version="00" * 32,
            date_start=date(2024, 1, 1),
            date_end=date(2024, 12, 31),
            start_ts=datetime(2026, 5, 13, tzinfo=UTC),
            judgment_mode="live",  # type: ignore[arg-type]
        )


def test_backtest_run_locks_invoker_literal():
    with pytest.raises(ValidationError):
        BacktestRun(
            run_id="r1",
            invoker="other",  # type: ignore[arg-type]
            ruleset_path=Path("/tmp/rules.toml"),
            ruleset_sha256="00" * 32,
            dataset_version="00" * 32,
            date_start=date(2024, 1, 1),
            date_end=date(2024, 12, 31),
            start_ts=datetime(2026, 5, 13, tzinfo=UTC),
        )
