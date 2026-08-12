"""Validation failure data readiness contract.

This module turns blocked candidate validation packages into a deterministic
read-only data readiness contract. It does not execute validation commands. It
only joins package plans, existing execution evidence, candidate history support,
portfolio TOMLs, public-data notes, and regime-stratify notes to separate data
input failures from strategy edge failures.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from auto_invest.analytics.candidate_history_support import (
    manifest_document as default_history_manifest,
)
from auto_invest.analytics.evolution_loop import mask_sensitive_values

SCHEMA_VERSION = "1.0"
COMPLETED_CANDIDATE_ID = "candidate-broad-validation-failure-data-readiness-contract"

STATUS_CONTRACT_READY = "CONTRACT_READY"
STATUS_WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
STATUS_BLOCKED_DATA_INPUT = "BLOCKED_DATA_INPUT"

STATUS_PASS_DATA_READY = "PASS_DATA_READY"

PUBLIC_DATA_OK = "OK"
PUBLIC_DATA_PARTIAL = "PARTIAL_RESEARCH_INPUT"
PUBLIC_DATA_MISSING = "MISSING"

REGIME_STRATIFY_PRESENT = "PRESENT"
REGIME_STRATIFY_MISSING = "MISSING"

BLOCKING_CAUSES = {
    "missing_portfolio_argument",
    "missing_history_root_argument",
    "unsupported_portfolio_manifest",
    "portfolio_toml_missing",
    "history_root_mismatch",
    "data_staleness_not_fresh",
}

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "no command execution",
    "contract only",
)


@dataclass(frozen=True)
class DataReadinessSurface:
    command_index: int
    command_digest: str
    portfolio_path: str | None
    history_root: str | None
    manifest_dataset_key: str | None
    manifest_history_root: str | None
    manifest_db_path: str | None
    portfolio_toml_exists: bool
    history_root_matches_manifest: bool
    execution_exit_code: int | None
    data_newest_session: str | None
    data_age_days: int | None
    data_staleness: str | None
    eval_window_start: str | None
    eval_window_end: str | None
    n_segments: int | None
    surface_status: str
    causes: tuple[str, ...]
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_index": self.command_index,
            "command_digest": self.command_digest,
            "portfolio_path": self.portfolio_path,
            "history_root": self.history_root,
            "manifest_dataset_key": self.manifest_dataset_key,
            "manifest_history_root": self.manifest_history_root,
            "manifest_db_path": self.manifest_db_path,
            "portfolio_toml_exists": self.portfolio_toml_exists,
            "history_root_matches_manifest": self.history_root_matches_manifest,
            "execution_exit_code": self.execution_exit_code,
            "data_newest_session": self.data_newest_session,
            "data_age_days": self.data_age_days,
            "data_staleness": self.data_staleness,
            "eval_window_start": self.eval_window_start,
            "eval_window_end": self.eval_window_end,
            "n_segments": self.n_segments,
            "surface_status": self.surface_status,
            "causes": list(self.causes),
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class DataReadinessRow:
    candidate_id: str
    package_id: str
    package_kind: str
    package_title_ko: str | None
    readiness_status: str
    data_missing_causes: tuple[str, ...]
    execution_count: int
    portfolio_paths: tuple[str, ...]
    history_roots: tuple[str, ...]
    manifest_dataset_keys: tuple[str, ...]
    latest_data_session: str | None
    max_data_age_days: int | None
    data_staleness_values: tuple[str, ...]
    observation_window_start: str | None
    observation_window_end: str | None
    surface_count: int
    data_surfaces: tuple[DataReadinessSurface, ...]
    public_data_status: str
    regime_stratify_status: str
    next_action_code: str
    next_action_ko: str
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "package_id": self.package_id,
            "package_kind": self.package_kind,
            "package_title_ko": self.package_title_ko,
            "readiness_status": self.readiness_status,
            "data_missing_causes": list(self.data_missing_causes),
            "execution_count": self.execution_count,
            "portfolio_paths": list(self.portfolio_paths),
            "history_roots": list(self.history_roots),
            "manifest_dataset_keys": list(self.manifest_dataset_keys),
            "latest_data_session": self.latest_data_session,
            "max_data_age_days": self.max_data_age_days,
            "data_staleness_values": list(self.data_staleness_values),
            "observation_window": {
                "start": self.observation_window_start,
                "end": self.observation_window_end,
            },
            "surface_count": self.surface_count,
            "data_surfaces": [surface.to_dict() for surface in self.data_surfaces],
            "public_data_status": self.public_data_status,
            "regime_stratify_status": self.regime_stratify_status,
            "next_action_code": self.next_action_code,
            "next_action_ko": self.next_action_ko,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class ValidationFailureDataReadinessReport:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    package_count: int
    surface_count: int
    data_ready_count: int
    waiting_count: int
    blocked_count: int
    execution_evidence_count: int
    public_data_summary: Mapping[str, Any]
    regime_stratify_summary: Mapping[str, Any]
    rows: tuple[DataReadinessRow, ...]
    missing_inputs: tuple[str, ...]
    safety_invariants: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "completed_candidate_id": self.completed_candidate_id,
            "package_count": self.package_count,
            "surface_count": self.surface_count,
            "data_ready_count": self.data_ready_count,
            "waiting_count": self.waiting_count,
            "blocked_count": self.blocked_count,
            "execution_evidence_count": self.execution_evidence_count,
            "public_data_summary": dict(self.public_data_summary),
            "regime_stratify_summary": dict(self.regime_stratify_summary),
            "missing_inputs": list(self.missing_inputs),
            "safety_invariants": list(self.safety_invariants),
            "data_readiness_contract": [row.to_dict() for row in self.rows],
        }

    def as_markdown(self) -> str:
        lines = [
            "# 검증 실패 데이터 준비도 계약",
            "",
            "읽기 전용 계약입니다. 이 보고서는 검증 명령을 실행하지 않고, "
            "기존 sidecar와 저장소 파일만 읽어 데이터 입력 문제와 엣지 실패를 분리합니다.",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| schema_version | {self.schema_version} |",
            f"| run_id | {self.run_id} |",
            f"| commit | {self.commit} |",
            f"| timestamp_utc | {self.timestamp_utc} |",
            f"| overall_status | {self.overall_status} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| package_count | {self.package_count} |",
            f"| surface_count | {self.surface_count} |",
            f"| data_ready_count | {self.data_ready_count} |",
            f"| waiting_count | {self.waiting_count} |",
            f"| blocked_count | {self.blocked_count} |",
            f"| execution_evidence_count | {self.execution_evidence_count} |",
            f"| public_data_status | {self.public_data_summary.get('status')} |",
            f"| regime_stratify_status | {self.regime_stratify_summary.get('status')} |",
            "",
            "## 패키지별 준비도",
            "",
            "| 후보 | 패키지 | 준비도 | 표면 | 최신 관측 | 평가 기간 | 원인 | 다음 행동 |",
            "|------|--------|--------|-----:|-----------|-----------|------|-----------|",
        ]
        if not self.rows:
            lines.append("| - | - | - | 0 | - | - | - | - |")
        for row in self.rows:
            causes = ", ".join(row.data_missing_causes) or "-"
            window = (
                f"{row.observation_window_start}..{row.observation_window_end}"
                if row.observation_window_start and row.observation_window_end
                else "-"
            )
            lines.append(
                "| "
                f"`{row.candidate_id}` | "
                f"`{row.package_id}` | "
                f"{row.readiness_status} | "
                f"{row.surface_count} | "
                f"{row.latest_data_session or '-'} | "
                f"{window} | "
                f"{_table(causes)} | "
                f"{_table(row.next_action_ko)} |"
            )
        lines += [
            "",
            "## 안전 경계",
            "",
        ]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        if self.missing_inputs:
            lines += ["", "## 누락 입력", ""]
            for item in self.missing_inputs:
                lines.append(f"- `{item}`")
        return mask_sensitive_values("\n".join(lines))


def build_validation_failure_data_readiness(
    *,
    package_plan: Mapping[str, Any] | None,
    result_evidence: Mapping[str, Any] | None,
    history_manifest: Mapping[str, Any] | None = None,
    public_data_text: str | None = None,
    regime_stratify_text: str | None = None,
    repo_root: Path | str | None = None,
    now: datetime | None = None,
    run_id: str = "local",
    commit: str = "unknown",
) -> ValidationFailureDataReadinessReport:
    timestamp = _iso(now or datetime.now(UTC))
    missing_inputs: list[str] = []
    packages = _packages(package_plan)
    results = _results_by_package(result_evidence)
    manifest = history_manifest or default_history_manifest()
    datasets = _history_datasets_by_portfolio(manifest)
    root = Path(repo_root) if repo_root is not None else Path(".")

    if package_plan is None or not isinstance(package_plan.get("packages"), list):
        missing_inputs.append("candidate_packages.packages")
    if result_evidence is None or not isinstance(result_evidence.get("results"), list):
        missing_inputs.append("candidate_results.results")
    if not datasets:
        missing_inputs.append("candidate_history_support.datasets")
    if public_data_text is None:
        missing_inputs.append("public_data.LAST_RUN.md")
    if regime_stratify_text is None:
        missing_inputs.append("regime_stratify.LAST_RUN.md")

    public_summary = _public_data_summary(public_data_text)
    regime_summary = _regime_stratify_summary(regime_stratify_text)
    rows = tuple(
        _row_for_package(
            package,
            result=results.get(_package_key(package)),
            datasets=datasets,
            repo_root=root,
            public_data_status=_text(public_summary.get("status")),
            regime_stratify_status=_text(regime_summary.get("status")),
        )
        for package in packages
    )
    rows = tuple(sorted(rows, key=_row_sort_key))

    surface_count = sum(row.surface_count for row in rows)
    ready_count = sum(row.readiness_status == STATUS_PASS_DATA_READY for row in rows)
    waiting_count = sum(
        row.readiness_status == STATUS_WAITING_FOR_EVIDENCE for row in rows
    )
    blocked_count = sum(
        row.readiness_status == STATUS_BLOCKED_DATA_INPUT for row in rows
    )
    execution_evidence_count = sum(
        surface.execution_exit_code is not None
        for row in rows
        for surface in row.data_surfaces
    )

    if blocked_count:
        overall = STATUS_BLOCKED_DATA_INPUT
    elif missing_inputs or not rows or waiting_count:
        overall = STATUS_WAITING_FOR_EVIDENCE
    else:
        overall = STATUS_CONTRACT_READY

    return ValidationFailureDataReadinessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        overall_status=overall,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        package_count=len(rows),
        surface_count=surface_count,
        data_ready_count=ready_count,
        waiting_count=waiting_count,
        blocked_count=blocked_count,
        execution_evidence_count=execution_evidence_count,
        public_data_summary=public_summary,
        regime_stratify_summary=regime_summary,
        rows=rows,
        missing_inputs=tuple(missing_inputs),
        safety_invariants=SAFETY_INVARIANTS,
    )


def write_validation_failure_data_readiness_artifacts(
    report: ValidationFailureDataReadinessReport,
    *,
    summary_out: Path | None = None,
    json_out: Path | None = None,
) -> None:
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(report.as_markdown() + "\n", encoding="utf-8")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _row_for_package(
    package: Mapping[str, Any],
    *,
    result: Mapping[str, Any] | None,
    datasets: Mapping[str, Mapping[str, str]],
    repo_root: Path,
    public_data_status: str,
    regime_stratify_status: str,
) -> DataReadinessRow:
    commands = tuple(
        _text(item) for item in package.get("commands") or () if _text(item)
    )
    surfaces = tuple(
        surface
        for index, command in enumerate(commands, start=1)
        if _has_portfolio_surface(command)
        for surface in (
            _surface_for_command(
                command,
                command_index=index,
                result=result,
                datasets=datasets,
                repo_root=repo_root,
            ),
        )
    )
    executions = _executions(result)
    causes: list[str] = []
    if not surfaces:
        causes.append("missing_portfolio_validation_surface")
    for surface in surfaces:
        causes.extend(surface.causes)
    if result is None:
        causes.append("missing_result_evidence")
    if public_data_status == PUBLIC_DATA_MISSING:
        causes.append("missing_public_data_evidence")
    elif public_data_status == STATUS_WAITING_FOR_EVIDENCE:
        causes.append("unparseable_public_data_evidence")
    if regime_stratify_status == REGIME_STRATIFY_MISSING:
        causes.append("missing_regime_stratify_evidence")
    elif regime_stratify_status == STATUS_WAITING_FOR_EVIDENCE:
        causes.append("unparseable_regime_stratify_evidence")

    unique_causes = tuple(sorted(set(causes)))
    if any(cause in BLOCKING_CAUSES for cause in unique_causes):
        readiness = STATUS_BLOCKED_DATA_INPUT
    elif unique_causes:
        readiness = STATUS_WAITING_FOR_EVIDENCE
    else:
        readiness = STATUS_PASS_DATA_READY
    action_code, action_ko = _next_action(readiness, unique_causes)

    return DataReadinessRow(
        candidate_id=_text(package.get("candidate_id")) or "unknown",
        package_id=_text(package.get("package_id")) or "unknown",
        package_kind=_text(package.get("package_kind")) or "unknown",
        package_title_ko=_text(package.get("title_ko")) or None,
        readiness_status=readiness,
        data_missing_causes=unique_causes,
        execution_count=len(executions),
        portfolio_paths=_unique(
            surface.portfolio_path for surface in surfaces if surface.portfolio_path
        ),
        history_roots=_unique(
            surface.history_root for surface in surfaces if surface.history_root
        ),
        manifest_dataset_keys=_unique(
            surface.manifest_dataset_key
            for surface in surfaces
            if surface.manifest_dataset_key
        ),
        latest_data_session=_max_text(
            surface.data_newest_session for surface in surfaces
        ),
        max_data_age_days=_max_int(surface.data_age_days for surface in surfaces),
        data_staleness_values=_unique(
            surface.data_staleness for surface in surfaces if surface.data_staleness
        ),
        observation_window_start=_min_text(
            surface.eval_window_start for surface in surfaces
        ),
        observation_window_end=_max_text(surface.eval_window_end for surface in surfaces),
        surface_count=len(surfaces),
        data_surfaces=tuple(sorted(surfaces, key=lambda item: item.command_index)),
        public_data_status=public_data_status,
        regime_stratify_status=regime_stratify_status,
        next_action_code=action_code,
        next_action_ko=action_ko,
        source_refs=(
            f"candidate-packages:{_text(package.get('package_id')) or 'unknown'}",
            f"candidate-result-executor:{_text(package.get('package_id')) or 'unknown'}",
            "candidate-history-support:manifest",
            "public-data:LAST_RUN.md",
            "regime-stratify:LAST_RUN.md",
        ),
    )


def _surface_for_command(
    command: str,
    *,
    command_index: int,
    result: Mapping[str, Any] | None,
    datasets: Mapping[str, Mapping[str, str]],
    repo_root: Path,
) -> DataReadinessSurface:
    tokens = _command_tokens(command)
    portfolio_path = _option_value(tokens, "--portfolio")
    history_root = _option_value(tokens, "--history-root")
    dataset = datasets.get(_normalize_path(portfolio_path)) if portfolio_path else None
    execution = _matching_execution(result, command)
    metrics = _stdout_metrics(execution)
    causes: list[str] = []

    if not portfolio_path:
        causes.append("missing_portfolio_argument")
    if not history_root:
        causes.append("missing_history_root_argument")
    if portfolio_path and dataset is None:
        causes.append("unsupported_portfolio_manifest")
    portfolio_exists = bool(
        portfolio_path and (repo_root / Path(portfolio_path)).is_file()
    )
    if portfolio_path and not portfolio_exists:
        causes.append("portfolio_toml_missing")
    manifest_history_root = dataset.get("history_root") if dataset else None
    root_matches = bool(
        history_root and manifest_history_root and history_root == manifest_history_root
    )
    if history_root and manifest_history_root and not root_matches:
        causes.append("history_root_mismatch")
    if execution is None:
        causes.append("missing_execution_evidence")
    elif _int_or_none(execution.get("exit_code")) is None:
        causes.append("missing_exit_code_evidence")

    data_newest = _text(metrics.get("data_newest_session")) or None
    data_age = _int_or_none(metrics.get("data_age_days"))
    data_staleness = _text(metrics.get("data_staleness")) or None
    window_start, window_end = _eval_window(metrics.get("eval_window"))
    n_segments = _int_or_none(metrics.get("n_segments"))

    if execution is not None:
        if not metrics:
            causes.append("missing_portfolio_metrics")
        if not data_newest:
            causes.append("missing_data_newest_session")
        if data_age is None:
            causes.append("missing_data_age_days")
        if not data_staleness:
            causes.append("missing_data_staleness")
        elif data_staleness != "fresh":
            causes.append("data_staleness_not_fresh")
        if not window_start or not window_end:
            causes.append("missing_eval_window")
        if n_segments is None:
            causes.append("missing_n_segments")

    unique_causes = tuple(sorted(set(causes)))
    if any(cause in BLOCKING_CAUSES for cause in unique_causes):
        surface_status = STATUS_BLOCKED_DATA_INPUT
    elif unique_causes:
        surface_status = STATUS_WAITING_FOR_EVIDENCE
    else:
        surface_status = STATUS_PASS_DATA_READY

    return DataReadinessSurface(
        command_index=command_index,
        command_digest=_digest(command),
        portfolio_path=portfolio_path,
        history_root=history_root,
        manifest_dataset_key=dataset.get("key") if dataset else None,
        manifest_history_root=manifest_history_root,
        manifest_db_path=dataset.get("db_path") if dataset else None,
        portfolio_toml_exists=portfolio_exists,
        history_root_matches_manifest=root_matches,
        execution_exit_code=(
            _int_or_none(execution.get("exit_code")) if execution is not None else None
        ),
        data_newest_session=data_newest,
        data_age_days=data_age,
        data_staleness=data_staleness,
        eval_window_start=window_start,
        eval_window_end=window_end,
        n_segments=n_segments,
        surface_status=surface_status,
        causes=unique_causes,
        source_refs=(
            f"command:{command_index}",
            f"portfolio:{portfolio_path or 'missing'}",
            f"history-root:{history_root or 'missing'}",
        ),
    )


def _public_data_summary(text: str | None) -> dict[str, Any]:
    if text is None:
        return {"status": PUBLIC_DATA_MISSING}
    summaries = [block for block in _json_blocks(text) if "overall_ok" in block]
    summary = summaries[0] if summaries else {}
    overall_ok = summary.get("overall_ok")
    published = _int_or_none(summary.get("published"))
    total_items = _int_or_none(summary.get("total_items"))
    items = summary.get("items") if isinstance(summary.get("items"), list) else []
    issues = tuple(
        issue
        for item in items
        if isinstance(item, Mapping)
        for issue in item.get("issues", ())
        if isinstance(issue, str)
    )
    status = (
        PUBLIC_DATA_OK
        if overall_ok is True
        else PUBLIC_DATA_PARTIAL
        if published
        else STATUS_WAITING_FOR_EVIDENCE
    )
    return {
        "status": status,
        "as_of": _text(summary.get("as_of")) or None,
        "overall_ok": overall_ok,
        "published": published,
        "total_items": total_items,
        "latest_item_date": _max_text(
            _text(item.get("last_date"))
            for item in items
            if isinstance(item, Mapping)
        ),
        "issue_count": len(issues),
        "issues": list(issues[:5]),
    }


def _regime_stratify_summary(text: str | None) -> dict[str, Any]:
    if text is None:
        return {"status": REGIME_STRATIFY_MISSING}
    total_days = _max_int(
        _int_or_none(match)
        for match in re.findall(r'"total_return_days"\s*:\s*(\d+)', text)
    )
    portfolio_ids = tuple(sorted(set(re.findall(r'"portfolio_id"\s*:\s*"([^"]+)"', text))))
    return {
        "status": REGIME_STRATIFY_PRESENT if total_days else STATUS_WAITING_FOR_EVIDENCE,
        "timestamp_utc": _table_value(text, "timestamp_utc"),
        "commit": _table_value(text, "commit"),
        "total_return_days": total_days,
        "portfolio_ids": list(portfolio_ids),
    }


def _history_datasets_by_portfolio(
    manifest: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, str]]:
    if not isinstance(manifest, Mapping):
        return {}
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        return {}
    out: dict[str, Mapping[str, str]] = {}
    for item in datasets:
        if not isinstance(item, Mapping):
            continue
        portfolio = _text(item.get("portfolio_path"))
        if not portfolio:
            continue
        out[_normalize_path(portfolio)] = {
            "key": _text(item.get("key")),
            "portfolio_path": portfolio,
            "db_path": _text(item.get("db_path")),
            "history_root": _text(item.get("history_root")),
        }
    return out


def _packages(package_plan: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(package_plan, Mapping):
        return ()
    packages = package_plan.get("packages")
    if not isinstance(packages, list):
        return ()
    return tuple(item for item in packages if isinstance(item, Mapping))


def _results_by_package(
    result_evidence: Mapping[str, Any] | None,
) -> dict[tuple[str, str], Mapping[str, Any]]:
    if not isinstance(result_evidence, Mapping):
        return {}
    results = result_evidence.get("results")
    if not isinstance(results, list):
        return {}
    out: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in results:
        if isinstance(item, Mapping):
            out[_package_key(item)] = item
    return out


def _package_key(item: Mapping[str, Any]) -> tuple[str, str]:
    return (_text(item.get("candidate_id")), _text(item.get("package_id")))


def _executions(result: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(result, Mapping):
        return ()
    executions = result.get("executions")
    if not isinstance(executions, list):
        return ()
    return tuple(item for item in executions if isinstance(item, Mapping))


def _matching_execution(
    result: Mapping[str, Any] | None,
    command: str,
) -> Mapping[str, Any] | None:
    target = _command_tokens(command)
    for execution in _executions(result):
        raw_command = execution.get("command")
        if isinstance(raw_command, list):
            tokens = tuple(_text(item) for item in raw_command)
        else:
            tokens = _command_tokens(_text(raw_command))
        if tokens == target:
            return execution
    return None


def _stdout_metrics(execution: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(execution, Mapping):
        return {}
    raw = _text(execution.get("stdout_excerpt"))
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, Mapping) else {}


def _has_portfolio_surface(command: str) -> bool:
    tokens = _command_tokens(command)
    return "--portfolio" in tokens or "--history-root" in tokens


def _command_tokens(command: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(command))
    except ValueError:
        return ()


def _option_value(tokens: tuple[str, ...], option: str) -> str | None:
    try:
        index = tokens.index(option)
    except ValueError:
        return None
    value_index = index + 1
    if value_index >= len(tokens):
        return None
    return _text(tokens[value_index]) or None


def _eval_window(value: Any) -> tuple[str | None, str | None]:
    if isinstance(value, list) and len(value) >= 2:
        return _text(value[0]) or None, _text(value[1]) or None
    return None, None


def _next_action(status: str, causes: tuple[str, ...]) -> tuple[str, str]:
    if status == STATUS_PASS_DATA_READY:
        return (
            "advance_to_package_kind_expansion",
            "데이터 입력은 준비됐다. 다음에는 패키지 종류별 실패 구조를 넓혀 본다.",
        )
    if status == STATUS_BLOCKED_DATA_INPUT:
        return (
            "repair_data_input_contract",
            f"데이터 입력 문제를 먼저 고친다: {', '.join(causes)}",
        )
    return (
        "collect_missing_data_readiness_evidence",
        f"누락된 준비도 증거를 먼저 모은다: {', '.join(causes)}",
    )


def _json_blocks(text: str) -> tuple[Mapping[str, Any], ...]:
    blocks: list[Mapping[str, Any]] = []
    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, Mapping):
            blocks.append(data)
    return tuple(blocks)


def _table_value(text: str, key: str) -> str | None:
    pattern = rf"\|\s*{re.escape(key)}\s*\|\s*([^|]+?)\s*\|"
    match = re.search(pattern, text)
    return _text(match.group(1)) if match else None


def _row_sort_key(row: DataReadinessRow) -> tuple[str, str]:
    return (row.candidate_id, row.package_id)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(text: str) -> str:
    return hashlib.sha256(mask_sensitive_values(text).encode("utf-8")).hexdigest()[:16]


def _normalize_path(value: str | None) -> str:
    return str(PurePosixPath(str(value))) if value else ""


def _unique(values: Any) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if value is not None}))


def _min_text(values: Any) -> str | None:
    present = [str(value) for value in values if value]
    return min(present) if present else None


def _max_text(values: Any) -> str | None:
    present = [str(value) for value in values if value]
    return max(present) if present else None


def _max_int(values: Any) -> int | None:
    present = [int(value) for value in values if value is not None]
    return max(present) if present else None


def _table(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
