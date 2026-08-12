"""Validation failure promotion recheck contract tests."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime

from auto_invest.analytics.validation_failure_promotion_recheck import (
    COMPLETED_CANDIDATE_ID,
    STATUS_CONTRACT_READY,
    STATUS_RECHECK_ALLOWED,
    STATUS_SUPPRESSION_ACTIVE,
    STATUS_WAITING_FOR_EVIDENCE,
    build_validation_failure_promotion_recheck,
)

NOW = datetime(2026, 8, 12, 4, 20, 0, tzinfo=UTC)


def _learning_ledger() -> dict:
    return {
        "schema_version": "1.0",
        "entries": [
            {
                "candidate_id": "candidate-cc96b35062da",
                "created_at_utc": "2026-06-28T17:18:21Z",
                "decision": "evidence_dependent",
                "entry_id": "ledger-f6440fc15f37",
                "evidence_package_id": None,
                "next_recheck_condition": "후보가 COMPARABLE 관측 수에 도달하면 재검토",
                "reason_ko": "후보별 전진 관측을 같은 기준으로 묶는다.",
            },
            {
                "candidate_id": "candidate-1ed634d8bf6d",
                "created_at_utc": "2026-07-01T09:30:35Z",
                "decision": "rejected",
                "entry_id": "ledger-5b69ce7cd6b0",
                "evidence_package_id": "autonomous-promotion:28504209238",
                "next_recheck_condition": None,
                "reason_ko": "기계 판독 검증 결과에 실패가 있다.",
            },
            {
                "candidate_id": "candidate-cc96b35062da",
                "created_at_utc": "2026-07-01T09:30:35Z",
                "decision": "rejected",
                "entry_id": "ledger-87e07600d9b6",
                "evidence_package_id": "autonomous-promotion:28504209238",
                "next_recheck_condition": None,
                "reason_ko": "기계 판독 검증 결과에 실패가 있다.",
            },
        ],
    }


def _promotion_summary() -> dict:
    return {
        "schema_version": "1.0",
        "run_id": "31478980165",
        "assessments": [
            _assessment(
                "candidate-1ed634d8bf6d",
                "strategy_design",
                "strategy_backtest",
                "pkg-c9a284fa4235",
                "micro GTAA 의도 손익 재검토와 대체 전략 연구",
            ),
            _assessment(
                "candidate-cc96b35062da",
                "portfolio_design",
                "portfolio_backtest",
                "pkg-8aae8cb99874",
                "비상관 포트폴리오 후보 비교력 강화",
            ),
        ],
    }


def _assessment(
    candidate_id: str,
    domain_key: str,
    package_kind: str,
    package_id: str,
    title_ko: str,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "stage": "DISCARD",
        "blocked_reason_ko": "기존 폐기 결정이 있고 재검토 조건이 없다.",
        "allowed_next_action": "학습 장부에서 폐기된 후보로 유지한다.",
        "candidate": {
            "candidate_id": candidate_id,
            "domain_key": domain_key,
            "source_status": "rejected",
            "title_ko": title_ko,
            "promotion_evidence": {
                "factory_package_id": package_id,
                "factory_kind": package_kind,
                "factory_status": "blocked",
                "factory_retryable": True,
                "factory_diagnostics": [
                    {
                        "code": "execution_failed",
                        "retryable": True,
                        "severity": "warning",
                        "summary_ko": "검증 명령이 비정상 종료했다.",
                    }
                ],
            },
        },
    }


def _result_evidence() -> dict:
    return {
        "schema_version": "1.0",
        "results": [
            _result(
                "candidate-cc96b35062da",
                "pkg-8aae8cb99874",
                "portfolio_backtest",
                "64bbe91cd22768c5045e93e61fa42a1edc4c95e7cef76283fe08fb70be41a36c",
                1,
                "1.106973",
                "1.361360",
            ),
            _result(
                "candidate-1ed634d8bf6d",
                "pkg-c9a284fa4235",
                "strategy_backtest",
                "bc8eecf916b2af971697045b711710135c474faf763c808104d7b5a8de49fc79",
                1,
                "1.725878",
                "1.971776",
            ),
        ],
    }


def _result(
    candidate_id: str,
    package_id: str,
    package_kind: str,
    dataset_version: str,
    wins: int,
    strategy_sharpe: str,
    benchmark_sharpe: str,
) -> dict:
    raw_metrics = {
        "dataset_version": dataset_version,
        "eval_window": ["2022-06-16", "2026-08-10"],
        "n_segments": 3,
        "segments_strategy_wins": wins,
        "mean_strategy_sharpe": strategy_sharpe,
        "mean_benchmark_sharpe": benchmark_sharpe,
        "strategy_psr": "0.999423",
        "strategy_dsr": "0.999423",
        "verdict": "강건한 엣지 없음: 구간 과반 실패. 라이브 배포 정당화 안 됨.",
    }
    return {
        "candidate_id": candidate_id,
        "package_id": package_id,
        "package_kind": package_kind,
        "status": "fail",
        "historical_backtest": "fail",
        "recent_oos": "fail",
        "walk_forward": "fail",
        "raw_metrics": raw_metrics,
        "executions": [
            {
                "command": ["uv", "run", "auto-invest", "portfolio-walk-forward"],
                "exit_code": 0,
                "stdout_excerpt": json.dumps(raw_metrics, ensure_ascii=False),
                "stderr_excerpt": "",
                "timed_out": False,
            }
        ],
    }


def _report():
    return build_validation_failure_promotion_recheck(
        learning_ledger=_learning_ledger(),
        promotion_summary=_promotion_summary(),
        result_evidence=_result_evidence(),
        now=NOW,
        run_id="unit",
        commit="abc123",
    )


def test_current_rejected_candidates_keep_suppression_active() -> None:
    report = _report()
    payload = report.to_dict()

    assert report.overall_status == STATUS_CONTRACT_READY
    assert payload["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert payload["candidate_count"] == 2
    assert payload["suppressed_count"] == 2
    assert payload["allowed_recheck_count"] == 0
    assert payload["waiting_count"] == 0

    rules = {
        rule["candidate_id"]: rule for rule in payload["promotion_recheck_contract"]
    }
    assert set(rules) == {"candidate-1ed634d8bf6d", "candidate-cc96b35062da"}
    assert all(rule["decision_status"] == STATUS_SUPPRESSION_ACTIVE for rule in rules.values())
    assert rules["candidate-cc96b35062da"]["ledger_entry_id"] == "ledger-87e07600d9b6"
    assert rules["candidate-cc96b35062da"]["historical_recheck_conditions"] == [
        "후보가 COMPARABLE 관측 수에 도달하면 재검토"
    ]
    assert all(rule["failure_fingerprint"] for rule in rules.values())


def test_result_pass_allows_recheck_for_that_candidate_only() -> None:
    results = copy.deepcopy(_result_evidence())
    strategy = next(
        item
        for item in results["results"]
        if item["candidate_id"] == "candidate-1ed634d8bf6d"
    )
    strategy["status"] = "pass"
    strategy["historical_backtest"] = "pass"
    strategy["recent_oos"] = "pass"
    strategy["walk_forward"] = "pass"
    strategy["raw_metrics"]["verdict"] = "재검토 가능한 엣지 후보"

    report = build_validation_failure_promotion_recheck(
        learning_ledger=_learning_ledger(),
        promotion_summary=_promotion_summary(),
        result_evidence=results,
        now=NOW,
    )
    rules = {
        rule["candidate_id"]: rule
        for rule in report.to_dict()["promotion_recheck_contract"]
    }

    assert rules["candidate-1ed634d8bf6d"]["decision_status"] == STATUS_RECHECK_ALLOWED
    assert rules["candidate-cc96b35062da"]["decision_status"] == STATUS_SUPPRESSION_ACTIVE
    conditions = {
        item["condition_key"]: item["is_currently_met"]
        for item in rules["candidate-1ed634d8bf6d"]["recheck_conditions"]
    }
    assert conditions["candidate_result_not_failed"] is True
    assert conditions["validation_layers_not_all_failed"] is True


def test_missing_inputs_wait_without_false_recheck() -> None:
    report = build_validation_failure_promotion_recheck(
        learning_ledger=None,
        promotion_summary=_promotion_summary(),
        result_evidence=_result_evidence(),
        now=NOW,
    )
    payload = report.to_dict()

    assert report.overall_status == STATUS_WAITING_FOR_EVIDENCE
    assert payload["missing_inputs"] == ["learning_ledger.entries"]
    assert payload["candidate_count"] == 2
    assert payload["waiting_count"] == 2
    assert payload["allowed_recheck_count"] == 0


def test_candidate_missing_result_waits_without_false_recheck() -> None:
    results = {"schema_version": "1.0", "results": []}
    report = build_validation_failure_promotion_recheck(
        learning_ledger=_learning_ledger(),
        promotion_summary=_promotion_summary(),
        result_evidence=results,
        now=NOW,
    )
    payload = report.to_dict()

    assert report.overall_status == STATUS_WAITING_FOR_EVIDENCE
    assert payload["waiting_count"] == 2
    assert all(
        rule["decision_status"] == STATUS_WAITING_FOR_EVIDENCE
        for rule in payload["promotion_recheck_contract"]
    )
    assert all(
        "candidate-result-executor" in rule["missing_evidence"]
        for rule in payload["promotion_recheck_contract"]
    )


def test_markdown_is_deterministic_and_keeps_safety_boundary() -> None:
    first = _report().as_markdown()
    second = build_validation_failure_promotion_recheck(
        learning_ledger=copy.deepcopy(_learning_ledger()),
        promotion_summary=copy.deepcopy(_promotion_summary()),
        result_evidence=copy.deepcopy(_result_evidence()),
        now=NOW,
        run_id="unit",
        commit="abc123",
    ).as_markdown()

    assert first == second
    assert "## 후보별 재검토 상태" in first
    assert "SUPPRESSION_ACTIVE" in first
    assert "no command execution" in first
