"""Validation failure package-kind expansion contract tests."""

from __future__ import annotations

import json
import shlex
from datetime import UTC, datetime

from auto_invest.analytics.validation_failure_package_kind_expansion import (
    COMPLETED_CANDIDATE_ID,
    STATUS_CONTRACT_READY,
    STATUS_READY_FOR_AXIS_EXPANSION,
    STATUS_WAITING_FOR_EVIDENCE,
    build_validation_failure_package_kind_expansion,
)

NOW = datetime(2026, 8, 12, 2, 15, 0, tzinfo=UTC)


def _package_plan() -> dict:
    return {
        "schema_version": "1.0",
        "packages": [
            {
                "candidate_id": "candidate-cc96b35062da",
                "domain_key": "portfolio_design",
                "package_id": "pkg-8aae8cb99874",
                "package_kind": "portfolio_backtest",
                "title_ko": "비상관 포트폴리오 후보 비교력 강화",
                "status": "blocked",
                "commands": [_global_wide_command(), _multi_asset_command()],
                "promotion_patch": _promotion_patch("portfolio_backtest"),
            },
            {
                "candidate_id": "candidate-1ed634d8bf6d",
                "domain_key": "strategy_design",
                "package_id": "pkg-c9a284fa4235",
                "package_kind": "strategy_backtest",
                "title_ko": "micro GTAA 의도 손익 재검토와 대체 전략 연구",
                "status": "blocked",
                "commands": [
                    _micro_gtaa_command(),
                    "uv run python scripts/deep_walk_forward_probe.py --segment-months 60",
                ],
                "promotion_patch": _promotion_patch("strategy_backtest"),
            },
        ],
    }


def _promotion_patch(kind: str) -> dict:
    next_action = {
        "action_code": "inspect_validation_failure",
        "owner": "automation",
        "safe_to_auto_run": True,
        "summary_ko": "종료 코드와 제한된 출력을 바탕으로 실패 원인을 더 좁힌다.",
    }
    return {
        "factory_diagnostics": [
            {
                "code": "execution_failed",
                "details": {"package_kind": kind},
                "next_actions": [next_action],
                "retryable": True,
                "severity": "warning",
                "summary_ko": "검증 명령이 비정상 종료했다.",
            }
        ],
        "factory_kind": kind,
        "factory_next_actions": [next_action],
        "factory_retryable": True,
        "factory_status": "blocked",
    }


def _result_evidence() -> dict:
    return {
        "schema_version": "1.0",
        "results": [
            {
                "candidate_id": "candidate-cc96b35062da",
                "package_id": "pkg-8aae8cb99874",
                "package_kind": "portfolio_backtest",
                "status": "fail",
                "historical_backtest": "fail",
                "recent_oos": "fail",
                "walk_forward": "fail",
                "block_reason_ko": "전략 검증 출력이 엣지 없음 또는 실패를 보고했다.",
                "executions": [
                    _execution(
                        _global_wide_command(),
                        {
                            "segments_strategy_wins": 1,
                            "n_segments": 3,
                            "mean_strategy_sharpe": "1.106973",
                            "mean_benchmark_sharpe": "1.361360",
                            "strategy_psr": "0.984746",
                            "strategy_dsr": "0.984746",
                            "verdict": (
                                "강건한 엣지 없음: 구간 과반 실패(1/3); "
                                "평균 샤프가 단순 보유 이하."
                            ),
                        },
                    ),
                    _execution(
                        _multi_asset_command(),
                        {
                            "segments_strategy_wins": 0,
                            "n_segments": 3,
                            "mean_strategy_sharpe": "1.182496",
                            "mean_benchmark_sharpe": "1.435841",
                            "strategy_psr": "0.972404",
                            "strategy_dsr": "0.972404",
                            "verdict": (
                                "강건한 엣지 없음: 구간 과반 실패(0/3); "
                                "평균 샤프가 단순 보유 이하."
                            ),
                        },
                    ),
                ],
            },
            {
                "candidate_id": "candidate-1ed634d8bf6d",
                "package_id": "pkg-c9a284fa4235",
                "package_kind": "strategy_backtest",
                "status": "fail",
                "historical_backtest": "fail",
                "recent_oos": "fail",
                "walk_forward": "fail",
                "block_reason_ko": "전략 검증 출력이 엣지 없음 또는 실패를 보고했다.",
                "executions": [
                    _execution(
                        _micro_gtaa_command(),
                        {
                            "segments_strategy_wins": 1,
                            "n_segments": 3,
                            "mean_strategy_sharpe": "1.725878",
                            "mean_benchmark_sharpe": "1.971776",
                            "strategy_psr": "0.999423",
                            "strategy_dsr": "0.999423",
                            "verdict": (
                                "강건한 엣지 없음: 구간 과반 실패(1/3); "
                                "평균 샤프가 단순 보유 이하."
                            ),
                        },
                    ),
                    {
                        "command": shlex.split(
                            "uv run python scripts/deep_walk_forward_probe.py "
                            "--segment-months 60"
                        ),
                        "exit_code": 0,
                        "stdout_excerpt": (
                            "깊은 OOS walk-forward — 추세 후보 vs 등가중 3자산 단순 보유\n"
                            "3자산 역변동성 추세 +금 (스펙 047, 라이브)       🏆 수익 엣지"
                        ),
                        "stderr_excerpt": "1971~: 주식·채권 667개월 (1971-01-01 … 2026-07-01)",
                        "timed_out": False,
                    },
                ],
            },
        ],
    }


