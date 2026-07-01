"""스펙 071 — 후보 결과 실행기 단위 테스트."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.candidate_factory import build_candidate_factory_run
from auto_invest.analytics.candidate_result_executor import (
    DIAG_COMMAND_CONTRACT_ERROR,
    DIAG_DATA_HISTORY_MISSING,
    DIAG_INSUFFICIENT_PASS_EVIDENCE,
    DIAG_UNSAFE_COMMAND,
    STATUS_BLOCKED,
    STATUS_PASS,
    STATUS_PENDING,
    CommandExecution,
    build_candidate_result_executor_run,
)
from auto_invest.analytics.promotion_loop import (
    STAGE_FORWARD_REGISTRATION_READY,
    scan_promotion,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "candidate_factory" / "fresh"
NOW = datetime(2026, 6, 30, 3, 0, 0, tzinfo=UTC)


def _json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _package_plan() -> dict:
    factory = build_candidate_factory_run(
        candidate_backlog=_json("candidate_backlog.json"),
        promotion_summary=_json("promotion_summary.json"),
        now=NOW,
        commit="abc1234",
        run_id="factory",
    )
    return factory.package_plan_dict()


def _passing_runner(command: list[str] | tuple[str, ...], timeout: int) -> CommandExecution:
    if "portfolio-walk-forward" in command:
        return CommandExecution(
            command=tuple(command),
            exit_code=0,
            stdout=json.dumps(
                {
                    "n_segments": 5,
                    "segments_strategy_wins": 3,
                    "strategy_dsr": "0.96",
                    "verdict": "강건한 엣지 신호: 다중검정 통과",
                },
                ensure_ascii=False,
            ),
            stderr="",
        )
    return CommandExecution(command=tuple(command), exit_code=0, stdout="{}", stderr="")


def _pending_runner(command: list[str] | tuple[str, ...], timeout: int) -> CommandExecution:
    return CommandExecution(
        command=tuple(command),
        exit_code=64,
        stdout="",
        stderr="no ingested datasets; run `auto-invest ingest-history`",
    )


def test_executor_creates_one_result_for_every_current_candidate_package() -> None:
    run = build_candidate_result_executor_run(
        package_plan=_package_plan(),
        now=NOW,
        commit="abc1234",
        run_id="unit",
        runner=_passing_runner,
    )
    assert len(run.results) == 9
    assert {row.candidate_id for row in run.results} == {
        candidate["candidate_id"]
        for candidate in _json("candidate_backlog.json")["candidates"]
    }
    assert run.counts[STATUS_PASS] == 9


def test_missing_strategy_data_is_pending_not_false_pass() -> None:
    plan = _package_plan()
    plan["packages"] = [
        package
        for package in plan["packages"]
        if package["candidate_id"] == "candidate-1ed634d8bf6d"
    ]
    run = build_candidate_result_executor_run(
        package_plan=plan,
        now=NOW,
        runner=_pending_runner,
    )
    result = run.results[0]
    assert result.status == STATUS_PENDING
    assert result.historical_backtest == "pending"
    assert result.recent_oos == "pending"
    assert result.walk_forward == "pending"
    assert result.retryable is True
    payload = result.to_dict()
    assert payload["diagnostics"][0]["code"] == DIAG_DATA_HISTORY_MISSING
    assert payload["next_actions"][0]["action_code"] == "prepare_history_dataset"


def test_strategy_verdict_is_case_insensitive() -> None:
    plan = _package_plan()
    plan["packages"] = [
        package
        for package in plan["packages"]
        if package["candidate_id"] == "candidate-1ed634d8bf6d"
    ]

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> CommandExecution:
        return CommandExecution(
            command=tuple(command),
            exit_code=0,
            stdout=json.dumps({"verdict": "edge_confirmed"}),
            stderr="",
        )

    run = build_candidate_result_executor_run(
        package_plan=plan,
        now=NOW,
        runner=runner,
    )
    assert run.results[0].status == STATUS_PASS
    assert run.results[0].walk_forward == "pass"


def test_strategy_history_root_command_is_allowed_and_can_pass() -> None:
    seen: list[tuple[str, ...]] = []

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> CommandExecution:
        seen.append(tuple(command))
        return CommandExecution(
            command=tuple(command),
            exit_code=0,
            stdout=json.dumps({"strategy_dsr": "0.97", "verdict": "EDGE_CONFIRMED"}),
            stderr="",
        )

    run = build_candidate_result_executor_run(
        package_plan={
            "schema_version": "1.0",
            "packages": [
                {
                    "package_id": "pkg-history",
                    "candidate_id": "candidate-history",
                    "package_kind": "strategy_backtest",
                    "status": "ready",
                    "commands": [
                        "uv run auto-invest portfolio-walk-forward "
                        "--portfolio deploy/micro-gtaa-live-portfolio.toml "
                        "--trailing-years 5 "
                        "--history-root /tmp/candidate_result_history/micro-gtaa/hist "
                        "--db data/candidate-factory/candidate-history.db "
                        "--halt-path data/candidate-factory/candidate-history.halt.flag "
                        "--json"
                    ],
                }
            ],
        },
        now=NOW,
        runner=runner,
    )

    assert seen == [
        (
            "uv",
            "run",
            "auto-invest",
            "portfolio-walk-forward",
            "--portfolio",
            "deploy/micro-gtaa-live-portfolio.toml",
            "--trailing-years",
            "5",
            "--history-root",
            "/tmp/candidate_result_history/micro-gtaa/hist",
            "--db",
            "data/candidate-factory/candidate-history.db",
            "--halt-path",
            "data/candidate-factory/candidate-history.halt.flag",
            "--json",
        )
    ]
    assert run.results[0].status == STATUS_PASS


def test_unsafe_command_is_blocked_without_execution() -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> CommandExecution:
        calls.append(tuple(command))
        return CommandExecution(command=tuple(command), exit_code=0, stdout="{}", stderr="")

    run = build_candidate_result_executor_run(
        package_plan={
            "schema_version": "1.0",
            "packages": [
                {
                    "package_id": "pkg-unsafe",
                    "candidate_id": "candidate-unsafe",
                    "package_kind": "strategy_backtest",
                    "status": "ready",
                    "commands": ["uv run auto-invest rebalance-once --mode live --confirm-live"],
                }
            ],
        },
        now=NOW,
        runner=runner,
    )
    assert run.results[0].status == STATUS_BLOCKED
    assert "안전하지 않은 명령" in str(run.results[0].block_reason_ko)
    assert run.results[0].to_dict()["diagnostics"][0]["code"] == DIAG_UNSAFE_COMMAND
    assert run.results[0].retryable is False
    assert calls == []


def test_mixed_strategy_pending_keeps_data_gap_and_insufficient_evidence() -> None:
    plan = _package_plan()
    plan["packages"] = [
        package
        for package in plan["packages"]
        if package["candidate_id"] == "candidate-1ed634d8bf6d"
    ]

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> CommandExecution:
        if "portfolio-walk-forward" in command:
            return CommandExecution(
                command=tuple(command),
                exit_code=64,
                stdout="",
                stderr="no ingested datasets; run `auto-invest ingest-history`",
            )
        return CommandExecution(
            command=tuple(command),
            exit_code=0,
            stdout="챔피언: 3자산 역변동성 추세 +금 — 방어 엣지",
            stderr="",
        )

    run = build_candidate_result_executor_run(
        package_plan=plan,
        now=NOW,
        runner=runner,
    )
    result = run.results[0]
    assert result.status == STATUS_PENDING
    codes = {item["code"] for item in result.to_dict()["diagnostics"]}
    assert DIAG_DATA_HISTORY_MISSING in codes
    assert DIAG_INSUFFICIENT_PASS_EVIDENCE in codes
    assert run.diagnostic_counts[DIAG_DATA_HISTORY_MISSING] == 1
    assert run.diagnostic_counts[DIAG_INSUFFICIENT_PASS_EVIDENCE] == 1


def test_command_contract_error_is_machine_readable_for_pending_ops_package() -> None:
    plan = {
        "schema_version": "1.0",
        "packages": [
            {
                "package_id": "pkg-ops",
                "candidate_id": "candidate-ops",
                "package_kind": "ops_liveness",
                "status": "ready",
                "commands": ["uv run python scripts/pipeline_liveness_probe.py --json"],
            }
        ],
    }

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> CommandExecution:
        return CommandExecution(
            command=tuple(command),
            exit_code=2,
            stdout="",
            stderr=(
                "usage: pipeline_liveness_probe.py [-h] [--sidecar-dir SIDECAR_DIR]\n"
                "pipeline_liveness_probe.py: error: --sidecar-dir 가 필요합니다"
            ),
        )

    run = build_candidate_result_executor_run(
        package_plan=plan,
        now=NOW,
        runner=runner,
    )
    result = run.results[0]
    payload = result.to_dict()
    assert result.status == STATUS_PENDING
    assert payload["diagnostics"][0]["code"] == DIAG_COMMAND_CONTRACT_ERROR
    assert payload["next_actions"][0]["action_code"] == "repair_candidate_package_command"
    assert payload["retryable"] is False


def test_data_quality_pipeline_liveness_command_is_allowed_and_can_pass() -> None:
    seen: list[tuple[str, ...]] = []

    def runner(command: list[str] | tuple[str, ...], timeout: int) -> CommandExecution:
        seen.append(tuple(command))
        return CommandExecution(
            command=tuple(command),
            exit_code=0,
            stdout=json.dumps({"overall_status": "OK"}),
            stderr="",
        )

    run = build_candidate_result_executor_run(
        package_plan={
            "schema_version": "1.0",
            "packages": [
                {
                    "package_id": "pkg-data",
                    "candidate_id": "candidate-data",
                    "package_kind": "data_quality",
                    "status": "ready",
                    "commands": [
                        "uv run python scripts/pipeline_liveness_probe.py "
                        "--sidecar-dir /tmp/candidate_result_sidecars --strict --json"
                    ],
                }
            ],
        },
        now=NOW,
        runner=runner,
    )

    assert seen == [
        (
            "uv",
            "run",
            "python",
            "scripts/pipeline_liveness_probe.py",
            "--sidecar-dir",
            "/tmp/candidate_result_sidecars",
            "--strict",
            "--json",
        )
    ]
    assert run.results[0].status == STATUS_PASS
    assert run.results[0].factory_validation == "pass"


def test_markdown_reports_diagnostic_counts_and_next_action() -> None:
    run = build_candidate_result_executor_run(
        package_plan={
            "schema_version": "1.0",
            "packages": [
                {
                    "package_id": "pkg-data",
                    "candidate_id": "candidate-data",
                    "package_kind": "data_quality",
                    "status": "ready",
                    "commands": ["uv run auto-invest bars-status --symbols SPY --json"],
                }
            ],
        },
        now=NOW,
        runner=_pending_runner,
    )
    text = run.as_markdown()
    assert "## 진단 집계" in text
    assert f"`{DIAG_DATA_HISTORY_MISSING}`: 1" in text
    assert "다음 행동: 안전한 데이터 수집 또는 ingest-history 실행 경로를 준비한다." in text


def test_executor_results_flow_through_factory_into_forward_ready_stage() -> None:
    package_plan = _package_plan()
    package_plan["packages"] = [
        package
        for package in package_plan["packages"]
        if package["candidate_id"] == "candidate-1ed634d8bf6d"
    ]
    result_run = build_candidate_result_executor_run(
        package_plan=package_plan,
        now=NOW,
        runner=_passing_runner,
    )
    factory = build_candidate_factory_run(
        candidate_backlog=_json("candidate_backlog.json"),
        promotion_summary=_json("promotion_summary.json"),
        result_evidence=result_run.results_document(),
        now=NOW,
    )
    summary = scan_promotion(
        candidate_backlog=factory.enriched_candidate_backlog,
        evidence_texts={},
        now=NOW,
    )
    by_stage = {assessment.candidate_id: assessment.stage for assessment in summary.assessments}
    assert by_stage["candidate-1ed634d8bf6d"] == STAGE_FORWARD_REGISTRATION_READY
