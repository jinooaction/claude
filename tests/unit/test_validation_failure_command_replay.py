"""Validation failure command replay contract tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from auto_invest.analytics.validation_failure_command_replay import (
    COMPLETED_CANDIDATE_ID,
    EXIT_EVIDENCE_MISSING,
    EXIT_EVIDENCE_PRESENT,
    STATUS_BLOCKED_UNSAFE_COMMAND,
    STATUS_CONTRACT_READY,
    STATUS_WAITING_FOR_INPUT,
    build_validation_failure_command_replay,
)

NOW = datetime(2026, 8, 11, 15, 0, 0, tzinfo=UTC)


def _package_plan() -> dict:
    return {
        "schema_version": "1.0",
        "packages": [
            {
                "candidate_id": "candidate-cc96b35062da",
                "package_id": "pkg-8aae8cb99874",
                "package_kind": "portfolio_backtest",
                "title_ko": "비상관 포트폴리오 후보 비교력 강화",
                "status": "blocked",
                "commands": [
                    "uv run auto-invest portfolio-walk-forward "
                    "--portfolio deploy/global-trend-wide-portfolio.toml "
                    "--trailing-years 5 "
                    "--history-root /tmp/candidate_result_history/global-trend-wide/hist "
                    "--db data/candidate-factory/candidate-cc96b35062da-wide.db "
                    "--halt-path data/candidate-factory/candidate-cc96b35062da.halt.flag "
                    "--json",
                    "uv run auto-invest portfolio-walk-forward "
                    "--portfolio deploy/multi-asset-trend-portfolio.toml "
                    "--trailing-years 5 "
                    "--history-root /tmp/candidate_result_history/multi-asset-trend/hist "
                    "--db data/candidate-factory/candidate-cc96b35062da-multi.db "
                    "--halt-path data/candidate-factory/candidate-cc96b35062da.halt.flag "
                    "--json",
                ],
                "promotion_patch": _promotion_patch("portfolio_backtest", "pkg-8aae8cb99874"),
            },
            {
                "candidate_id": "candidate-1ed634d8bf6d",
                "package_id": "pkg-c9a284fa4235",
                "package_kind": "strategy_backtest",
                "title_ko": "micro GTAA 의도 손익 재검토와 대체 전략 연구",
                "status": "blocked",
                "commands": [
                    "uv run auto-invest portfolio-walk-forward "
                    "--portfolio deploy/micro-gtaa-live-portfolio.toml "
                    "--trailing-years 5 "
                    "--history-root /tmp/candidate_result_history/micro-gtaa/hist "
                    "--db data/candidate-factory/candidate-1ed634d8bf6d.db "
                    "--halt-path data/candidate-factory/candidate-1ed634d8bf6d.halt.flag "
                    "--json",
                    "uv run python scripts/deep_walk_forward_probe.py --segment-months 60",
                ],
                "promotion_patch": _promotion_patch("strategy_backtest", "pkg-c9a284fa4235"),
            },
        ],
    }


def _result_evidence() -> dict:
    return {
        "schema_version": "1.0",
        "results": [
            _blocked_result(
                candidate_id="candidate-cc96b35062da",
                package_id="pkg-8aae8cb99874",
                package_kind="portfolio_backtest",
            ),
            _blocked_result(
                candidate_id="candidate-1ed634d8bf6d",
                package_id="pkg-c9a284fa4235",
                package_kind="strategy_backtest",
            ),
        ],
    }


def _promotion_patch(kind: str, package_id: str) -> dict:
    return {
        "factory_status": "blocked",
        "factory_retryable": True,
        "factory_package_id": package_id,
        "factory_kind": kind,
        "factory_diagnostics": [
            {
                "code": "execution_failed",
                "retryable": True,
                "severity": "warning",
                "summary_ko": "검증 명령이 비정상 종료했다.",
            }
        ],
        "factory_next_actions": [
            {
                "action_code": "inspect_validation_failure",
                "owner": "automation",
                "safe_to_auto_run": True,
                "summary_ko": "종료 코드와 제한된 출력을 바탕으로 실패 원인을 더 좁힌다.",
            }
        ],
    }


def _blocked_result(*, candidate_id: str, package_id: str, package_kind: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "package_id": package_id,
        "package_kind": package_kind,
        "status": "blocked",
        "executions": [],
        "retryable": True,
        "diagnostics": [
            {
                "code": "execution_failed",
                "retryable": True,
                "severity": "warning",
                "summary_ko": "검증 명령이 비정상 종료했다.",
            }
        ],
        "next_actions": [
            {
                "action_code": "inspect_validation_failure",
                "summary_ko": "종료 코드와 제한된 출력을 바탕으로 실패 원인을 더 좁힌다.",
            }
        ],
    }


def test_current_blocked_packages_become_safe_replay_contract_rows() -> None:
    report = build_validation_failure_command_replay(
        package_plan=_package_plan(),
        result_evidence=_result_evidence(),
        now=NOW,
        run_id="unit",
        commit="abc123",
    )

    payload = report.to_dict()

    assert report.overall_status == STATUS_CONTRACT_READY
    assert payload["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert payload["package_count"] == 2
    assert payload["command_count"] == 4
    assert payload["replay_safe_count"] == 4
    assert payload["missing_execution_count"] == 4
    assert {
        row["package_id"] for row in payload["command_replay_contract"]
    } == {"pkg-8aae8cb99874", "pkg-c9a284fa4235"}
    assert all(row["safe_to_replay"] for row in payload["command_replay_contract"])
    assert all(
        row["exit_code_evidence_status"] == EXIT_EVIDENCE_MISSING
        for row in payload["command_replay_contract"]
    )
    assert all(
        "execution_failed" in row["diagnostic_codes"]
        for row in payload["command_replay_contract"]
    )
    assert all(
        row["next_action_code"] == "inspect_validation_failure"
        for row in payload["command_replay_contract"]
    )


def test_execution_evidence_is_joined_by_command_tokens_and_redacted() -> None:
    packages = _package_plan()
    command = packages["packages"][1]["commands"][0]
    results = _result_evidence()
    results["results"][1]["executions"] = [
            {
                "command": command.split(),
                "exit_code": 64,
                "stdout_excerpt": (
                    '{"verdict":"NO_EDGE","access_token":'
                    '"abcd1234abcd1234abcd1234abcd1234"}'
                ),
                "stderr_excerpt": "no ingested datasets",
            }
        ]

    report = build_validation_failure_command_replay(
        package_plan=packages,
        result_evidence=results,
        now=NOW,
    )

    rows = {
        (row["package_id"], row["command_index"]): row
        for row in report.to_dict()["command_replay_contract"]
    }
    row = rows[("pkg-c9a284fa4235", 1)]

    assert row["observed_exit_code"] == 64
    assert row["exit_code_evidence_status"] == EXIT_EVIDENCE_PRESENT
    assert "[REDACTED]" in row["stdout_excerpt"]
    assert row["output_digest"]


def test_unsafe_command_blocks_contract_without_execution() -> None:
    packages = _package_plan()
    packages["packages"][0]["commands"] = [
        "uv run auto-invest rebalance-once --mode live --confirm-live"
    ]

    report = build_validation_failure_command_replay(
        package_plan=packages,
        result_evidence=_result_evidence(),
        now=NOW,
    )
    unsafe_rows = [
        row
        for row in report.to_dict()["command_replay_contract"]
        if row["package_id"] == "pkg-8aae8cb99874"
    ]

    assert report.overall_status == STATUS_BLOCKED_UNSAFE_COMMAND
    assert unsafe_rows[0]["safe_to_replay"] is False
    assert "안전하지 않은 명령" in unsafe_rows[0]["safety_reason_ko"]


def test_missing_inputs_wait_without_false_completion() -> None:
    report = build_validation_failure_command_replay(
        package_plan=None,
        result_evidence=None,
        now=NOW,
    )

    assert report.overall_status == STATUS_WAITING_FOR_INPUT
    assert report.to_dict()["command_replay_contract"] == []
    assert set(report.to_dict()["missing_inputs"]) == {
        "candidate_packages.packages",
        "candidate_results.results",
    }


def test_markdown_is_deterministic_and_contains_safety_boundary() -> None:
    first = build_validation_failure_command_replay(
        package_plan=_package_plan(),
        result_evidence=_result_evidence(),
        now=NOW,
    ).as_markdown()
    second = build_validation_failure_command_replay(
        package_plan=json.loads(json.dumps(_package_plan())),
        result_evidence=json.loads(json.dumps(_result_evidence())),
        now=NOW,
    ).as_markdown()

    assert first == second
    assert "## 명령별 계약" in first
    assert "no broker API call" in first
    assert "no command execution" in first
