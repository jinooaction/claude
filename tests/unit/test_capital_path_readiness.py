"""스펙 076 — 자본 경로 준비도 루프 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.capital_path_readiness import (
    LIVE_STATUS_BLOCKED,
    LIVE_STATUS_PREVIEW,
    STATE_ACCUMULATING_EDGE,
    STATE_LIVE_BLOCKED,
    STATE_UNKNOWN,
    build_capital_path_readiness,
)

NOW = datetime(2026, 7, 1, 8, 10, 0, tzinfo=UTC)


def _fenced(header: str, payload: dict) -> str:
    return f"## {header}\n\n```json\n{json.dumps(payload, ensure_ascii=False)}\n```\n"


def _money_path(stage: str = "ACCUMULATING_EDGE", status: str = LIVE_STATUS_PREVIEW) -> str:
    return _fenced(
        "결정 JSON",
        {
            "schema_version": "1.0",
            "stage": stage,
            "blocking_gate": "전진 관측 부족: 13/20",
            "next_action": "기존 전진 관측과 자본 사다리 게이트를 계속 사용한다.",
            "live_money_state": {
                "status": status,
                "can_submit_real_orders": False,
                "required_gates": ["operator-live-toggle"],
            },
            "gates": [{"name": "전진 관측 수", "status": "PENDING", "reason": "13/20"}],
        },
    )


def test_accumulating_edge_preview_only_uses_existing_gates():
    report = build_capital_path_readiness(
        {
            "money-path": _money_path(),
            "reassign": _fenced("5중 게이트 결정 JSON", {"action": "HOLD"}),
            "evolution-backlog": json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "domain_key": "live_readiness",
                            "status": "new",
                            "score": 597,
                            "title_ko": "money path readiness/gate alignment",
                            "next_action_ko": "자본 경로 gate alignment를 검증한다.",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "evolution-ledger": json.dumps({"entries": []}),
            "autonomous-promotion": json.dumps({"actions": []}),
        },
        now=NOW,
    )

    assert report.readiness_state == STATE_ACCUMULATING_EDGE
    assert report.live_money_status == LIVE_STATUS_PREVIEW
    assert report.capital_ladder_stage == "ACCUMULATING_EDGE"
    assert report.blocking_gate == "전진 관측 부족: 13/20"
    assert report.required_existing_gates == [
        "money-path",
        "edge-autoarm",
        "reassign",
        "operator-live-toggle",
    ]
    assert [c.candidate_id for c in report.priority_candidates] == [
        "candidate-fd04772a23c5"
    ]
    assert report.suppressed_candidates == []


def test_learning_ledger_suppresses_rejected_candidates():
    report = build_capital_path_readiness(
        {
            "money-path": _money_path(),
            "evolution-backlog": json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "domain_key": "live_readiness",
                            "status": "new",
                            "score": 597,
                        },
                        {
                            "candidate_id": "candidate-1ed634d8bf6d",
                            "domain_key": "strategy_design",
                            "status": "rejected",
                            "score": 618,
                        },
                    ]
                }
            ),
            "evolution-ledger": json.dumps(
                {
                    "entries": [
                        {
                            "candidate_id": "candidate-1ed634d8bf6d",
                            "domain_key": "strategy_design",
                            "status": "rejected",
                            "reason_ko": "machine validation 실패",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "autonomous-promotion": json.dumps({"actions": []}),
        },
        now=NOW,
    )

    assert [c.candidate_id for c in report.priority_candidates] == [
        "candidate-fd04772a23c5"
    ]
    assert {c.candidate_id for c in report.suppressed_candidates} == {
        "candidate-1ed634d8bf6d"
    }


def test_missing_money_path_fails_closed_unknown():
    report = build_capital_path_readiness({}, now=NOW)

    assert report.readiness_state == STATE_UNKNOWN
    assert report.live_money_status == "UNKNOWN"
    assert report.capital_ladder_stage == "UNKNOWN"
    assert report.blocking_gate == "money-path evidence missing"
    assert "money-path sidecar" in report.next_action_ko


def test_blocked_live_money_state_surfaces_blocker():
    report = build_capital_path_readiness(
        {
            "money-path": _money_path(stage="BLOCKED", status=LIVE_STATUS_BLOCKED),
        },
        now=NOW,
    )

    assert report.readiness_state == STATE_LIVE_BLOCKED
    assert report.live_money_status == LIVE_STATUS_BLOCKED
    assert report.blocking_gate == "전진 관측 부족: 13/20"
