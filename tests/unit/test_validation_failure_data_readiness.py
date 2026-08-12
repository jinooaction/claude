"""Validation failure data readiness contract tests."""

from __future__ import annotations

import json
import shlex
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.candidate_history_support import manifest_document
from auto_invest.analytics.validation_failure_data_readiness import (
    COMPLETED_CANDIDATE_ID,
    STATUS_BLOCKED_DATA_INPUT,
    STATUS_CONTRACT_READY,
    STATUS_PASS_DATA_READY,
    STATUS_WAITING_FOR_EVIDENCE,
    build_validation_failure_data_readiness,
)

NOW = datetime(2026, 8, 12, 1, 30, 0, tzinfo=UTC)


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
                    _global_wide_command(),
                    _multi_asset_command(),
                ],
            },
            {
                "candidate_id": "candidate-1ed634d8bf6d",
                "package_id": "pkg-c9a284fa4235",
                "package_kind": "strategy_backtest",
                "title_ko": "micro GTAA 의도 손익 재검토와 대체 전략 연구",
                "status": "blocked",
                "commands": [
                    _micro_gtaa_command(),
                    "uv run python scripts/deep_walk_forward_probe.py --segment-months 60",
                ],
            },
        ],
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
                "executions": [
                    _execution(
                        _global_wide_command(),
                        {
                            "dataset_version": "wide-version",
                            "data_newest_session": "2026-08-10",
                            "data_age_days": 1,
                            "data_staleness": "fresh",
                            "eval_window": ["2022-06-16", "2026-08-10"],
                            "n_segments": 3,
                            "verdict": "강건한 엣지 없음",
                        },
                    ),
                    _execution(
                        _multi_asset_command(),
                        {
                            "dataset_version": "multi-version",
                            "data_newest_session": "2026-08-10",
                            "data_age_days": 1,
                            "data_staleness": "fresh",
                            "eval_window": ["2022-06-10", "2026-08-10"],
                            "n_segments": 3,
                            "verdict": "강건한 엣지 없음",
                        },
                    ),
                ],
            },
            {
                "candidate_id": "candidate-1ed634d8bf6d",
                "package_id": "pkg-c9a284fa4235",
                "package_kind": "strategy_backtest",
                "status": "fail",
                "executions": [
                    _execution(
                        _micro_gtaa_command(),
                        {
                            "dataset_version": "micro-version",
                            "data_newest_session": "2026-08-10",
                            "data_age_days": 1,
                            "data_staleness": "fresh",
                            "eval_window": ["2022-06-16", "2026-08-10"],
                            "n_segments": 3,
                            "verdict": "강건한 엣지 없음",
                        },
                    ),
                    {
                        "command": shlex.split(
                            "uv run python scripts/deep_walk_forward_probe.py "
                            "--segment-months 60"
                        ),
                        "exit_code": 0,
                        "stdout_excerpt": "깊은 OOS walk-forward — 엣지 비교",
                        "stderr_excerpt": "1971-01-01 … 2026-07-01",
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


def _repo_root(tmp_path: Path) -> Path:
    for path in (
        "deploy/global-trend-wide-portfolio.toml",
        "deploy/multi-asset-trend-portfolio.toml",
        "deploy/micro-gtaa-live-portfolio.toml",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("[portfolio]\nid = \"test\"\n", encoding="utf-8")
    return tmp_path


def _public_data_text() -> str:
    return (
        "# 공개 데이터 수집 채널\n\n"
        "```json\n"
        + json.dumps(
            {
                "schema_version": "2.0",
                "as_of": "2026-08-11",
                "overall_ok": False,
                "published": 10,
                "total_items": 11,
                "items": [
                    {
                        "kind": "treasury",
                        "id": "UST10Y",
                        "ok": True,
                        "last_date": "2026-08-10",
                        "issues": [],
                    },
                    {
                        "kind": "bls",
                        "id": "CUUR0000SA0",
                        "ok": False,
                        "last_date": "2026-06-01",
                        "issues": ["신선도 위반"],
                    },
                ],
            },
            ensure_ascii=False,
        )
        + "\n```\n"
    )


def _regime_stratify_text() -> str:
    return """
# 레짐 층화

| 항목 | 값 |
|------|-----|
| commit | abc123 |
| timestamp_utc | 2026-08-12T00:08:05Z |

{"portfolio_id": "global-trend-wide", "total_return_days": 750}
"""


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


def _report(tmp_path: Path):
    return build_validation_failure_data_readiness(
        package_plan=_package_plan(),
        result_evidence=_result_evidence(),
        history_manifest=manifest_document(),
        public_data_text=_public_data_text(),
        regime_stratify_text=_regime_stratify_text(),
        repo_root=_repo_root(tmp_path),
        now=NOW,
        run_id="unit",
        commit="abc123",
    )


def test_current_failed_packages_are_data_ready_not_missing(tmp_path: Path) -> None:
    report = _report(tmp_path)
    payload = report.to_dict()

    assert report.overall_status == STATUS_CONTRACT_READY
    assert payload["completed_candidate_id"] == COMPLETED_CANDIDATE_ID
    assert payload["package_count"] == 2
    assert payload["surface_count"] == 3
    assert payload["data_ready_count"] == 2
    assert payload["waiting_count"] == 0
    assert payload["blocked_count"] == 0
    assert payload["execution_evidence_count"] == 3
    assert payload["public_data_summary"]["status"] == "PARTIAL_RESEARCH_INPUT"
    assert payload["regime_stratify_summary"]["total_return_days"] == 750

    rows = payload["data_readiness_contract"]
    assert {row["readiness_status"] for row in rows} == {STATUS_PASS_DATA_READY}
    assert all(not row["data_missing_causes"] for row in rows)
    assert {
        surface["manifest_dataset_key"]
        for row in rows
        for surface in row["data_surfaces"]
    } == {"global-trend-wide", "multi-asset-trend", "micro-gtaa"}
    assert all(
        surface["history_root_matches_manifest"]
        for row in rows
        for surface in row["data_surfaces"]
    )


def test_history_root_mismatch_blocks_data_input(tmp_path: Path) -> None:
    plan = _package_plan()
    plan["packages"] = [plan["packages"][0]]
    plan["packages"][0]["commands"] = [
        _global_wide_command().replace(
            "/tmp/candidate_result_history/global-trend-wide/hist",
            "/tmp/candidate_result_history/wrong/hist",
        )
    ]

    report = build_validation_failure_data_readiness(
        package_plan=plan,
        result_evidence=_result_evidence(),
        history_manifest=manifest_document(),
        public_data_text=_public_data_text(),
        regime_stratify_text=_regime_stratify_text(),
        repo_root=_repo_root(tmp_path),
        now=NOW,
    )
    row = report.to_dict()["data_readiness_contract"][0]

    assert report.overall_status == STATUS_BLOCKED_DATA_INPUT
    assert row["readiness_status"] == STATUS_BLOCKED_DATA_INPUT
    assert "history_root_mismatch" in row["data_missing_causes"]


def test_missing_result_evidence_waits_without_false_completion(tmp_path: Path) -> None:
    report = build_validation_failure_data_readiness(
        package_plan=_package_plan(),
        result_evidence={"schema_version": "1.0", "results": []},
        history_manifest=manifest_document(),
        public_data_text=_public_data_text(),
        regime_stratify_text=_regime_stratify_text(),
        repo_root=_repo_root(tmp_path),
        now=NOW,
    )

    assert report.overall_status == STATUS_WAITING_FOR_EVIDENCE
    assert report.to_dict()["waiting_count"] == 2
    assert all(
        "missing_execution_evidence" in row["data_missing_causes"]
        or "missing_result_evidence" in row["data_missing_causes"]
        for row in report.to_dict()["data_readiness_contract"]
    )


def test_markdown_is_deterministic_and_contains_safety_boundary(
    tmp_path: Path,
) -> None:
    first = _report(tmp_path).as_markdown()
    second = build_validation_failure_data_readiness(
        package_plan=json.loads(json.dumps(_package_plan())),
        result_evidence=json.loads(json.dumps(_result_evidence())),
        history_manifest=manifest_document(),
        public_data_text=_public_data_text(),
        regime_stratify_text=_regime_stratify_text(),
        repo_root=tmp_path,
        now=NOW,
        run_id="unit",
        commit="abc123",
    ).as_markdown()

    assert first == second
    assert "## 패키지별 준비도" in first
    assert "no command execution" in first
    assert "PARTIAL_RESEARCH_INPUT" in first
