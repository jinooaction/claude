"""Spec 009 T005 — paper-trading audit 페이로드 4종 + K4 additive 계약.

`PAPER_RUN_STARTED`, `PAPER_RUN_STOPPED`, `ORDER_PAPER_FILLED`,
`PAPER_RUN_REJECTED` 네 가지가 spec 009의 유일한 K4 터치다.
이 테스트가 보장하는 것:

  - 각 페이로드의 `event_type` 디스크리미네이터가 상수와 일치.
  - K4 변경이 ADDITIVE — spec 008까지 존재하던 모든 literal 유지.
  - 4종이 정확히 추가되었고 그 외 신규는 없음.
  - 각 페이로드가 `model_dump_json` → `model_validate_json` round-trip 성공.
  - 음수 qty·잘못된 ruleset_sha256 등 유효성 검증.
"""

from __future__ import annotations

import json
import typing

import pytest
from pydantic import ValidationError

from auto_invest.persistence.audit import (
    AnyPayload,
    EventType,
    OrderPaperFilledPayload,
    PaperRunRejectedPayload,
    PaperRunStartedPayload,
    PaperRunStoppedPayload,
)

# ---------------------------------------------------------- K4 additive contract


def test_k4_touch_is_purely_additive() -> None:
    """Spec 009 K4 변경 직전(spec 008까지)에 존재하던 모든 literal이 유지되어야 한다.

    이 테스트가 깨지면 spec 009의 K4 터치가 더 이상 additive가 아니며
    constitution principle IV (append-only audit) 침해.
    """

    literals = set(typing.get_args(EventType))

    pre_009 = {
        # spec 001~006 baseline
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
        "DEPLOY_STARTED",
        "DEPLOY_COMPLETED",
        "DEPLOY_FAILED",
        "DEPLOY_ROLLED_BACK",
        "DEPLOY_KERNEL_TOUCHED",
        # spec 007
        "CANARY_ENTERED",
        "CANARY_PASSED",
        "CANARY_FAILED",
        "CANARY_KERNEL_TOUCH_DETECTED",
        # spec 008
        "BACKTEST_STARTED",
        "BACKTEST_COMPLETED",
        "LLM_CALL_STUBBED",
    }

    missing = pre_009 - literals
    assert not missing, f"K4 touch deleted pre-existing literals: {missing}"


def test_k4_touch_adds_exactly_four_new_literals() -> None:
    literals = set(typing.get_args(EventType))
    added = {
        "PAPER_RUN_STARTED",
        "PAPER_RUN_STOPPED",
        "ORDER_PAPER_FILLED",
        "PAPER_RUN_REJECTED",
    }
    assert added.issubset(literals)


# ---------------------------------------------------------- per-payload smoke


def _started() -> PaperRunStartedPayload:
    return PaperRunStartedPayload(
        pid=12345,
        config_path="/etc/auto-invest/rules.toml",
        ruleset_sha256="a" * 64,
        started_at_utc="2026-05-19T01:00:00.000Z",
        host="vultr-paper-1",
    )


def _stopped() -> PaperRunStoppedPayload:
    return PaperRunStoppedPayload(
        reason="signal_received",
        stopped_at_utc="2026-05-19T14:30:00.000Z",
        session_started_event_id=42,
    )


def _filled() -> OrderPaperFilledPayload:
    return OrderPaperFilledPayload(
        rule_id="RULE_A_BUY_AAPL",
        symbol="AAPL",
        side="BUY",
        qty=5,
        simulated_fill_price_usd="148.20",
        quote_source="ask",
        correlation_id="ord-abc123",
        paper_session_id=42,
    )


def _rejected() -> PaperRunRejectedPayload:
    return PaperRunRejectedPayload(
        attempted_mode="paper",
        reason="mutex_conflict",
        conflicting_event_id=17,
        conflicting_session_started_at="2026-05-19T00:30:00.000Z",
        detail="live worker started at 2026-05-19T00:30:00Z is still running",
    )


@pytest.mark.parametrize(
    "payload_fn,expected_event_type",
    [
        (_started, "PAPER_RUN_STARTED"),
        (_stopped, "PAPER_RUN_STOPPED"),
        (_filled, "ORDER_PAPER_FILLED"),
        (_rejected, "PAPER_RUN_REJECTED"),
    ],
)
def test_payload_event_type_discriminator(payload_fn, expected_event_type) -> None:
    payload = payload_fn()
    assert payload.event_type == expected_event_type


@pytest.mark.parametrize(
    "payload_fn",
    [_started, _stopped, _filled, _rejected],
)
def test_payload_round_trip(payload_fn) -> None:
    payload = payload_fn()
    json_str = payload.model_dump_json()
    reloaded = type(payload).model_validate_json(json_str)
    assert reloaded == payload


