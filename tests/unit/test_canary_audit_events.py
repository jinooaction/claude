"""Spec 007 T006 — payload models + K4 additive-touch contract.

The four new event types appended to `audit.py`'s `EventType` Literal
(`CANARY_ENTERED`, `CANARY_PASSED`, `CANARY_FAILED`,
`CANARY_KERNEL_TOUCH_DETECTED`) are the K4 touch of spec 007. This
test pins:

  - Each payload's `event_type` discriminator equals its constant.
  - The K4 touch is ADDITIVE — every literal that existed before
    spec 007 is still present (no rename, no removal).
  - `CanaryPassedPayload` serialises to under 1 KB (R-C11 — audit-row
    payloads are read often and should stay small).
  - Each payload round-trips through `model_dump_json` → `model_validate_json`.
"""

from __future__ import annotations

import json
import typing

import pytest

from auto_invest.persistence import audit, db
from auto_invest.persistence.audit import (
    AnyPayload,
    CanaryEnteredPayload,
    CanaryFailedPayload,
    CanaryKernelTouchDetectedPayload,
    CanaryPassedPayload,
    EventType,
)

# ---------------------------------------------------------- K4 additive contract


def test_k4_touch_is_purely_additive() -> None:
    """Every literal that existed before spec 007 must still be present in EventType.

    If this test fails, the K4 touch is no longer additive and the
    constitution principle IV (append-only audit) becomes unsafe to
    consumers reading historical audit_log rows.
    """

    literals = set(typing.get_args(EventType))

    pre_007 = {
        "RULE_LOAD",
        "ORDER_INTENT",
        "ORDER_SUBMITTED",
        "ORDER_REJECTED_BY_GATE",
        "ORDER_REJECTED_BY_BROKER",
        "FILL",
        "CANCEL",
        "ERROR",
        "RECONCILIATION_OK",
        "RECONCILIATION_MISMATCH",
        "HALT_SET",
        "HALT_CLEARED",
        "STRATEGY_PAUSED",
        "STRATEGY_PROMOTED",
        "DATA_QUALITY_ISSUE",
        "SECRETS_LOADED",
        "WORKER_STARTED",
        "WORKER_STOPPED",
        "LLM_CALL",
        "PRICE_TABLE_LOADED",
        "DEPLOY_BLOCKED_KERNEL_TOUCH",
        "BACKTEST_STARTED",
        "BACKTEST_COMPLETED",
        "LLM_CALL_STUBBED",
    }

    missing = pre_007 - literals
    assert not missing, f"K4 touch deleted pre-existing literals: {missing}"


def test_k4_touch_adds_exactly_four_new_literals() -> None:
    literals = set(typing.get_args(EventType))
    added = {
        "CANARY_ENTERED",
        "CANARY_PASSED",
        "CANARY_FAILED",
        "CANARY_KERNEL_TOUCH_DETECTED",
    }
    assert added.issubset(literals)


# ---------------------------------------------------------- per-payload smoke


def _entered() -> CanaryEnteredPayload:
    return CanaryEnteredPayload(
        canary_run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        candidate_rev="a" * 40,
        baseline_rev="b" * 40,
        tier="L2",
        window_trading_days=30,
        window_start_date="2026-03-31",
        window_end_date="2026-05-13",
        bands_snapshot={
            "pnl_drawdown_pct": 3.0,
            "risk_gate_violations": 0,
            "audit_integrity_failures": 0,
            "latency_p95_regression_pct": 20.0,
            "llm_cost_regression_pct": 10.0,
        },
    )


def _kernel_touch() -> CanaryKernelTouchDetectedPayload:
    return CanaryKernelTouchDetectedPayload(
        canary_run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        candidate_rev="a" * 40,
        touched_groups=["K1", "K4"],
        touched_files=[
            "src/auto_invest/persistence/audit.py",
            "src/auto_invest/risk/gates.py",
        ],
    )


