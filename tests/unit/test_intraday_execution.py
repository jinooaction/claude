"""Deterministic execution invariants independent of account credentials."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from auto_invest.execution.intraday import (
    Decision,
    Observation,
    validate_decision,
    validate_observation,
)

NOW = datetime(2026, 9, 8, 15, 0, tzinfo=UTC)
FP = "a" * 64


@pytest.mark.parametrize("value", [float("nan"), Decimal("NaN"), Decimal("Infinity"), 0, -1])
def test_invalid_mark_rejected(value):
    with pytest.raises(ValueError):
        validate_observation(
            Observation(NOW, Decimal("1000"), Decimal("1000"), {}, {"SPY": value}, ()), NOW, {"SPY"}
        )


@pytest.mark.parametrize("qty", [True, -1, 1.5])
def test_target_is_whole_nonnegative(qty):
    with pytest.raises(ValueError):
        validate_decision(Decision(FP, NOW, {"SPY": qty}, {"SPY": Decimal("100")}), FP)


def test_foreign_symbol_and_identity_rejected():
    with pytest.raises(ValueError):
        validate_decision(Decision(FP, NOW, {"UNKNOWN": 1}, {"UNKNOWN": Decimal("100")}), FP)
    with pytest.raises(ValueError):
        validate_decision(Decision("b" * 64, NOW, {"SPY": 1}, {"SPY": Decimal("100")}), FP)


@pytest.mark.parametrize("offset", [-31, 1])
def test_observation_timestamp_fail_closed(offset):
    with pytest.raises(ValueError):
        validate_observation(
            Observation(
                NOW + timedelta(seconds=offset),
                Decimal("1000"),
                Decimal("1000"),
                {},
                {"SPY": Decimal("100")},
                (),
            ),
            NOW,
            {"SPY"},
        )


def signal_fixture():
    from pathlib import Path

    from auto_invest.analytics.intraday_paper_challenger import (
        build_candidate_registry,
        load_preregistration,
    )
    from auto_invest.market_data.intraday import SYMBOLS, iso

    candidate = build_candidate_registry(
        load_preregistration(
            Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
        )
    )[0]
    opening = NOW.replace(hour=13, minute=30)
    bars = [
        dict(
            symbol=s,
            timestamp_utc=iso(opening + timedelta(minutes=5 * n)),
            open=100 + n,
            high=102 + n,
            low=99 + n,
            close=101 + n,
            volume=100000,
        )
        for n in range(9)
        for s in SYMBOLS
    ]
    return candidate, bars, opening + timedelta(minutes=45)


def test_strategy_signal_uses_confirmed_positions_and_closed_bars():
    from auto_invest.execution.intraday_signals import compile_decision, execution_fingerprint

    candidate, bars, now = signal_fixture()
    provider = "kis-nasdaq-partial-unadjusted"
    decision = compile_decision(
        candidate,
        provider=provider,
        bars=bars,
        now=now,
        owned={},
        entry_times={},
        entered_symbols=set(),
        capital=Decimal("10000"),
        cash=Decimal("10000"),
    )
    assert decision.fingerprint == execution_fingerprint(candidate, provider)
    assert all(q > 0 for q in decision.targets.values())
    with pytest.raises(ValueError, match="SIGNAL_BAR_GAP"):
        compile_decision(
            candidate,
            provider=provider,
            bars=bars[1:],
            now=now,
            owned={},
            entry_times={},
            entered_symbols=set(),
            capital=Decimal("10000"),
            cash=Decimal("10000"),
        )


def test_strategy_does_not_use_future_bar_or_foreign_provider():
    from auto_invest.execution.intraday_signals import compile_decision, execution_fingerprint

    candidate, bars, now = signal_fixture()
    with pytest.raises(ValueError):
        compile_decision(
            candidate,
            provider="kis-nasdaq-partial-unadjusted",
            bars=bars,
            now=now - timedelta(minutes=1),
            owned={},
            entry_times={},
            entered_symbols=set(),
            capital=Decimal("10000"),
            cash=Decimal("10000"),
        )
    with pytest.raises(ValueError):
        execution_fingerprint(candidate, "invented-consolidated-data")