def test_any_payload_union_includes_four_new() -> None:
    """Union이 신규 페이로드를 모두 포함해야 audit.append가 받을 수 있다."""
    args = set(typing.get_args(AnyPayload))
    assert PaperRunStartedPayload in args
    assert PaperRunStoppedPayload in args
    assert OrderPaperFilledPayload in args
    assert PaperRunRejectedPayload in args


# ---------------------------------------------------------- validation


def test_filled_payload_rejects_zero_qty() -> None:
    with pytest.raises(ValidationError):
        OrderPaperFilledPayload(
            rule_id="X",
            symbol="AAPL",
            side="BUY",
            qty=0,  # gt=0
            simulated_fill_price_usd="1.00",
            quote_source="ask",
            correlation_id="ord-x",
            paper_session_id=1,
        )


def test_filled_payload_rejects_negative_qty() -> None:
    with pytest.raises(ValidationError):
        OrderPaperFilledPayload(
            rule_id="X",
            symbol="AAPL",
            side="BUY",
            qty=-1,
            simulated_fill_price_usd="1.00",
            quote_source="ask",
            correlation_id="ord-x",
            paper_session_id=1,
        )


def test_started_payload_rejects_wrong_sha_length() -> None:
    with pytest.raises(ValidationError):
        PaperRunStartedPayload(
            pid=1,
            config_path="/x",
            ruleset_sha256="abc",  # 64자 미만
            started_at_utc="2026-05-19T01:00:00.000Z",
            host="h",
        )


def test_filled_payload_rejects_unknown_side() -> None:
    with pytest.raises(ValidationError):
        OrderPaperFilledPayload(
            rule_id="X",
            symbol="AAPL",
            side="HOLD",  # type: ignore[arg-type]
            qty=1,
            simulated_fill_price_usd="1.00",
            quote_source="ask",
            correlation_id="ord-x",
            paper_session_id=1,
        )


def test_filled_payload_rejects_unknown_quote_source() -> None:
    with pytest.raises(ValidationError):
        OrderPaperFilledPayload(
            rule_id="X",
            symbol="AAPL",
            side="BUY",
            qty=1,
            simulated_fill_price_usd="1.00",
            quote_source="midpoint",  # type: ignore[arg-type]
            correlation_id="ord-x",
            paper_session_id=1,
        )


def test_stopped_payload_rejects_unknown_reason() -> None:
    with pytest.raises(ValidationError):
        PaperRunStoppedPayload(
            reason="user_pressed_x",  # type: ignore[arg-type]
            stopped_at_utc="2026-05-19T14:30:00.000Z",
            session_started_event_id=1,
        )


def test_rejected_payload_optional_fields_default_to_none() -> None:
    payload = PaperRunRejectedPayload(
        attempted_mode="paper",
        reason="no_quote_field",
        detail="quote missing ask/bid/last",
    )
    assert payload.conflicting_event_id is None
    assert payload.conflicting_session_started_at is None


# ---------------------------------------------------------- audit.append integration


def test_payloads_persist_to_audit_log(tmp_path) -> None:
    """append()가 4종 모두 받아서 audit_log에 row를 남기는지 통합 검증."""
    from auto_invest.persistence import audit, db

    db_path = tmp_path / "test.db"
    conn = db.get_connection(db_path)
    db.migrate(conn)

    seq_started = audit.append(conn, _started())
    seq_filled = audit.append(
        conn,
        _filled(),
        rule_id="RULE_A_BUY_AAPL",
        symbol="AAPL",
        correlation_id="ord-abc123",
    )
    seq_rejected = audit.append(conn, _rejected())
    seq_stopped = audit.append(conn, _stopped())

    assert seq_started > 0
    assert seq_filled > seq_started
    assert seq_rejected > seq_filled
    assert seq_stopped > seq_rejected

    rows = list(conn.execute(
        "SELECT event_type, payload_json FROM audit_log ORDER BY seq"
    ))
    event_types = [r["event_type"] for r in rows]
    assert event_types == [
        "PAPER_RUN_STARTED",
        "ORDER_PAPER_FILLED",
        "PAPER_RUN_REJECTED",
        "PAPER_RUN_STOPPED",
    ]
    # OrderPaperFilledPayload는 audit_log의 rule_id/symbol/correlation_id 컬럼도 채운다
    filled_row = list(
        conn.execute(
            "SELECT rule_id, symbol, correlation_id FROM audit_log "
            "WHERE event_type = 'ORDER_PAPER_FILLED'"
        )
    )[0]
    assert filled_row["rule_id"] == "RULE_A_BUY_AAPL"
    assert filled_row["symbol"] == "AAPL"
    assert filled_row["correlation_id"] == "ord-abc123"

    # 페이로드 JSON이 round-trip 가능
    started_payload = json.loads(rows[0]["payload_json"])
    assert started_payload["ruleset_sha256"] == "a" * 64
    conn.close()