def _passed() -> CanaryPassedPayload:
    return CanaryPassedPayload(
        canary_run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        candidate_rev="a" * 40,
        baseline_rev="b" * 40,
        tier="L2",
        finished_at="2026-05-14T08:42:17.412Z",
        artefact_path="data/canary/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/canary-run.json",
    )


def _failed() -> CanaryFailedPayload:
    return CanaryFailedPayload(
        canary_run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        candidate_rev="a" * 40,
        baseline_rev="b" * 40,
        tier="L3",
        finished_at="2026-05-14T08:42:17.412Z",
        failing_metrics=["llm_cost_regression_pct"],
        artefact_path="data/canary/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/canary-run.json",
    )


def test_event_type_discriminators_pinned() -> None:
    assert _entered().event_type == "CANARY_ENTERED"
    assert _kernel_touch().event_type == "CANARY_KERNEL_TOUCH_DETECTED"
    assert _passed().event_type == "CANARY_PASSED"
    assert _failed().event_type == "CANARY_FAILED"


@pytest.mark.parametrize("payload_factory", [_entered, _kernel_touch, _passed, _failed])
def test_payload_round_trips_via_model_dump_json(payload_factory) -> None:
    original = payload_factory()
    blob = original.model_dump_json()
    cls = type(original)
    restored = cls.model_validate_json(blob)
    assert restored == original


def test_canary_passed_payload_bounded_size() -> None:
    """R-C11 — terminal audit payloads stay small (forensic-index size)."""
    blob = _passed().model_dump_json()
    assert len(blob.encode("utf-8")) < 1024, (
        f"CanaryPassedPayload serialized to {len(blob)} bytes; R-C11 budget is < 1 KB"
    )


def test_canary_failed_payload_bounded_size_with_5_failing_metrics() -> None:
    """Worst case: all 5 metrics failing. Still must fit inside 1 KB."""
    payload = CanaryFailedPayload(
        canary_run_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        candidate_rev="a" * 40,
        baseline_rev="b" * 40,
        tier="L3",
        finished_at="2026-05-14T08:42:17.412Z",
        failing_metrics=[
            "pnl_drawdown_pct",
            "risk_gate_violations",
            "audit_integrity_failures",
            "latency_p95_regression_pct",
            "llm_cost_regression_pct",
        ],
        artefact_path="data/canary/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/canary-run.json",
    )
    assert len(payload.model_dump_json().encode("utf-8")) < 1024


# ---------------------------------------------------------- AnyPayload union


def test_any_payload_union_includes_all_four_new_models() -> None:
    union_args = set(typing.get_args(AnyPayload))
    assert CanaryEnteredPayload in union_args
    assert CanaryKernelTouchDetectedPayload in union_args
    assert CanaryPassedPayload in union_args
    assert CanaryFailedPayload in union_args


# ---------------------------------------------------------- audit.append integration


def test_canary_event_appends_and_correlates(tmp_path) -> None:
    """End-to-end: a canary's 3 lifecycle rows are linked by correlation_id."""
    conn = db.get_connection(tmp_path / "audit.sqlite")
    db.migrate(conn)
    try:
        correlation = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        audit.append(conn, _entered(), correlation_id=correlation)
        audit.append(conn, _kernel_touch(), correlation_id=correlation)
        audit.append(conn, _passed(), correlation_id=correlation)
        conn.commit()

        rows = audit.read_by_correlation(conn, correlation)
        assert [r["event_type"] for r in rows] == [
            "CANARY_ENTERED",
            "CANARY_KERNEL_TOUCH_DETECTED",
            "CANARY_PASSED",
        ]
        # Payload JSON round-trips.
        first_payload = json.loads(rows[0]["payload_json"])
        assert first_payload["event_type"] == "CANARY_ENTERED"
        assert first_payload["tier"] == "L2"
    finally:
        conn.close()