def _execution(command: str, payload: dict) -> dict:
    return {
        "command": shlex.split(command),
        "exit_code": 0,
        "stdout_excerpt": json.dumps(payload, ensure_ascii=False),
        "stderr_excerpt": "",
        "timed_out": False,
    }


def _global_wide_command() -> str:
    return (
        "uv run auto-invest portfolio-walk-forward "
        "--portfolio deploy/global-trend-wide-portfolio.toml "
        "--trailing-years 5 "
        "--history-root /tmp/candidate_result_history/global-trend-wide/hist "
        "--db data/candidate-factory/candidate-cc96b35062da-wide.db "
        "--halt-path data/candidate-factory/candidate-cc96b35062da.halt.flag "
        "--json"
    )


def _multi_asset_command() -> str:
    return (
        "uv run auto-invest portfolio-walk-forward "
        "--portfolio deploy/multi-asset-trend-portfolio.toml "
        "--trailing-years 5 "
        "--history-root /tmp/candidate_result_history/multi-asset-trend/hist "
        "--db data/candidate-factory/candidate-cc96b35062da-multi.db "
        "--halt-path data/candidate-factory/candidate-cc96b35062da.halt.flag "
        "--json"
    )


def _micro_gtaa_command() -> str:
    return (
        "uv run auto-invest portfolio-walk-forward "
        "--portfolio deploy/micro-gtaa-live-portfolio.toml "
        "--trailing-years 5 "
        "--history-root /tmp/candidate_result_history/micro-gtaa/hist "
        "--db data/candidate-factory/candidate-1ed634d8bf6d.db "
        "--halt-path data/candidate-factory/candidate-1ed634d8bf6d.halt.flag "
        "--json"
    )


def _report():
    return build_validation_failure_package_kind_expansion(
        package_plan=_package_plan(),
        result_evidence=_result_evidence(),
        now=NOW,
        run_id="unit",
        commit="abc123",
    )


def test_current_failed_packages_split_into_two_package_kind_buckets() -> None:
    report = _report()
    payload = report.to_dict()

    assert report.overall_status == STATUS_CONTRACT_READY
    assert payload["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert payload["package_count"] == 2
    assert payload["bucket_count"] == 2
    assert payload["retryable_count"] == 2
    assert payload["command_count"] == 4
    assert payload["execution_evidence_count"] == 4

    buckets = {
        bucket["package_kind"]: bucket
        for bucket in payload["package_kind_expansion_contract"]
    }
    assert set(buckets) == {"portfolio_backtest", "strategy_backtest"}
    assert buckets["portfolio_backtest"]["bucket_status"] == STATUS_READY_FOR_AXIS_EXPANSION
    assert buckets["strategy_backtest"]["bucket_status"] == STATUS_READY_FOR_AXIS_EXPANSION
    assert buckets["portfolio_backtest"]["package_refs"][0]["package_id"] == "pkg-8aae8cb99874"
    assert buckets["strategy_backtest"]["package_refs"][0]["package_id"] == "pkg-c9a284fa4235"
    assert buckets["portfolio_backtest"]["metric_summary"]["segment_win_values"] == [
        "0/3",
        "1/3",
    ]
    assert len(buckets["portfolio_backtest"]["metric_summary"]["verdicts"]) == 2


def test_strategy_and_portfolio_get_different_no_live_axes() -> None:
    buckets = {
        bucket["package_kind"]: bucket
        for bucket in _report().to_dict()["package_kind_expansion_contract"]
    }

    portfolio_axes = {axis["axis_key"] for axis in buckets["portfolio_backtest"]["experiment_axes"]}
    strategy_axes = {axis["axis_key"] for axis in buckets["strategy_backtest"]["experiment_axes"]}

    assert "portfolio_design" in portfolio_axes
    assert "asset_universe" in portfolio_axes
    assert "strategy_family" not in portfolio_axes
    assert "strategy_family" in strategy_axes
    assert "signal_family" in strategy_axes
    assert "portfolio_design" not in strategy_axes
    assert "holding_period" in portfolio_axes & strategy_axes
    assert "3자산 역변동성" in " ".join(
        buckets["strategy_backtest"]["metric_summary"]["text_hints"]
    )
    assert all(
        "live" not in axis["axis_key"]
        for axis in buckets["strategy_backtest"]["experiment_axes"]
    )


def test_missing_result_evidence_waits_without_false_completion() -> None:
    report = build_validation_failure_package_kind_expansion(
        package_plan=_package_plan(),
        result_evidence={"schema_version": "1.0", "results": []},
        now=NOW,
    )
    payload = report.to_dict()

    assert report.overall_status == STATUS_WAITING_FOR_EVIDENCE
    assert payload["bucket_count"] == 2
    assert payload["execution_evidence_count"] == 0
    assert all(
        bucket["bucket_status"] == STATUS_WAITING_FOR_EVIDENCE
        for bucket in payload["package_kind_expansion_contract"]
    )
    assert all(
        ref["result_status"] == "missing"
        for bucket in payload["package_kind_expansion_contract"]
        for ref in bucket["package_refs"]
    )


def test_markdown_is_deterministic_and_keeps_safety_boundary() -> None:
    first = _report().as_markdown()
    second = build_validation_failure_package_kind_expansion(
        package_plan=json.loads(json.dumps(_package_plan())),
        result_evidence=json.loads(json.dumps(_result_evidence())),
        now=NOW,
        run_id="unit",
        commit="abc123",
    ).as_markdown()

    assert first == second
    assert "## 패키지 종류별 실패 구조" in first
    assert "strategy_backtest" in first
    assert "portfolio_backtest" in first
    assert "no command execution" in first
