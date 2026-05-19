"""Spec 010 T005 — 자동 룰 설계 audit 페이로드 4종 + K4 additive 계약.

`RULE_DESIGN_REQUESTED`, `RULE_DESIGN_COMPLETED`, `RULE_DESIGN_REJECTED`,
`RULE_DESIGN_DEPLOYED` 4종이 spec 010의 유일한 K4 터치다 (K3 코드는 무수정).

검증:
  - 각 페이로드의 `event_type` 디스크리미네이터.
  - K4 변경이 ADDITIVE — spec 009까지 32종 literal 모두 유지.
  - 4종이 정확히 추가, 그 외 신규 없음.
  - round-trip (model_dump_json → model_validate_json) 성공.
  - validation: cost_usd, retry_index 범위 등.
"""

from __future__ import annotations

import json
import typing

import pytest
from pydantic import ValidationError

from auto_invest.persistence.audit import (
    AnyPayload,
    EventType,
    RuleDesignCompletedPayload,
    RuleDesignDeployedPayload,
    RuleDesignRejectedPayload,
    RuleDesignRequestedPayload,
)

# ---------------------------------------------------------- K4 additive contract


def test_k4_touch_is_purely_additive() -> None:
    """spec 010 K4 변경 직전(spec 009까지)에 존재하던 모든 literal이 유지."""

    literals = set(typing.get_args(EventType))

    pre_010 = {
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
        # spec 009
        "PAPER_RUN_STARTED",
        "PAPER_RUN_STOPPED",
        "ORDER_PAPER_FILLED",
        "PAPER_RUN_REJECTED",
    }

    missing = pre_010 - literals
    assert not missing, f"K4 touch deleted pre-existing literals: {missing}"


def test_k4_touch_adds_exactly_four_new_literals() -> None:
    literals = set(typing.get_args(EventType))
    added = {
        "RULE_DESIGN_REQUESTED",
        "RULE_DESIGN_COMPLETED",
        "RULE_DESIGN_REJECTED",
        "RULE_DESIGN_DEPLOYED",
    }
    assert added.issubset(literals)


# ---------------------------------------------------------- per-payload smoke


def _requested() -> RuleDesignRequestedPayload:
    return RuleDesignRequestedPayload(
        intent="자본 100달러, 미국 대형주 분산, 매주 적립, 위험 보통",
        requested_at_utc="2026-05-19T01:00:00.000Z",
        kis_balance_usd="102.45",
        kis_holdings=[{"symbol": "VOO", "qty": 0.2, "avg_cost_usd": "450.00"}],
        host="vultr-1",
    )


def _completed() -> RuleDesignCompletedPayload:
    return RuleDesignCompletedPayload(
        intent="자본 100달러, 미국 대형주 분산, 매주 적립, 위험 보통",
        interpretation={
            "max_drawdown_pct": 5,
            "per_symbol_pct": 20,
            "universe": ["VOO", "QQQ", "SPY"],
        },
        generated_rules_toml="[caps]\nper_trade_pct = 5\n...",
        model_id="claude-opus-4-7",
        tokens_input=1234,
        tokens_output=567,
        cost_usd="0.012",
        retry_index=1,
        paper_run_session_id=99,
    )


def _rejected() -> RuleDesignRejectedPayload:
    return RuleDesignRejectedPayload(
        reason="mutex_conflict",
        detail="다른 design 명령이 이미 실행 중입니다 (seq=41).",
        conflicting_event_id=41,
    )


def _deployed() -> RuleDesignDeployedPayload:
    return RuleDesignDeployedPayload(
        design_session_id=42,
        live_session_id=58,
        deployed_at_utc="2026-05-19T14:30:00.000Z",
        total_capital_usd="102.45",
    )


@pytest.mark.parametrize(
    "payload_fn,expected_event_type",
    [
        (_requested, "RULE_DESIGN_REQUESTED"),
        (_completed, "RULE_DESIGN_COMPLETED"),
        (_rejected, "RULE_DESIGN_REJECTED"),
        (_deployed, "RULE_DESIGN_DEPLOYED"),
    ],
)
def test_payload_event_type_discriminator(payload_fn, expected_event_type) -> None:
    assert payload_fn().event_type == expected_event_type


@pytest.mark.parametrize(
    "payload_fn", [_requested, _completed, _rejected, _deployed]
)
def test_payload_round_trip(payload_fn) -> None:
    p = payload_fn()
    reloaded = type(p).model_validate_json(p.model_dump_json())
    assert reloaded == p


def test_any_payload_union_includes_four_new() -> None:
    args = set(typing.get_args(AnyPayload))
    assert RuleDesignRequestedPayload in args
    assert RuleDesignCompletedPayload in args
    assert RuleDesignRejectedPayload in args
    assert RuleDesignDeployedPayload in args


# ---------------------------------------------------------- validation


def test_completed_rejects_retry_index_out_of_range() -> None:
    with pytest.raises(ValidationError):
        RuleDesignCompletedPayload(
            intent="x",
            interpretation={},
            generated_rules_toml="...",
            model_id="claude-opus-4-7",
            tokens_input=1,
            tokens_output=1,
            cost_usd="0.01",
            retry_index=4,  # 1~3만 허용
        )


def test_completed_rejects_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        RuleDesignCompletedPayload(
            intent="x",
            interpretation={},
            generated_rules_toml="...",
            model_id="claude-opus-4-7",
            tokens_input=-1,
            tokens_output=1,
            cost_usd="0.01",
            retry_index=1,
        )


def test_rejected_rejects_unknown_reason() -> None:
    with pytest.raises(ValidationError):
        RuleDesignRejectedPayload(
            reason="something_else",  # type: ignore[arg-type]
            detail="x",
        )


def test_rejected_optional_fields_default_none() -> None:
    p = RuleDesignRejectedPayload(reason="claude_api_error", detail="timeout")
    assert p.retry_index is None
    assert p.conflicting_event_id is None


# ---------------------------------------------------------- audit.append integration


def test_payloads_persist_to_audit_log(tmp_path) -> None:
    """append()가 4종 모두 받아서 audit_log에 row를 남기는지 통합 검증."""
    from auto_invest.persistence import audit, db

    conn = db.get_connection(tmp_path / "test.db")
    db.migrate(conn)

    seq_req = audit.append(conn, _requested())
    seq_com = audit.append(conn, _completed())
    seq_rej = audit.append(conn, _rejected())
    seq_dep = audit.append(conn, _deployed())

    assert seq_req > 0
    assert seq_com > seq_req
    assert seq_rej > seq_com
    assert seq_dep > seq_rej

    rows = list(conn.execute(
        "SELECT event_type FROM audit_log ORDER BY seq"
    ))
    assert [r["event_type"] for r in rows] == [
        "RULE_DESIGN_REQUESTED",
        "RULE_DESIGN_COMPLETED",
        "RULE_DESIGN_REJECTED",
        "RULE_DESIGN_DEPLOYED",
    ]

    # COMPLETED row의 interpretation·tokens가 round-trip
    completed_row = list(conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type = 'RULE_DESIGN_COMPLETED'"
    ))[0]
    payload = json.loads(completed_row["payload_json"])
    assert payload["interpretation"]["max_drawdown_pct"] == 5
    assert payload["tokens_input"] == 1234

    conn.close()
