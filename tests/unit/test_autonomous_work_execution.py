"""스펙 077 — 자율 작업 실행 루프 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.autonomous_work_execution import (
    AUTONOMY_CLOSED_RELEASED,
    AUTONOMY_CODEX_START,
    AUTONOMY_OPERATOR_APPROVAL,
    CODEX_COMPLETION_GATES,
    STATUS_EXECUTION_READY,
    STATUS_OPERATOR_APPROVAL_REQUIRED,
    STATUS_RELEASED,
    build_autonomous_work_execution,
)

NOW = datetime(2026, 7, 1, 9, 10, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _liveness(overall: str = "OK") -> str:
    return "## 결정 JSON\n\n```json\n" + _json({"overall": overall, "checks": []}) + "\n```\n"


def test_selects_capital_path_priority_candidate():
    report = build_autonomous_work_execution(
        {
            "capital-path-readiness": _json(
                {
                    "readiness_state": "ACCUMULATING_EDGE",
                    "live_money_status": "PREVIEW_ONLY",
                    "priority_candidates": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "domain_key": "live_readiness",
                            "status": "new",
                            "score": 597,
                            "title_ko": "자본 경로 gate alignment",
                            "next_action_ko": "자본 경로 gate alignment를 검증한다.",
                        }
                    ],
                }
            ),
            "evolution-backlog": _json({"candidates": []}),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
        run_id="123",
        commit="abc123",
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == "candidate-fd04772a23c5"
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.autonomy_level == AUTONOMY_CODEX_START
    assert "운영자 추가 질문 없이" in report.selected_work.start_guidance_ko
    assert report.selected_work.completion_gates == CODEX_COMPLETION_GATES
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.priority_score == 3597
    assert report.run_id == "123"
    assert report.commit == "abc123"


def test_pipeline_critical_overrides_growth_candidates():
    report = build_autonomous_work_execution(
        {
            "capital-path-readiness": _json(
                {
                    "priority_candidates": [
                        {
                            "candidate_id": "candidate-safe",
                            "domain_key": "analysis",
                            "status": "new",
                            "score": 999,
                        }
                    ]
                }
            ),
            "pipeline-liveness": _json(
                {
                    "overall": "CRITICAL",
                    "checks": [
                        {
                            "key": "rebalance-paper-forward",
                            "status": "STALE",
                            "critical": True,
                        }
                    ],
                }
            ),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == "ops-pipeline-liveness-critical"
    assert report.selected_work.priority_score > 10000
    assert "rebalance-paper-forward" in report.selected_work.reason_ko


def test_safety_surface_requires_operator_approval():
    report = build_autonomous_work_execution(
        {
            "capital-path-readiness": _json({"priority_candidates": []}),
            "evolution-backlog": _json(
                {
                    "candidates": [
                        {
                            "candidate_id": "candidate-live-order",
                            "domain_key": "execution_quality",
                            "status": "new",
                            "title_ko": "실제 주문 제출 자동화",
                            "next_action_ko": "주문 제출 경로를 자동화한다.",
                            "score": 1000,
                        }
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == "candidate-live-order"
    assert report.selected_work.status == STATUS_OPERATOR_APPROVAL_REQUIRED
    assert report.selected_work.autonomy_level == AUTONOMY_OPERATOR_APPROVAL
    assert "운영자 명시 승인" in report.selected_work.start_guidance_ko
    assert report.selected_work.risk_grade == 4
    assert "orders" in report.selected_work.safety_impact


def test_learning_ledger_suppresses_rejected_candidate_from_other_sources():
    report = build_autonomous_work_execution(
        {
            "capital-path-readiness": _json({"priority_candidates": []}),
            "evolution-ledger": _json(
                {
                    "entries": [
                        {
                            "candidate_id": "candidate-rejected",
                            "status": "rejected",
                            "reason_ko": "검증 실패",
                        }
                    ]
                }
            ),
            "autonomous-promotion": _json(
                {
                    "actions": [
                        {
                            "candidate_id": "candidate-rejected",
                            "domain_key": "analysis",
                            "status": "new",
                            "score": 1000,
                        }
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == "candidate-rejected"
    assert report.selected_work.status == "SUPPRESSED"
    assert "learning ledger" in report.selected_work.reason_ko


def test_released_work_consumes_completed_candidate_and_selects_next_candidate():
    report = build_autonomous_work_execution(
        {
            "capital-path-readiness": _json(
                {
                    "priority_candidates": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "domain_key": "live_readiness",
                            "status": "new",
                            "score": 597,
                            "title_ko": "돈 경로 준비도와 기존 게이트 정렬",
                        },
                        {
                            "candidate_id": "candidate-e481b0309206",
                            "domain_key": "analysis",
                            "status": "new",
                            "score": 531,
                            "title_ko": "레짐 성과 후보 점수화",
                        },
                    ]
                }
            ),
            "released-work": _json(
                {
                    "released_work": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "status": "released",
                            "reason_ko": "스펙 078로 구현·머지·인계 완료",
                        }
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == "candidate-e481b0309206"
    assert report.selected_work.status == STATUS_EXECUTION_READY
    released = {packet.candidate_id: packet for packet in report.suppressed_work}
    assert released["candidate-fd04772a23c5"].status == STATUS_RELEASED
    assert released["candidate-fd04772a23c5"].autonomy_level == AUTONOMY_CLOSED_RELEASED
    assert "released-work" in released["candidate-fd04772a23c5"].reason_ko


def test_missing_all_evidence_emits_liveness_repair_packet():
    report = build_autonomous_work_execution({}, now=NOW)

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == "ops-pipeline-liveness-missing"
    assert all(surface.parse_status == "missing" for surface in report.evidence_surfaces)


def test_deterministic_order_for_same_inputs():
    evidence = {
        "capital-path-readiness": _json(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-b",
                        "domain_key": "analysis",
                        "status": "new",
                        "score": 11,
                    },
                    {
                        "candidate_id": "candidate-a",
                        "domain_key": "analysis",
                        "status": "new",
                        "score": 11,
                    },
                ]
            }
        ),
        "pipeline-liveness": _liveness(),
    }

    first = build_autonomous_work_execution(evidence, now=NOW).to_dict()
    second = build_autonomous_work_execution(evidence, now=NOW).to_dict()

    assert first == second
    assert first["selected_work"]["candidate_id"] == "candidate-a"
