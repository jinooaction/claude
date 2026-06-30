"""스펙 070 — 후보 구현 공장 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.candidate_factory import (
    KIND_ANALYTICS_VALIDATION,
    KIND_DATA_QUALITY,
    KIND_GATE_ALIGNMENT,
    KIND_OPS_LIVENESS,
    KIND_PORTFOLIO_BACKTEST,
    KIND_STRATEGY_BACKTEST,
    STATUS_EVIDENCE_PASSED,
    STATUS_PENDING,
    STATUS_READY,
    build_candidate_factory_run,
)
from auto_invest.analytics.promotion_loop import (
    STAGE_BACKTEST_REQUIRED,
    STAGE_FACTORY_PACKAGE_READY,
    STAGE_FORWARD_REGISTRATION_READY,
    scan_promotion,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "candidate_factory" / "fresh"
NOW = datetime(2026, 6, 29, 3, 0, 0, tzinfo=UTC)


def _json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _run(result_evidence: dict | None = None):
    return build_candidate_factory_run(
        candidate_backlog=_json("candidate_backlog.json"),
        promotion_summary=_json("promotion_summary.json"),
        result_evidence=result_evidence,
        now=NOW,
        commit="abc1234",
        run_id="unit",
    )


def test_factory_builds_one_package_for_every_current_candidate_kind() -> None:
    run = _run()
    assert len(run.packages) == 9
    assert {package.candidate_id for package in run.packages} == {
        candidate["candidate_id"]
        for candidate in _json("candidate_backlog.json")["candidates"]
    }
    by_id = {package.candidate_id: package for package in run.packages}
    assert by_id["candidate-1ed634d8bf6d"].package_kind == KIND_STRATEGY_BACKTEST
    assert by_id["candidate-cc96b35062da"].package_kind == KIND_PORTFOLIO_BACKTEST
    assert by_id["candidate-fd04772a23c5"].package_kind == KIND_GATE_ALIGNMENT
    assert by_id["candidate-88a7e7f07361"].package_kind == KIND_OPS_LIVENESS
    assert by_id["candidate-e481b0309206"].package_kind == KIND_ANALYTICS_VALIDATION
    assert by_id["candidate-6ee3370e933d"].package_kind == KIND_DATA_QUALITY
    assert all(package.status == STATUS_READY for package in run.packages)
    assert "portfolio-walk-forward" in by_id["candidate-1ed634d8bf6d"].commands[0]


def test_factory_emits_current_candidate_support_input_commands() -> None:
    run = _run()
    by_id = {package.candidate_id: package for package in run.packages}

    ops_command = by_id["candidate-88a7e7f07361"].commands[0]
    assert "scripts/pipeline_liveness_probe.py" in ops_command
    assert "--sidecar-dir /tmp/candidate_result_sidecars" in ops_command
    assert "--strict --json" in ops_command

    analytics_command = by_id["candidate-e481b0309206"].commands[0]
    assert analytics_command == (
        "uv run auto-invest macro-regime "
        "--data-dir /tmp/candidate_result_public_data --json"
    )
    assert "--format json" not in analytics_command

    data_quality_command = by_id["candidate-6ee3370e933d"].commands[0]
    assert "scripts/pipeline_liveness_probe.py" in data_quality_command
    assert "--sidecar-dir /tmp/candidate_result_sidecars" in data_quality_command
    assert "bars-status" not in data_quality_command
    assert "data/auto_invest.db" not in data_quality_command


def test_missing_result_evidence_never_creates_false_pass() -> None:
    run = _run()
    enriched = run.enriched_candidate_backlog
    strategy = enriched["candidates"][0]["promotion_evidence"]
    assert strategy["historical_backtest"] == "pending"
    assert strategy["recent_oos"] == "pending"
    assert strategy["walk_forward"] == "pending"
    summary = scan_promotion(candidate_backlog=enriched, evidence_texts={}, now=NOW)
    by_id = {assessment.candidate_id: assessment for assessment in summary.assessments}
    assert by_id["candidate-1ed634d8bf6d"].stage == STAGE_BACKTEST_REQUIRED


def test_strategy_result_evidence_can_advance_to_forward_registration_ready() -> None:
    run = _run(_json("result_evidence.json"))
    by_id = {package.candidate_id: package for package in run.packages}
    assert by_id["candidate-1ed634d8bf6d"].status == STATUS_EVIDENCE_PASSED
    enriched = run.enriched_candidate_backlog
    strategy = enriched["candidates"][0]["promotion_evidence"]
    assert strategy["historical_backtest"] == "pass"
    assert strategy["recent_oos"] == "pass"
    assert strategy["walk_forward"] == "pass"
    assert strategy["forward_track"]["track_key"] == "micro-gtaa-research"

    summary = scan_promotion(candidate_backlog=enriched, evidence_texts={}, now=NOW)
    by_stage = {assessment.candidate_id: assessment.stage for assessment in summary.assessments}
    assert by_stage["candidate-1ed634d8bf6d"] == STAGE_FORWARD_REGISTRATION_READY


def test_non_trading_validation_does_not_pretend_to_be_strategy_backtest() -> None:
    run = _run(_json("result_evidence.json"))
    by_package = {package.candidate_id: package for package in run.packages}
    assert by_package["candidate-fd04772a23c5"].status == STATUS_EVIDENCE_PASSED
    assert run.counts[STATUS_EVIDENCE_PASSED] == 2
    live_readiness = run.enriched_candidate_backlog["candidates"][1]["promotion_evidence"]
    assert live_readiness["factory_validation"] == "pass"
    assert "historical_backtest" not in live_readiness
    summary = scan_promotion(
        candidate_backlog=run.enriched_candidate_backlog,
        evidence_texts={},
        now=NOW,
    )
    by_stage = {assessment.candidate_id: assessment.stage for assessment in summary.assessments}
    assert by_stage["candidate-fd04772a23c5"] == STAGE_FACTORY_PACKAGE_READY


def test_pending_result_diagnostics_flow_into_promotion_evidence_without_false_pass() -> None:
    run = _run(
        {
            "schema_version": "1.0",
            "results": [
                {
                    "candidate_id": "candidate-1ed634d8bf6d",
                    "package_id": "pkg-c9a284fa4235",
                    "package_kind": "strategy_backtest",
                    "status": "pending",
                    "source_ref": "candidate-result-executor:pkg-c9a284fa4235",
                    "historical_backtest": "pending",
                    "recent_oos": "pending",
                    "walk_forward": "pending",
                    "diagnostics": [
                        {
                            "code": "data_history_missing",
                            "severity": "warning",
                            "retryable": True,
                            "summary_ko": "과거 가격 데이터가 준비되지 않았다.",
                            "evidence_source": "command",
                            "next_actions": [
                                {
                            "action_code": "prepare_history_dataset",
                            "summary_ko": (
                                "안전한 데이터 수집 또는 ingest-history 실행 경로를 "
                                "준비한다."
                            ),
                                    "owner": "automation",
                                    "safe_to_auto_run": True,
                                }
                            ],
                            "details": {"exit_code": 64},
                        }
                    ],
                    "next_actions": [
                        {
                            "action_code": "prepare_history_dataset",
                            "summary_ko": (
                                "안전한 데이터 수집 또는 ingest-history 실행 경로를 "
                                "준비한다."
                            ),
                            "owner": "automation",
                            "safe_to_auto_run": True,
                        }
                    ],
                    "retryable": True,
                }
            ],
        }
    )
    by_id = {package.candidate_id: package for package in run.packages}
    assert by_id["candidate-1ed634d8bf6d"].status == STATUS_PENDING
    assert run.counts[STATUS_EVIDENCE_PASSED] == 0
    evidence = run.enriched_candidate_backlog["candidates"][0]["promotion_evidence"]
    assert evidence["historical_backtest"] == "pending"
    assert evidence["factory_diagnostics"][0]["code"] == "data_history_missing"
    assert evidence["factory_next_actions"][0]["action_code"] == "prepare_history_dataset"
    assert evidence["factory_retryable"] is True
    summary = scan_promotion(
        candidate_backlog=run.enriched_candidate_backlog,
        evidence_texts={},
        now=NOW,
    )
    by_stage = {assessment.candidate_id: assessment.stage for assessment in summary.assessments}
    assert by_stage["candidate-1ed634d8bf6d"] == STAGE_BACKTEST_REQUIRED


def test_blocked_result_diagnostics_block_factory_patch() -> None:
    run = _run(
        {
            "schema_version": "1.0",
            "results": [
                {
                    "candidate_id": "candidate-fd04772a23c5",
                    "package_id": "pkg-03d9502cd7de",
                    "package_kind": "gate_alignment",
                    "status": "blocked",
                    "source_ref": "candidate-result-executor:pkg-03d9502cd7de",
                    "block_reason_ko": "자동 실행 안전 범위 밖의 명령이다.",
                    "diagnostics": [
                        {
                            "code": "unsafe_command",
                            "severity": "blocked",
                            "retryable": False,
                            "summary_ko": "자동 실행 안전 범위 밖의 명령이다.",
                            "evidence_source": "package",
                            "next_actions": [
                                {
                            "action_code": "remove_unsafe_command_surface",
                            "summary_ko": (
                                "live, broker, SSH, 자본, whitelist/caps, sentinel "
                                "표면을 제거한다."
                            ),
                                    "owner": "operator",
                                    "safe_to_auto_run": False,
                                }
                            ],
                            "details": {"fragment": "--mode live"},
                        }
                    ],
                    "next_actions": [
                        {
                            "action_code": "remove_unsafe_command_surface",
                            "summary_ko": (
                                "live, broker, SSH, 자본, whitelist/caps, sentinel "
                                "표면을 제거한다."
                            ),
                            "owner": "operator",
                            "safe_to_auto_run": False,
                        }
                    ],
                    "retryable": False,
                }
            ],
        }
    )
    by_id = {package.candidate_id: package for package in run.packages}
    assert by_id["candidate-fd04772a23c5"].status == "blocked"
    evidence = run.enriched_candidate_backlog["candidates"][1]["promotion_evidence"]
    assert evidence["factory_status"] == "blocked"
    assert evidence["factory_diagnostics"][0]["code"] == "unsafe_command"
    assert evidence["factory_retryable"] is False
    assert "factory_validation" not in evidence


def test_hard_safety_surface_is_blocked_without_pass_patch() -> None:
    backlog = _json("candidate_backlog.json")
    backlog["candidates"] = [
        {
            **backlog["candidates"][0],
            "candidate_id": "candidate-unsafe",
            "safety_impact": ["orders"],
        }
    ]
    run = build_candidate_factory_run(
        candidate_backlog=backlog,
        result_evidence={
            "results": [
                {
                    "candidate_id": "candidate-unsafe",
                    "historical_backtest": "pass",
                    "recent_oos": "pass",
                    "walk_forward": "pass",
                }
            ]
        },
        now=NOW,
    )
    package = run.packages[0]
    assert package.status == "blocked"
    evidence = run.enriched_candidate_backlog["candidates"][0]["promotion_evidence"]
    assert evidence["factory_status"] == "blocked"
    assert "historical_backtest" not in evidence
