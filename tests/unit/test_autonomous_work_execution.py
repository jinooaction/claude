"""스펙 077 — 자율 작업 실행 루프 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.autonomous_work_execution import (
    AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
    AGENT_OPS_FRONTIER_CANDIDATE_ID,
    AUTONOMY_CLOSED_RELEASED,
    AUTONOMY_CODEX_START,
    AUTONOMY_OPERATOR_APPROVAL,
    BROAD_FRONTIER_EXPANSION_NO_EDGE_CANDIDATE_PREFIX,
    BROAD_FRONTIER_EXPANSION_VALIDATION_FAILURES_CANDIDATE_PREFIX,
    BROAD_NO_EDGE_ASSET_UNIVERSE_ROTATION_CANDIDATE_ID,
    BROAD_NO_EDGE_MULTI_HORIZON_SIGNAL_CANDIDATE_ID,
    BROAD_VALIDATION_FAILURE_COMMAND_REPLAY_CANDIDATE_ID,
    BROAD_VALIDATION_FAILURE_DATA_READINESS_CANDIDATE_ID,
    BROKER_DIAGNOSTIC_LIVENESS_CANDIDATE_ID,
    BROKER_REJECTION_TAXONOMY_CANDIDATE_ID,
    CODEX_COMPLETION_GATES,
    COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
    DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
    DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
    EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID,
    EXECUTION_COST_BASIS_CANDIDATE_ID,
    EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID,
    FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
    FRONTIER_DISCOVERY_CANDIDATE_ID,
    HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
    INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
    MACRO_CANDIDATE_MAP_REGENERATOR_ID,
    MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
    MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
    MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
    OPERATOR_REPORT_LIVENESS_CANDIDATE_ID,
    PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
    PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
    REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
    SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
    STATUS_EXECUTION_READY,
    STATUS_OPERATOR_APPROVAL_REQUIRED,
    STATUS_RELEASED,
    WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
    build_autonomous_work_execution,
)

NOW = datetime(2026, 7, 1, 9, 10, 0, tzinfo=UTC)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _liveness(overall: str = "OK") -> str:
    return "## 결정 JSON\n\n```json\n" + _json({"overall": overall, "checks": []}) + "\n```\n"


def _released_work(*candidate_ids: str) -> str:
    return _json(
        {
            "released_work": [
                {
                    "candidate_id": candidate_id,
                    "status": "released",
                    "reason_ko": f"{candidate_id} 완료",
                }
                for candidate_id in candidate_ids
            ]
        }
    )


def _released_through_broker_diagnostic_liveness(*extra_candidate_ids: str) -> str:
    return _released_work(
        "candidate-fd04772a23c5",
        MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
        MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
        MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
        FRONTIER_DISCOVERY_CANDIDATE_ID,
        MACRO_CANDIDATE_MAP_REGENERATOR_ID,
        INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
        FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
        SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
        COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
        DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
        PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
        REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
        DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
        EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID,
        BROKER_REJECTION_TAXONOMY_CANDIDATE_ID,
        EXECUTION_COST_BASIS_CANDIDATE_ID,
        BROKER_DIAGNOSTIC_LIVENESS_CANDIDATE_ID,
        *extra_candidate_ids,
    )


def _retryable_blocked_candidate_results() -> str:
    next_action = {
        "action_code": "inspect_validation_failure",
        "summary_ko": "종료 코드와 제한된 출력을 바탕으로 실패 원인을 더 좁힌다.",
        "owner": "automation",
        "safe_to_auto_run": True,
    }
    return _json(
        {
            "schema_version": "1.0",
            "results": [
                {
                    "candidate_id": "candidate-1ed634d8bf6d",
                    "package_id": "pkg-c9a284fa4235",
                    "package_kind": "strategy_backtest",
                    "status": "blocked",
                    "source_ref": "candidate-result-executor:pkg-c9a284fa4235",
                    "block_reason_ko": "검증 명령이 비정상 종료했다.",
                    "diagnostics": [
                        {
                            "code": "execution_failed",
                            "severity": "warning",
                            "retryable": True,
                            "summary_ko": "검증 명령이 비정상 종료했다.",
                            "evidence_source": "package",
                            "next_actions": [next_action],
                            "details": {"exit_code": 1},
                        }
                    ],
                    "next_actions": [next_action],
                    "retryable": True,
                },
                {
                    "candidate_id": "candidate-cc96b35062da",
                    "package_id": "pkg-8aae8cb99874",
                    "package_kind": "portfolio_backtest",
                    "status": "blocked",
                    "source_ref": "candidate-result-executor:pkg-8aae8cb99874",
                    "block_reason_ko": "검증 명령이 비정상 종료했다.",
                    "diagnostics": [
                        {
                            "code": "execution_failed",
                            "severity": "warning",
                            "retryable": True,
                            "summary_ko": "검증 명령이 비정상 종료했다.",
                            "evidence_source": "package",
                            "next_actions": [next_action],
                            "details": {"exit_code": 2},
                        }
                    ],
                    "next_actions": [next_action],
                    "retryable": True,
                },
            ],
        }
    )


def _all_known_released_no_edge_evidence(*extra_candidate_ids: str) -> dict[str, str]:
    return {
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
                    }
                ],
            }
        ),
        "released-work": _released_through_broker_diagnostic_liveness(
            AGENT_OPS_FRONTIER_CANDIDATE_ID,
            HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
            PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
            WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
            AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
            OPERATOR_REPORT_LIVENESS_CANDIDATE_ID,
            EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID,
            *extra_candidate_ids,
        ),
        "money-path": _json(
            {
                "overall_status": "PREVIEW_ONLY",
                "live_money_state": {"status": "PREVIEW_ONLY"},
                "stage": "NO_EDGE_YET",
            }
        ),
        "edge-autoarm": _json(
            {
                "action": "WAIT_EDGE",
                "reason": "forward 판정='NO_EDGE'",
            }
        ),
        "pipeline-liveness": _liveness(),
    }


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
    assert report.selected_work.candidate_id == MACRO_GROWTH_DISCOVERY_CANDIDATE_ID
    suppressed = {packet.candidate_id: packet for packet in report.suppressed_work}
    assert suppressed["candidate-rejected"].status == "SUPPRESSED"
    assert "learning ledger" in suppressed["candidate-rejected"].reason_ko


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


def test_released_source_status_is_not_execution_ready():
    report = build_autonomous_work_execution(
        {
            "capital-path-readiness": _json({"priority_candidates": []}),
            "evolution-backlog": _json(
                {
                    "candidates": [
                        {
                            "candidate_id": "candidate-88a7e7f07361",
                            "domain_key": "agent_ops",
                            "status": "released",
                            "title_ko": "자율 루프 sidecar와 handoff 생존성",
                            "next_action_ko": "이미 충족",
                            "composite_score": 568,
                        },
                        {
                            "candidate_id": "candidate-next",
                            "domain_key": "analysis",
                            "status": "new",
                            "title_ko": "다음 후보",
                            "next_action_ko": "다음 후보를 진행한다.",
                            "composite_score": 100,
                        },
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == "candidate-next"
    released = {packet.candidate_id: packet for packet in report.suppressed_work}
    assert released["candidate-88a7e7f07361"].status == STATUS_RELEASED
    assert released["candidate-88a7e7f07361"].autonomy_level == AUTONOMY_CLOSED_RELEASED
    assert "다시 착수하지 않는다" in released["candidate-88a7e7f07361"].start_guidance_ko


def test_closed_regular_queue_emits_macro_growth_candidate():
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
                        }
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
    assert report.selected_work.candidate_id == MACRO_GROWTH_DISCOVERY_CANDIDATE_ID
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.autonomy_level == AUTONOMY_CODEX_START
    assert "정적 후보" in report.selected_work.reason_ko
    assert _source_refs(report.selected_work) >= {
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
    }


def test_released_macro_bootstrap_advances_to_next_macro_candidate():
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
                        }
                    ]
                }
            ),
            "released-work": _json(
                {
                    "released_work": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "status": "released",
                            "reason_ko": "스펙 078 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 088 완료",
                        },
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID
    )
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert "정적 템플릿 밖" in report.selected_work.next_action_ko


def test_released_source_diversification_output_advances_to_objective_calibration():
    source_output_candidate_id = "candidate-source-diversification-sidecar-bottleneck"
    report = build_autonomous_work_execution(
        {
            "capital-path-readiness": _json({"priority_candidates": []}),
            "evolution-backlog": _json(
                {
                    "candidates": [
                        {
                            "candidate_id": source_output_candidate_id,
                            "domain_key": "agent_ops",
                            "status": "new",
                            "score": 600,
                            "title_ko": "증거 기반 후보 소스 다변화",
                            "next_action_ko": (
                                "학습 장부, released-work, pipeline-liveness, "
                                "capital-path-readiness sidecar를 후보 생성 입력으로 승격한다."
                            ),
                            "safety_impact": [],
                            "risk_grade": 2,
                        }
                    ]
                }
            ),
            "released-work": _json(
                {
                    "released_work": [
                        {
                            "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 088 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 089 완료",
                        },
                        {
                            "candidate_id": source_output_candidate_id,
                            "status": "released",
                            "reason_ko": "스펙 090 완료",
                        },
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID
    )
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert "목적 함수" in report.selected_work.title_ko
    released = {packet.candidate_id: packet for packet in report.suppressed_work}
    assert released[source_output_candidate_id].status == STATUS_RELEASED
    assert "다시 착수하지 않는다" in released[source_output_candidate_id].start_guidance_ko


def test_retryable_blocked_validation_packages_emit_source_diversification_candidate():
    source_output_candidate_id = "candidate-source-diversification-sidecar-bottleneck"
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
                            "title_ko": "돈 경로 준비도와 기존 게이트 정렬",
                        }
                    ],
                }
            ),
            "evolution-backlog": _json(
                {
                    "candidates": [
                        {
                            "candidate_id": source_output_candidate_id,
                            "domain_key": "agent_ops",
                            "status": "new",
                            "score": 600,
                            "title_ko": "증거 기반 후보 소스 다변화",
                            "next_action_ko": "후보 생성 입력을 확장한다.",
                            "safety_impact": [],
                            "risk_grade": 2,
                        }
                    ]
                }
            ),
            "candidate-result-executor": _retryable_blocked_candidate_results(),
            "money-path": _json(
                {
                    "overall_status": "PREVIEW_ONLY",
                    "live_money_state": {"status": "PREVIEW_ONLY"},
                    "stage": "NO_EDGE_YET",
                }
            ),
            "edge-autoarm": _json(
                {
                    "action": "WAIT_EDGE",
                    "current_rung": 0,
                    "reason": "단 0 + forward 판정='NO_EDGE' — EDGE_CONFIRMED 아님.",
                    "target_rung": 0,
                }
            ),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                source_output_candidate_id,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID
    )
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.autonomy_level == AUTONOMY_CODEX_START
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.safety_impact == ()
    assert "PREVIEW_ONLY" in report.selected_work.reason_ko
    assert "NO_EDGE_YET" in report.selected_work.reason_ko
    assert "WAIT_EDGE" in report.selected_work.reason_ko
    assert "NO_EDGE" in report.selected_work.reason_ko
    assert "실제 주문" in " ".join(report.selected_work.safety_boundary)

    selected = report.selected_work.to_dict()
    assert selected["blocked_package_refs"] == [
        {
            "candidate_id": "candidate-1ed634d8bf6d",
            "package_id": "pkg-c9a284fa4235",
            "package_kind": "strategy_backtest",
            "status": "blocked",
            "retryable": True,
            "diagnostic_codes": ["execution_failed"],
            "next_action_codes": ["inspect_validation_failure"],
            "safe_to_auto_run": True,
            "source_ref": "candidate-result-executor:pkg-c9a284fa4235",
        },
        {
            "candidate_id": "candidate-cc96b35062da",
            "package_id": "pkg-8aae8cb99874",
            "package_kind": "portfolio_backtest",
            "status": "blocked",
            "retryable": True,
            "diagnostic_codes": ["execution_failed"],
            "next_action_codes": ["inspect_validation_failure"],
            "safe_to_auto_run": True,
            "source_ref": "candidate-result-executor:pkg-8aae8cb99874",
        },
    ]
    assert selected["validation_failure_groups"] == [
        {
            "reason_code": "execution_failed",
            "summary_ko": (
                "execution_failed 진단으로 막힌 검증 패키지 2개를 "
                "같은 원인으로 묶었다."
            ),
            "package_count": 2,
            "retryable_count": 2,
            "safe_action_codes": ["inspect_validation_failure"],
            "package_refs": ["pkg-8aae8cb99874", "pkg-c9a284fa4235"],
        }
    ]
    assert set(selected["required_inputs"]) >= {
        "automation/candidate-implementation-results:candidate_results.json",
        "automation/candidate-implementation-factory-last-run:candidate_factory.json",
        "automation/candidate-implementation-factory-last-run:candidate_packages.json",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/edge-autoarm-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
    }
    assert selected["source_refs"] == selected["required_inputs"]

    markdown = report.as_markdown()
    assert "## 막힌 검증 패키지" in markdown
    assert "pkg-c9a284fa4235" in markdown
    assert "pkg-8aae8cb99874" in markdown
    assert "inspect_validation_failure" in markdown


def test_objective_calibration_tracks_selected_work_deterministically():
    source_output_candidate_id = "candidate-source-diversification-sidecar-bottleneck"
    evidence = {
        "capital-path-readiness": _json({"priority_candidates": []}),
        "evolution-backlog": _json(
            {
                "candidates": [
                    {
                        "candidate_id": source_output_candidate_id,
                        "domain_key": "agent_ops",
                        "status": "new",
                        "score": 600,
                        "title_ko": "증거 기반 후보 소스 다변화",
                        "next_action_ko": "후보 생성 입력을 확장한다.",
                        "safety_impact": [],
                        "risk_grade": 2,
                    }
                ]
            }
        ),
        "released-work": _json(
            {
                "released_work": [
                    {
                        "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 088 완료",
                    },
                    {
                        "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 089 완료",
                    },
                    {
                        "candidate_id": source_output_candidate_id,
                        "status": "released",
                        "reason_ko": "스펙 090 완료",
                    },
                ]
            }
        ),
        "pipeline-liveness": _liveness(),
    }

    first = build_autonomous_work_execution(evidence, now=NOW).to_dict()
    second = build_autonomous_work_execution(evidence, now=NOW).to_dict()

    assert first["objective_calibration"] == second["objective_calibration"]
    calibration = first["objective_calibration"]
    assert (
        calibration["selected_candidate_id"]
        == MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID
    )
    assert calibration["exploration_budget"]["max_parallel_candidates"] == 1
    assert calibration["exploration_budget"]["max_ranked_candidates"] == 10
    assert calibration["learning_metrics"]["ranked_count"] == 1
    selected_score = calibration["candidate_scores"][0]
    assert selected_score["candidate_id"] == calibration["selected_candidate_id"]
    assert set(selected_score["component_scores"]) >= {
        "growth_leverage",
        "evidence_readiness",
        "validation_cost_fit",
        "safety_margin",
        "learning_value",
    }
    assert selected_score["component_scores"]["safety_margin"] == 100
    assert selected_score["total_score"] > 0

    markdown = build_autonomous_work_execution(evidence, now=NOW).as_markdown()
    assert "## 목적 함수 보정" in markdown
    assert MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID in markdown
    assert "max_parallel_candidates" in markdown


def test_objective_calibration_penalizes_safety_impact_candidates():
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

    payload = report.to_dict()
    assert payload["selected_work"]["status"] == STATUS_OPERATOR_APPROVAL_REQUIRED
    calibration = payload["objective_calibration"]
    score = calibration["candidate_scores"][0]
    assert score["candidate_id"] == "candidate-live-order"
    assert score["status"] == STATUS_OPERATOR_APPROVAL_REQUIRED
    assert score["component_scores"]["safety_margin"] < 50
    assert any("operator approval" in item for item in calibration["stop_conditions"])


def test_exhausted_macro_candidates_emit_frontier_discovery_candidate():
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
                        }
                    ]
                }
            ),
            "released-work": _json(
                {
                    "released_work": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "status": "released",
                            "reason_ko": "스펙 078 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 088 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 089 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 091 완료",
                        },
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == FRONTIER_DISCOVERY_CANDIDATE_ID
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.risk_grade == 2
    assert "닫힌 후보" in report.selected_work.reason_ko
    assert "frontier" in report.selected_work.next_action_ko
    assert set(report.selected_work.required_inputs) >= {
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
    }
    assert report.ranked_work[0].candidate_id == FRONTIER_DISCOVERY_CANDIDATE_ID


def test_frontier_discovery_does_not_mask_regular_ready_candidate():
    report = build_autonomous_work_execution(
        {
            "capital-path-readiness": _json(
                {
                    "priority_candidates": [
                        {
                            "candidate_id": "candidate-next",
                            "domain_key": "analysis",
                            "status": "new",
                            "score": 100,
                            "title_ko": "다음 일반 후보",
                        }
                    ]
                }
            ),
            "released-work": _json(
                {
                    "released_work": [
                        {
                            "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 088 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 089 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 091 완료",
                        },
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == "candidate-next"
    assert FRONTIER_DISCOVERY_CANDIDATE_ID not in {
        packet.candidate_id for packet in report.ranked_work
    }


def test_released_frontier_emits_macro_candidate_map_regenerator():
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
                        }
                    ]
                }
            ),
            "released-work": _json(
                {
                    "released_work": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "status": "released",
                            "reason_ko": "스펙 078 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 088 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 089 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 091 완료",
                        },
                        {
                            "candidate_id": FRONTIER_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 092 완료",
                        },
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == MACRO_CANDIDATE_MAP_REGENERATOR_ID
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert "거시 후보 지도" in report.selected_work.title_ko


def test_released_regenerator_emits_investment_edge_frontier_candidate():
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
                        }
                    ]
                }
            ),
            "released-work": _json(
                {
                    "released_work": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "status": "released",
                            "reason_ko": "스펙 078 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 088 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 089 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 091 완료",
                        },
                        {
                            "candidate_id": FRONTIER_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 092 완료",
                        },
                        {
                            "candidate_id": MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                            "status": "released",
                            "reason_ko": "스펙 093 완료",
                        },
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.domain_key == "strategy_design"
    assert "투자 엣지" in report.selected_work.title_ko


def test_investment_edge_frontier_map_is_deterministic_and_rendered():
    evidence = {
        "capital-path-readiness": _json(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            }
        ),
        "rebalance-paper-forward": _json({"overall": "OK", "tracks": []}),
        "edge-autoarm": _json({"overall": "OK"}),
        "money-path": _json(
            {
                "overall_status": "OK",
                "live_money_state": {"status": "PREVIEW_ONLY"},
            }
        ),
        "released-work": _json(
            {
                "released_work": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "status": "released",
                        "reason_ko": "스펙 078 완료",
                    },
                    {
                        "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 088 완료",
                    },
                    {
                        "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 089 완료",
                    },
                    {
                        "candidate_id": MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 091 완료",
                    },
                    {
                        "candidate_id": FRONTIER_DISCOVERY_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 092 완료",
                    },
                    {
                        "candidate_id": MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                        "status": "released",
                        "reason_ko": "스펙 093 완료",
                    },
                ]
            }
        ),
        "pipeline-liveness": _liveness(),
    }

    first = build_autonomous_work_execution(evidence, now=NOW).to_dict()
    second = build_autonomous_work_execution(evidence, now=NOW).to_dict()

    assert first["investment_edge_frontier_map"] == second[
        "investment_edge_frontier_map"
    ]
    assert (
        first["investment_edge_frontier_map"][0]["recommended_candidate_id"]
        == FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID
    )
    assert first["investment_edge_frontier_map"][0]["coverage_status"] == "open"

    markdown = build_autonomous_work_execution(evidence, now=NOW).as_markdown()
    assert "## 투자 엣지 frontier 지도" in markdown
    assert FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID in markdown


def test_released_investment_edge_frontier_emits_no_live_experiment_candidate():
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
                        }
                    ]
                }
            ),
            "rebalance-paper-forward": _json({"overall": "OK", "tracks": []}),
            "edge-autoarm": _json({"overall": "OK"}),
            "money-path": _json(
                {
                    "overall_status": "OK",
                    "live_money_state": {"status": "PREVIEW_ONLY"},
                }
            ),
            "released-work": _json(
                {
                    "released_work": [
                        {
                            "candidate_id": "candidate-fd04772a23c5",
                            "status": "released",
                            "reason_ko": "스펙 078 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 088 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 089 완료",
                        },
                        {
                            "candidate_id": MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 091 완료",
                        },
                        {
                            "candidate_id": FRONTIER_DISCOVERY_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 092 완료",
                        },
                        {
                            "candidate_id": MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                            "status": "released",
                            "reason_ko": "스펙 093 완료",
                        },
                        {
                            "candidate_id": INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                            "status": "released",
                            "reason_ko": "스펙 094 완료",
                        },
                    ]
                }
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID
    )
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.domain_key == "strategy_design"
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.safety_impact == ()
    assert "no-live" in report.selected_work.next_action_ko
    assert set(report.selected_work.required_inputs) >= {
        "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/autonomous-evolution-last-run:learning_ledger.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
    }


def test_completed_investment_edge_experiments_emit_data_evidence_frontier_candidate():
    released_work = _released_work(
        "candidate-fd04772a23c5",
        MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
        MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
        MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
        FRONTIER_DISCOVERY_CANDIDATE_ID,
        MACRO_CANDIDATE_MAP_REGENERATOR_ID,
        INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
        FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
        SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
        COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
    )
    evidence = {
        "capital-path-readiness": _json(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            }
        ),
        "public-data": _json({"overall_ok": True, "published": 11}),
        "regime-stratify": _json({"overall": "OK", "total_return_days": 751}),
        "released-work": released_work,
        "pipeline-liveness": _liveness(),
    }

    first = build_autonomous_work_execution(evidence, now=NOW).to_dict()
    second = build_autonomous_work_execution(evidence, now=NOW).to_dict()

    assert first["data_evidence_frontier_map"] == second[
        "data_evidence_frontier_map"
    ]
    assert (
        first["data_evidence_frontier_map"][0]["recommended_candidate_id"]
        == PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID
    )
    assert first["data_evidence_frontier_map"][0]["coverage_status"] == "open"
    assert first["selected_work"]["candidate_id"] == DATA_EVIDENCE_FRONTIER_CANDIDATE_ID
    assert first["selected_work"]["domain_key"] == "data_quality"

    markdown = build_autonomous_work_execution(evidence, now=NOW).as_markdown()
    assert "## 데이터 증거 frontier 지도" in markdown
    assert PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID in markdown


def test_released_data_evidence_frontier_emits_public_data_input_quality_candidate():
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
                        }
                    ]
                }
            ),
            "public-data": _json({"overall_ok": True, "published": 11}),
            "regime-stratify": _json({"overall": "OK", "total_return_days": 751}),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                FRONTIER_DISCOVERY_CANDIDATE_ID,
                MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
                SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
                COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
                DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.domain_key == "data_quality"
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.safety_impact == ()
    assert "공개 데이터" in report.selected_work.next_action_ko
    assert set(report.selected_work.required_inputs) >= {
        "automation/public-data:LAST_RUN.md",
        "automation/public-data:summary.json",
        "automation/public-data:regime.json",
        "automation/public-data:regime_timeline.csv",
        "automation/regime-stratify-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
    }


def test_released_public_data_input_quality_advances_to_regime_timeline_candidate():
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
                        }
                    ]
                }
            ),
            "public-data": _json({"overall_ok": True, "published": 11}),
            "regime-stratify": _json({"overall": "OK", "total_return_days": 751}),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                FRONTIER_DISCOVERY_CANDIDATE_ID,
                MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
                SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
                COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
                DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
                PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == REGIME_TIMELINE_COVERAGE_CANDIDATE_ID
    assert report.selected_work.domain_key == "data_quality"
    assert report.selected_work.risk_grade == 2
    data_map = {entry.frontier_key: entry for entry in report.data_evidence_frontier_map}
    assert data_map["public_data_input_quality"].coverage_status == "released"
    assert data_map["regime_timeline_coverage"].coverage_status == "open"


def test_released_regime_timeline_coverage_advances_to_data_evidence_liveness():
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
                        }
                    ]
                }
            ),
            "public-data": _json({"overall_ok": True, "published": 11}),
            "regime-stratify": _json({"overall": "OK", "total_return_days": 751}),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                FRONTIER_DISCOVERY_CANDIDATE_ID,
                MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
                SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
                COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
                DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
                PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
                REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == DATA_EVIDENCE_LIVENESS_CANDIDATE_ID
    assert report.selected_work.domain_key == "data_quality"
    assert report.selected_work.risk_grade == 2
    data_map = {entry.frontier_key: entry for entry in report.data_evidence_frontier_map}
    assert data_map["regime_timeline_coverage"].coverage_status == "released"
    assert data_map["data_evidence_liveness"].coverage_status == "open"


def test_released_data_evidence_liveness_advances_to_execution_quality_frontier():
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
                        }
                    ]
                }
            ),
            "public-data": _json({"overall_ok": True, "published": 11}),
            "regime-stratify": _json({"overall": "OK", "total_return_days": 751}),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                FRONTIER_DISCOVERY_CANDIDATE_ID,
                MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
                SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
                COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
                DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
                PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
                REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
                DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID
    assert report.selected_work.domain_key == "execution_quality"
    assert report.selected_work.risk_grade == 2
    data_map = {entry.frontier_key: entry for entry in report.data_evidence_frontier_map}
    assert data_map["data_evidence_liveness"].coverage_status == "released"
    execution_map = {
        entry.frontier_key: entry for entry in report.execution_quality_frontier_map
    }
    assert execution_map["broker_rejection_taxonomy"].coverage_status == "open"
    assert (
        execution_map["broker_rejection_taxonomy"].recommended_candidate_id
        == BROKER_REJECTION_TAXONOMY_CANDIDATE_ID
    )


def test_execution_quality_frontier_map_is_deterministic_and_rendered():
    evidence = {
        "capital-path-readiness": _json(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            }
        ),
        "execution-quality": _json(
            {
                "overall_status": "OBSERVE",
                "broker_rejections": {"rejected_orders": 2},
            }
        ),
        "kis-smoke": "smoke_state | success",
        "rebalance-micro-gtaa": _json(
            {
                "verdict": "INSUFFICIENT_DATA",
                "latest_signal": "INTENT_LOSS",
            }
        ),
        "money-path": _json(
            {
                "overall_status": "OK",
                "live_money_state": {"status": "PREVIEW_ONLY"},
            }
        ),
        "released-work": _released_work(
            "candidate-fd04772a23c5",
            MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
            MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
            MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
            FRONTIER_DISCOVERY_CANDIDATE_ID,
            MACRO_CANDIDATE_MAP_REGENERATOR_ID,
            INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
            FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
            SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
            COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
            DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
            PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
            REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
            DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
        ),
        "pipeline-liveness": _liveness(),
    }

    first = build_autonomous_work_execution(evidence, now=NOW).to_dict()
    second = build_autonomous_work_execution(evidence, now=NOW).to_dict()

    assert first["execution_quality_frontier_map"] == second[
        "execution_quality_frontier_map"
    ]
    assert (
        first["execution_quality_frontier_map"][0]["recommended_candidate_id"]
        == BROKER_REJECTION_TAXONOMY_CANDIDATE_ID
    )
    assert first["execution_quality_frontier_map"][0]["coverage_status"] == "open"
    assert (
        first["selected_work"]["candidate_id"]
        == EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID
    )

    markdown = build_autonomous_work_execution(evidence, now=NOW).as_markdown()
    assert "## 체결 품질 frontier 지도" in markdown
    assert BROKER_REJECTION_TAXONOMY_CANDIDATE_ID in markdown


def test_released_execution_quality_frontier_emits_broker_rejection_candidate():
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
                        }
                    ]
                }
            ),
            "execution-quality": _json({"overall_status": "OBSERVE"}),
            "kis-smoke": "smoke_state | success",
            "rebalance-micro-gtaa": _json({"latest_signal": "INTENT_LOSS"}),
            "money-path": _json({"live_money_state": {"status": "PREVIEW_ONLY"}}),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                FRONTIER_DISCOVERY_CANDIDATE_ID,
                MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
                SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
                COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
                DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
                PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
                REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
                DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
                EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == BROKER_REJECTION_TAXONOMY_CANDIDATE_ID
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.domain_key == "execution_quality"
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.safety_impact == ()
    assert "브로커 거부" in report.selected_work.next_action_ko
    assert set(report.selected_work.required_inputs) >= {
        "automation/execution-quality-last-run:LAST_RUN.md",
        "automation/kis-smoke-last-run:LAST_RUN.md",
        "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
    }


def test_released_broker_rejection_advances_to_execution_cost_basis():
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
                        }
                    ]
                }
            ),
            "execution-quality": _json({"overall_status": "OBSERVE"}),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                FRONTIER_DISCOVERY_CANDIDATE_ID,
                MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
                SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
                COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
                DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
                PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
                REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
                DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
                EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID,
                BROKER_REJECTION_TAXONOMY_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == EXECUTION_COST_BASIS_CANDIDATE_ID
    execution_map = {
        entry.frontier_key: entry for entry in report.execution_quality_frontier_map
    }
    assert execution_map["broker_rejection_taxonomy"].coverage_status == "released"
    assert execution_map["execution_cost_basis"].coverage_status == "open"


def test_released_execution_cost_basis_advances_to_broker_diagnostic_liveness():
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
                        }
                    ]
                }
            ),
            "execution-quality": _json({"overall_status": "OBSERVE"}),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                FRONTIER_DISCOVERY_CANDIDATE_ID,
                MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
                SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
                COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
                DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
                PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
                REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
                DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
                EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID,
                BROKER_REJECTION_TAXONOMY_CANDIDATE_ID,
                EXECUTION_COST_BASIS_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == BROKER_DIAGNOSTIC_LIVENESS_CANDIDATE_ID
    execution_map = {
        entry.frontier_key: entry for entry in report.execution_quality_frontier_map
    }
    assert execution_map["execution_cost_basis"].coverage_status == "released"
    assert execution_map["broker_diagnostic_liveness"].coverage_status == "open"


def test_released_broker_diagnostic_liveness_advances_to_agent_ops_frontier():
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
                        }
                    ]
                }
            ),
            "execution-quality": _json({"overall_status": "OBSERVE"}),
            "released-work": _released_work(
                "candidate-fd04772a23c5",
                MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                FRONTIER_DISCOVERY_CANDIDATE_ID,
                MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
                FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
                SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
                COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
                DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
                PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
                REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
                DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
                EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID,
                BROKER_REJECTION_TAXONOMY_CANDIDATE_ID,
                EXECUTION_COST_BASIS_CANDIDATE_ID,
                BROKER_DIAGNOSTIC_LIVENESS_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id == AGENT_OPS_FRONTIER_CANDIDATE_ID
    execution_map = {
        entry.frontier_key: entry for entry in report.execution_quality_frontier_map
    }
    assert execution_map["broker_diagnostic_liveness"].coverage_status == "released"


def test_agent_ops_frontier_map_is_deterministic_and_rendered():
    evidence = {
        "capital-path-readiness": _json(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            }
        ),
        "released-work": _released_through_broker_diagnostic_liveness(),
        "pipeline-liveness": _liveness(),
    }

    first = build_autonomous_work_execution(evidence, now=NOW).to_dict()
    second = build_autonomous_work_execution(evidence, now=NOW).to_dict()

    assert first["selected_work"]["candidate_id"] == AGENT_OPS_FRONTIER_CANDIDATE_ID
    assert first["agent_ops_frontier_map"] == second["agent_ops_frontier_map"]
    assert (
        first["agent_ops_frontier_map"][0]["recommended_candidate_id"]
        == HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID
    )
    assert first["agent_ops_frontier_map"][0]["coverage_status"] == "open"

    markdown = build_autonomous_work_execution(evidence, now=NOW).as_markdown()
    assert "## 운영 체계 frontier 지도" in markdown
    assert HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID in markdown


def test_released_agent_ops_frontier_emits_handoff_truth_candidate():
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
                        }
                    ]
                }
            ),
            "released-work": _released_through_broker_diagnostic_liveness(
                AGENT_OPS_FRONTIER_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID
    assert report.selected_work.domain_key == "agent_ops"
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.safety_impact == ()
    assert set(report.selected_work.required_inputs) >= {
        "automation/autonomous-work-execution-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "HANDOFF.md",
        "scripts/check_handoff_facts.py",
        "scripts/agent_harness_probe.py",
        ".github/workflows/pr-quality-gate.yml",
    }


def test_released_handoff_truth_advances_to_pr_merge_evidence_candidate():
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
                        }
                    ]
                }
            ),
            "released-work": _released_through_broker_diagnostic_liveness(
                AGENT_OPS_FRONTIER_CANDIDATE_ID,
                HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID
    )
    agent_ops_map = {entry.frontier_key: entry for entry in report.agent_ops_frontier_map}
    assert agent_ops_map["handoff_truth_liveness"].coverage_status == "released"
    assert agent_ops_map["pr_merge_evidence_liveness"].coverage_status == "open"


def test_released_pr_merge_evidence_advances_to_worktree_concurrency_candidate():
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
                        }
                    ]
                }
            ),
            "released-work": _released_through_broker_diagnostic_liveness(
                AGENT_OPS_FRONTIER_CANDIDATE_ID,
                HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
                PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID
    )
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.safety_impact == ()
    agent_ops_map = {entry.frontier_key: entry for entry in report.agent_ops_frontier_map}
    assert agent_ops_map["handoff_truth_liveness"].coverage_status == "released"
    assert agent_ops_map["pr_merge_evidence_liveness"].coverage_status == "released"
    assert agent_ops_map["worktree_concurrency_liveness"].coverage_status == "open"


def test_released_worktree_concurrency_advances_to_agent_harness_candidate():
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
                        }
                    ]
                }
            ),
            "released-work": _released_through_broker_diagnostic_liveness(
                AGENT_OPS_FRONTIER_CANDIDATE_ID,
                HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
                PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
                WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID
    )
    assert report.selected_work.domain_key == "agent_ops"
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.safety_impact == ()
    assert set(report.selected_work.required_inputs) >= {
        "scripts/local_concurrency_guard.py",
        ".codex/hooks.json",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".codex/harness/evaluation_tasks.toml",
        ".codex/harness/quality_tasks.toml",
        ".codex/harness/redteam_tasks.toml",
        "scripts/agent_harness_probe.py",
    }
    agent_ops_map = {entry.frontier_key: entry for entry in report.agent_ops_frontier_map}
    assert agent_ops_map["worktree_concurrency_liveness"].coverage_status == "released"
    assert agent_ops_map["agent_harness_regression_liveness"].coverage_status == "open"


def test_released_agent_harness_advances_to_operator_report_candidate():
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
                        }
                    ]
                }
            ),
            "released-work": _released_through_broker_diagnostic_liveness(
                AGENT_OPS_FRONTIER_CANDIDATE_ID,
                HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
                PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
                WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
                AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.selected_work is not None
    assert report.selected_work.candidate_id == OPERATOR_REPORT_LIVENESS_CANDIDATE_ID
    assert report.selected_work.domain_key == "agent_ops"
    assert report.selected_work.risk_grade == 2
    assert report.selected_work.safety_impact == ()
    assert set(report.selected_work.required_inputs) >= {
        "AGENTS.md",
        ".codex/quality-gate.md",
        ".github/pull_request_template.md",
        ".codex/harness/quality_tasks.toml",
    }
    agent_ops_map = {entry.frontier_key: entry for entry in report.agent_ops_frontier_map}
    assert agent_ops_map["agent_harness_regression_liveness"].coverage_status == "released"
    assert agent_ops_map["operator_report_liveness"].coverage_status == "open"


def test_released_operator_report_candidate_is_not_reselected():
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
                        }
                    ]
                }
            ),
            "released-work": _released_through_broker_diagnostic_liveness(
                AGENT_OPS_FRONTIER_CANDIDATE_ID,
                HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
                PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
                WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
                AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
                OPERATOR_REPORT_LIVENESS_CANDIDATE_ID,
            ),
            "pipeline-liveness": _liveness(),
        },
        now=NOW,
    )

    agent_ops_map = {entry.frontier_key: entry for entry in report.agent_ops_frontier_map}
    assert agent_ops_map["operator_report_liveness"].coverage_status == "released"
    assert all(
        packet.candidate_id != OPERATOR_REPORT_LIVENESS_CANDIDATE_ID
        for packet in report.ranked_work
    )
    if report.selected_work is not None:
        assert report.selected_work.candidate_id != OPERATOR_REPORT_LIVENESS_CANDIDATE_ID


def test_all_released_candidates_emit_broad_frontier_expansion_before_waiting():
    base_evidence = {
        "capital-path-readiness": _json(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            }
        ),
        "candidate-result-executor": _retryable_blocked_candidate_results(),
        "evolution-ledger": _json(
            {
                "entries": [
                    {
                        "candidate_id": "candidate-1ed634d8bf6d",
                        "status": "rejected",
                        "reason_ko": "검증 실패로 승격하지 않는다.",
                    },
                    {
                        "candidate_id": "candidate-cc96b35062da",
                        "status": "rejected",
                        "reason_ko": "검증 실패로 승격하지 않는다.",
                    },
                ]
            }
        ),
        "released-work": _released_through_broker_diagnostic_liveness(
            AGENT_OPS_FRONTIER_CANDIDATE_ID,
            HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
            PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
            WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
            AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
            OPERATOR_REPORT_LIVENESS_CANDIDATE_ID,
            EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID,
        ),
        "money-path": _json(
            {
                "overall_status": "PREVIEW_ONLY",
                "live_money_state": {"status": "PREVIEW_ONLY"},
                "stage": "NO_EDGE_YET",
            }
        ),
        "edge-autoarm": _json(
            {
                "action": "WAIT_EDGE",
                "reason": "forward 판정='NO_EDGE'",
            }
        ),
        "pipeline-liveness": _liveness(),
    }
    report = build_autonomous_work_execution(base_evidence, now=NOW)

    assert report.selected_work is not None
    assert report.selected_work.candidate_id.startswith(
        f"{BROAD_FRONTIER_EXPANSION_VALIDATION_FAILURES_CANDIDATE_PREFIX}-"
    )
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.autonomy_level == AUTONOMY_CODEX_START
    assert report.overall_status == STATUS_EXECUTION_READY
    assert report.ranked_work == (report.selected_work,)
    assert "정적 템플릿 밖" in report.selected_work.reason_ko
    assert "no-live" in report.selected_work.next_action_ko
    assert "실제 주문" in " ".join(report.selected_work.safety_boundary)
    assert len(report.selected_work.blocked_package_refs) == 2
    assert (
        EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID
        not in {packet.candidate_id for packet in report.ranked_work}
    )

    repeated_evidence = {
        **base_evidence,
        "released-work": _released_through_broker_diagnostic_liveness(
            AGENT_OPS_FRONTIER_CANDIDATE_ID,
            HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
            PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
            WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
            AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
            OPERATOR_REPORT_LIVENESS_CANDIDATE_ID,
            EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID,
            report.selected_work.candidate_id,
        ),
    }
    repeated_report = build_autonomous_work_execution(repeated_evidence, now=NOW)

    assert repeated_report.selected_work is not None
    assert (
        repeated_report.selected_work.candidate_id
        == BROAD_VALIDATION_FAILURE_COMMAND_REPLAY_CANDIDATE_ID
    )
    assert repeated_report.selected_work.status == STATUS_EXECUTION_READY
    assert repeated_report.selected_work.autonomy_level == AUTONOMY_CODEX_START
    assert "명령 재현" in repeated_report.selected_work.title_ko
    assert "실제 주문" in " ".join(repeated_report.selected_work.safety_boundary)
    assert len(repeated_report.selected_work.blocked_package_refs) == 2

    payload = repeated_report.to_dict()
    validation_map = payload["broad_validation_failure_frontier_map"]
    assert (
        validation_map[0]["recommended_candidate_id"]
        == BROAD_VALIDATION_FAILURE_COMMAND_REPLAY_CANDIDATE_ID
    )
    assert validation_map[0]["coverage_status"] == "open"
    assert validation_map[0]["package_count"] == 2
    assert "검증 실패 frontier 지도" in repeated_report.as_markdown()


def test_released_validation_failure_entry_advances_to_next_entry():
    base_evidence = {
        "capital-path-readiness": _json(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            }
        ),
        "candidate-result-executor": _retryable_blocked_candidate_results(),
        "evolution-ledger": _json(
            {
                "entries": [
                    {
                        "candidate_id": "candidate-1ed634d8bf6d",
                        "status": "rejected",
                        "reason_ko": "검증 실패로 승격하지 않는다.",
                    },
                    {
                        "candidate_id": "candidate-cc96b35062da",
                        "status": "rejected",
                        "reason_ko": "검증 실패로 승격하지 않는다.",
                    },
                ]
            }
        ),
        "released-work": _released_through_broker_diagnostic_liveness(
            AGENT_OPS_FRONTIER_CANDIDATE_ID,
            HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
            PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
            WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
            AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
            OPERATOR_REPORT_LIVENESS_CANDIDATE_ID,
            EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID,
        ),
        "money-path": _json(
            {
                "overall_status": "PREVIEW_ONLY",
                "live_money_state": {"status": "PREVIEW_ONLY"},
                "stage": "NO_EDGE_YET",
            }
        ),
        "edge-autoarm": _json(
            {
                "action": "WAIT_EDGE",
                "reason": "forward 판정='NO_EDGE'",
            }
        ),
        "pipeline-liveness": _liveness(),
    }
    parent_report = build_autonomous_work_execution(base_evidence, now=NOW)
    assert parent_report.selected_work is not None
    parent_id = parent_report.selected_work.candidate_id

    report = build_autonomous_work_execution(
        {
            **base_evidence,
            "released-work": _released_through_broker_diagnostic_liveness(
                AGENT_OPS_FRONTIER_CANDIDATE_ID,
                HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
                PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
                WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
                AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
                OPERATOR_REPORT_LIVENESS_CANDIDATE_ID,
                EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID,
                parent_id,
                BROAD_VALIDATION_FAILURE_COMMAND_REPLAY_CANDIDATE_ID,
            ),
        },
        now=NOW,
    )

    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == BROAD_VALIDATION_FAILURE_DATA_READINESS_CANDIDATE_ID
    )
    validation_map = {
        entry.frontier_key: entry for entry in report.broad_validation_failure_frontier_map
    }
    assert validation_map["command_replay_contract"].coverage_status == "released"
    assert validation_map["data_readiness_contract"].coverage_status == "open"


def test_all_released_no_edge_context_emits_broad_frontier_expansion():
    report = build_autonomous_work_execution(
        _all_known_released_no_edge_evidence(),
        now=NOW,
    )

    assert report.selected_work is not None
    assert report.selected_work.candidate_id.startswith(
        f"{BROAD_FRONTIER_EXPANSION_NO_EDGE_CANDIDATE_PREFIX}-"
    )
    assert report.selected_work.status == STATUS_EXECUTION_READY
    assert report.selected_work.title_ko == "NO_EDGE_YET 기반 광역 투자 frontier 확장"
    assert report.selected_work.blocked_package_refs == ()
    assert "투자 엣지 탐색 축 자체" in report.selected_work.reason_ko
    assert "NO_EDGE_YET" in report.selected_work.reason_ko
    assert "전략군" in report.selected_work.next_action_ko
    assert "주문" in " ".join(report.selected_work.safety_boundary)


def test_released_broad_no_edge_parent_advances_without_hash_loop():
    parent_report = build_autonomous_work_execution(
        _all_known_released_no_edge_evidence(),
        now=NOW,
    )
    assert parent_report.selected_work is not None
    parent_id = parent_report.selected_work.candidate_id
    assert parent_id.startswith(f"{BROAD_FRONTIER_EXPANSION_NO_EDGE_CANDIDATE_PREFIX}-")

    repeated_report = build_autonomous_work_execution(
        _all_known_released_no_edge_evidence(parent_id),
        now=NOW,
    )

    assert repeated_report.selected_work is not None
    assert (
        repeated_report.selected_work.candidate_id
        == BROAD_NO_EDGE_ASSET_UNIVERSE_ROTATION_CANDIDATE_ID
    )
    assert not repeated_report.selected_work.candidate_id.startswith(
        f"{BROAD_FRONTIER_EXPANSION_NO_EDGE_CANDIDATE_PREFIX}-"
    )
    assert repeated_report.selected_work.status == STATUS_EXECUTION_READY
    assert repeated_report.selected_work.autonomy_level == AUTONOMY_CODEX_START
    assert repeated_report.selected_work.domain_key == "strategy_design"
    assert "자산군" in repeated_report.selected_work.next_action_ko
    assert "실제 주문" in " ".join(repeated_report.selected_work.safety_boundary)


def test_broad_no_edge_frontier_map_is_deterministic_and_rendered():
    parent_report = build_autonomous_work_execution(
        _all_known_released_no_edge_evidence(),
        now=NOW,
    )
    assert parent_report.selected_work is not None
    parent_id = parent_report.selected_work.candidate_id

    evidence = _all_known_released_no_edge_evidence(parent_id)
    first = build_autonomous_work_execution(evidence, now=NOW).to_dict()
    second = build_autonomous_work_execution(evidence, now=NOW).to_dict()

    assert first["broad_no_edge_frontier_map"] == second[
        "broad_no_edge_frontier_map"
    ]
    assert (
        first["broad_no_edge_frontier_map"][0]["recommended_candidate_id"]
        == BROAD_NO_EDGE_ASSET_UNIVERSE_ROTATION_CANDIDATE_ID
    )
    assert first["broad_no_edge_frontier_map"][0]["coverage_status"] == "open"
    assert set(first["broad_no_edge_frontier_map"][0]["review_axes"]) >= {
        "strategy_family",
        "asset_universe",
    }

    markdown = build_autonomous_work_execution(evidence, now=NOW).as_markdown()
    assert "## 광역 no-edge frontier 지도" in markdown
    assert BROAD_NO_EDGE_ASSET_UNIVERSE_ROTATION_CANDIDATE_ID in markdown


def test_released_broad_no_edge_entry_advances_to_next_entry():
    parent_report = build_autonomous_work_execution(
        _all_known_released_no_edge_evidence(),
        now=NOW,
    )
    assert parent_report.selected_work is not None
    parent_id = parent_report.selected_work.candidate_id

    report = build_autonomous_work_execution(
        _all_known_released_no_edge_evidence(
            parent_id,
            BROAD_NO_EDGE_ASSET_UNIVERSE_ROTATION_CANDIDATE_ID,
        ),
        now=NOW,
    )

    assert report.selected_work is not None
    assert (
        report.selected_work.candidate_id
        == BROAD_NO_EDGE_MULTI_HORIZON_SIGNAL_CANDIDATE_ID
    )
    broad_map = {entry.frontier_key: entry for entry in report.broad_no_edge_frontier_map}
    assert broad_map["asset_universe_rotation"].coverage_status == "released"
    assert broad_map["multi_horizon_signal"].coverage_status == "open"


def test_macro_candidate_map_is_deterministic_and_rendered():
    evidence = {
        "capital-path-readiness": _json(
            {
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ]
            }
        ),
        "released-work": _json(
            {
                "released_work": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "status": "released",
                        "reason_ko": "스펙 078 완료",
                    },
                    {
                        "candidate_id": MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 088 완료",
                    },
                    {
                        "candidate_id": MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 089 완료",
                    },
                    {
                        "candidate_id": MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 091 완료",
                    },
                    {
                        "candidate_id": FRONTIER_DISCOVERY_CANDIDATE_ID,
                        "status": "released",
                        "reason_ko": "스펙 092 완료",
                    },
                    {
                        "candidate_id": MACRO_CANDIDATE_MAP_REGENERATOR_ID,
                        "status": "released",
                        "reason_ko": "스펙 093 완료",
                    },
                ]
            }
        ),
        "pipeline-liveness": _liveness(),
    }

    first = build_autonomous_work_execution(evidence, now=NOW).to_dict()
    second = build_autonomous_work_execution(evidence, now=NOW).to_dict()

    assert first["macro_candidate_map"] == second["macro_candidate_map"]
    assert first["macro_candidate_map"][0]["domain_key"] == "investment_edge"
    assert (
        first["macro_candidate_map"][0]["recommended_candidate_id"]
        == INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID
    )
    assert first["macro_candidate_map"][0]["coverage_status"] in {
        "exhausted",
        "underexplored",
    }

    markdown = build_autonomous_work_execution(evidence, now=NOW).as_markdown()
    assert "## 거시 후보 지도" in markdown
    assert INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID in markdown


def test_macro_growth_does_not_mask_operator_approval_candidate():
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
    ranked_ids = {packet.candidate_id for packet in report.ranked_work}
    assert MACRO_GROWTH_DISCOVERY_CANDIDATE_ID not in ranked_ids


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


def _source_refs(packet) -> set[str]:
    return set(packet.source_refs)
