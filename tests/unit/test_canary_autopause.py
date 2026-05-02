"""Tests for `auto_invest.strategy.canary` (T041)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.config.caps import SizingCaps
from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import StrategyPausedPayload, StrategyPromotedPayload
from auto_invest.strategy.canary import (
    evaluate_session_close,
    initial_state,
    restore_pause_status,
)

CAPS = SizingCaps(
    per_trade_pct=Decimal("5"),
    per_symbol_pct=Decimal("20"),
    global_exposure_pct=Decimal("80"),
    canary_capital_pct=Decimal("5"),
    canary_min_duration_days=10,
    canary_acceptance_drawdown_pct=Decimal("3"),
)


# ------------------------------------------------------ evaluate_session_close


def test_continue_when_value_rises():
    state = initial_state("r1", Decimal("1000"))
    decision = evaluate_session_close(
        state, current_value_usd=Decimal("1010"), caps=CAPS,
    )
    assert decision.action == "CONTINUE"
    assert state.peak_value_usd == Decimal("1010")
    assert state.paused is False


def test_continue_when_drawdown_within_acceptance():
    state = initial_state("r1", Decimal("1000"))
    # 2% drawdown — under the 3% acceptance.
    decision = evaluate_session_close(
        state, current_value_usd=Decimal("980"), caps=CAPS,
    )
    assert decision.action == "CONTINUE"
    assert decision.drawdown_pct == Decimal("2")
    assert state.paused is False


def test_continue_at_exact_acceptance_boundary():
    state = initial_state("r1", Decimal("1000"))
    # Exactly 3% drawdown — boundary is inclusive (<=).
    decision = evaluate_session_close(
        state, current_value_usd=Decimal("970"), caps=CAPS,
    )
    assert decision.action == "CONTINUE"
    assert state.paused is False


def test_pause_when_drawdown_exceeds_acceptance():
    state = initial_state("r1", Decimal("1000"))
    # 4% drawdown — over the 3% acceptance.
    decision = evaluate_session_close(
        state, current_value_usd=Decimal("960"), caps=CAPS,
    )
    assert decision.action == "PAUSE_NOW"
    assert state.paused is True
    assert "drawdown" in decision.reason.lower()


def test_already_paused_stays_paused():
    state = initial_state("r1", Decimal("1000"))
    state.paused = True
    decision = evaluate_session_close(
        state, current_value_usd=Decimal("500"), caps=CAPS,
    )
    assert decision.action == "ALREADY_PAUSED"
    # State must not be tampered with.
    assert state.peak_value_usd == Decimal("1000")


def test_transient_dip_then_recovery_does_not_pause():
    state = initial_state("r1", Decimal("1000"))
    # Day 1: dip 2% (under 3%) — CONTINUE.
    evaluate_session_close(state, current_value_usd=Decimal("980"), caps=CAPS)
    # Day 2: recovers and exceeds prior peak — peak updates.
    evaluate_session_close(state, current_value_usd=Decimal("1010"), caps=CAPS)
    # Day 3: 1% drawdown from new peak (1010) — CONTINUE.
    decision = evaluate_session_close(
        state, current_value_usd=Decimal("1000"), caps=CAPS,
    )
    assert decision.action == "CONTINUE"
    assert state.paused is False
    assert state.peak_value_usd == Decimal("1010")


# ------------------------------------------------------ restore_pause_status


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "t.db")
    db.migrate(c)
    yield c
    c.close()


def test_restore_pause_status_false_when_no_history(conn):
    assert restore_pause_status(conn, "r1") is False


def test_restore_pause_status_true_after_pause_event(conn):
    audit.append(
        conn,
        StrategyPausedPayload(reason="drawdown", metric_value="4.0"),
        rule_id="r1",
    )
    assert restore_pause_status(conn, "r1") is True


def test_restore_pause_status_false_after_promotion(conn):
    audit.append(
        conn,
        StrategyPausedPayload(reason="dd", metric_value="4.0"),
        rule_id="r1",
    )
    audit.append(
        conn,
        StrategyPromotedPayload(from_stage="CANARY", to_stage="FULL_LIVE"),
        rule_id="r1",
    )
    assert restore_pause_status(conn, "r1") is False


def test_restore_pause_status_isolated_per_rule(conn):
    audit.append(
        conn,
        StrategyPausedPayload(reason="dd", metric_value="4.0"),
        rule_id="r1",
    )
    assert restore_pause_status(conn, "r1") is True
    assert restore_pause_status(conn, "r2") is False
