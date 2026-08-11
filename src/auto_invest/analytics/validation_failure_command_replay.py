"""Validation failure command replay contract.

This module turns blocked candidate validation packages into a deterministic
no-live replay contract. It does not execute commands. It only joins the
candidate package plan with result evidence and records whether each validation
command is replay-safe, what exit/output evidence is already available, and what
diagnostic action should happen next.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.candidate_result_executor import (
    DIAG_EXECUTION_FAILED,
    STATUS_BLOCKED,
    validation_command_safety_reason,
)
from auto_invest.analytics.evolution_loop import mask_sensitive_values

SCHEMA_VERSION = "1.0"
COMPLETED_CANDIDATE_ID = "candidate-broad-validation-failure-command-replay-contract"

STATUS_CONTRACT_READY = "CONTRACT_READY"
STATUS_WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
STATUS_BLOCKED_UNSAFE_COMMAND = "BLOCKED_UNSAFE_COMMAND"

EXIT_EVIDENCE_PRESENT = "present"
EXIT_EVIDENCE_MISSING = "missing_execution_evidence"

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
class CommandReplayRow:
    candidate_id: str
    package_id: str
    package_kind: str
    package_title_ko: str | None
    command_index: int
    command: str
    command_digest: str
    safe_to_replay: bool
    replay_scope: str
    safety_reason_ko: str
    result_status: str | None
    observed_exit_code: int | None
    exit_code_evidence_status: str
    stdout_excerpt: str
    stderr_excerpt: str
    output_digest: str | None
    diagnostic_codes: tuple[str, ...]
    retryable: bool
    next_action_code: str | None
    next_action_ko: str
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "package_id": self.package_id,
            "package_kind": self.package_kind,
            "package_title_ko": self.package_title_ko,
            "command_index": self.command_index,
            "command": self.command,
            "command_digest": self.command_digest,
            "safe_to_replay": self.safe_to_replay,
            "replay_scope": self.replay_scope,
            "safety_reason_ko": self.safety_reason_ko,
            "result_status": self.result_status,
            "observed_exit_code": self.observed_exit_code,
            "exit_code_evidence_status": self.exit_code_evidence_status,
            "stdout_excerpt": self.stdout_excerpt,
            "stderr_excerpt": self.stderr_excerpt,
            "output_digest": self.output_digest,
            "diagnostic_codes": list(self.diagnostic_codes),
            "retryable": self.retryable,
            "next_action_code": self.next_action_code,
            "next_action_ko": self.next_action_ko,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class ValidationFailureCommandReplayReport:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    command_count: int
    package_count: int
    replay_safe_count: int
    missing_execution_count: int
    unsafe_command_count: int
    rows: tuple[CommandReplayRow, ...]
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
            "command_count": self.command_count,
            "package_count": self.package_count,
            "replay_safe_count": self.replay_safe_count,
            "missing_execution_count": self.missing_execution_count,
            "unsafe_command_count": self.unsafe_command_count,
            "missing_inputs": list(self.missing_inputs),
            "safety_invariants": list(self.safety_invariants),
            "command_replay_contract": [row.to_dict() for row in self.rows],
        }

    def as_markdown(self) -> str:
        lines = [
            "# 검증 실패 명령 재현 계약",
            "",
            "읽기 전용 계약입니다. 이 보고서는 명령을 실행하지 않고, "
            "검증 실패 패키지의 명령·안전 재현 범위·기존 실행 증거를 정리합니다.",
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
            f"| command_count | {self.command_count} |",
            f"| replay_safe_count | {self.replay_safe_count} |",
            f"| missing_execution_count | {self.missing_execution_count} |",
            f"| unsafe_command_count | {self.unsafe_command_count} |",
            "",
            "## 명령별 계약",
            "",
            "| 후보 | 패키지 | 명령 | 안전 재현 | 종료 코드 증거 | 다음 행동 |",
            "|------|--------|-----:|-----------|----------------|-----------|",
        ]
        if not self.rows:
            lines.append("| - | - | - | - | - | - |")
        for row in self.rows:
            exit_value = (
                str(row.observed_exit_code)
                if row.observed_exit_code is not None
                else row.exit_code_evidence_status
            )
            lines.append(
                "| "
                f"`{row.candidate_id}` | "
                f"`{row.package_id}` | "
                f"{row.command_index} | "
                f"{'yes' if row.safe_to_replay else 'no'} | "
                f"{exit_value} | "
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


def build_validation_failure_command_replay(
    *,
    package_plan: Mapping[str, Any] | None,
    result_evidence: Mapping[str, Any] | None,
    now: datetime | None = None,
    run_id: str = "local",
    commit: str = "unknown",
) -> ValidationFailureCommandReplayReport:
    timestamp = _iso(now or datetime.now(UTC))
    missing_inputs: list[str] = []
    packages = _packages(package_plan)
    results = _results_by_package(result_evidence)
    if package_plan is None or not isinstance(package_plan.get("packages"), list):
        missing_inputs.append("candidate_packages.packages")
    if result_evidence is None or not isinstance(result_evidence.get("results"), list):
        missing_inputs.append("candidate_results.results")

    rows = tuple(
        row
        for package in packages
        if _is_replay_target(package, results.get(_package_key(package)))
        for row in _rows_for_package(package, results.get(_package_key(package)))
    )
    package_count = len({row.package_id for row in rows})
    safe_count = sum(row.safe_to_replay for row in rows)
    missing_execution_count = sum(
        row.exit_code_evidence_status == EXIT_EVIDENCE_MISSING for row in rows
    )
    unsafe_count = sum(not row.safe_to_replay for row in rows)
    if not rows or missing_inputs:
        overall = STATUS_WAITING_FOR_INPUT
    elif unsafe_count:
        overall = STATUS_BLOCKED_UNSAFE_COMMAND
    else:
        overall = STATUS_CONTRACT_READY

    return ValidationFailureCommandReplayReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        overall_status=overall,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        command_count=len(rows),
        package_count=package_count,
        replay_safe_count=safe_count,
        missing_execution_count=missing_execution_count,
        unsafe_command_count=unsafe_count,
        rows=tuple(sorted(rows, key=_row_sort_key)),
        missing_inputs=tuple(missing_inputs),
        safety_invariants=SAFETY_INVARIANTS,
    )


def write_validation_failure_command_replay_artifacts(
    report: ValidationFailureCommandReplayReport,
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


def _rows_for_package(
    package: Mapping[str, Any],
    result: Mapping[str, Any] | None,
) -> tuple[CommandReplayRow, ...]:
    kind = _text(package.get("package_kind"))
    commands = tuple(
        _text(item) for item in package.get("commands") or () if _text(item)
    )
    rows: list[CommandReplayRow] = []
    for index, command in enumerate(commands, start=1):
        safety_reason = validation_command_safety_reason(kind, (command,))
        execution = _matching_execution(result, command)
        diagnostics = _diagnostic_codes(result, package)
        next_action_code, next_action_ko = _next_action(result, package)
        stdout = _text(execution.get("stdout_excerpt")) if execution else ""
        stderr = _text(execution.get("stderr_excerpt")) if execution else ""
        observed_exit = _int_or_none(execution.get("exit_code")) if execution else None
        rows.append(
            CommandReplayRow(
                candidate_id=_text(package.get("candidate_id")) or "unknown",
                package_id=_text(package.get("package_id")) or "unknown",
                package_kind=kind or "unknown",
                package_title_ko=_text(package.get("title_ko")) or None,
                command_index=index,
                command=command,
                command_digest=_digest(command),
                safe_to_replay=safety_reason is None,
                replay_scope=(
                    "allowlisted_no_live_validation"
                    if safety_reason is None
                    else "blocked"
                ),
                safety_reason_ko=safety_reason or "허용된 no-live 검증 명령 표면이다.",
                result_status=_text(result.get("status")) if result else None,
                observed_exit_code=observed_exit,
                exit_code_evidence_status=(
                    EXIT_EVIDENCE_PRESENT
                    if observed_exit is not None
                    else EXIT_EVIDENCE_MISSING
                ),
                stdout_excerpt=_excerpt(stdout),
                stderr_excerpt=_excerpt(stderr),
                output_digest=(
                    _digest(f"{observed_exit}\n{stdout}\n{stderr}")
                    if observed_exit is not None or stdout or stderr
                    else None
                ),
                diagnostic_codes=diagnostics,
                retryable=_retryable(result, package),
                next_action_code=next_action_code,
                next_action_ko=next_action_ko,
                source_refs=(
                    f"candidate-packages:{_text(package.get('package_id')) or 'unknown'}",
                    f"candidate-result-executor:{_text(package.get('package_id')) or 'unknown'}",
                ),
            )
        )
    return tuple(rows)


def _is_replay_target(
    package: Mapping[str, Any],
    result: Mapping[str, Any] | None,
) -> bool:
    codes = _diagnostic_codes(result, package)
    retryable = _retryable(result, package)
    return bool(
        (DIAG_EXECUTION_FAILED in codes and retryable)
        or (_text(package.get("status")).lower() == STATUS_BLOCKED and retryable)
    )


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


def _matching_execution(
    result: Mapping[str, Any] | None,
    command: str,
) -> Mapping[str, Any] | None:
    if not isinstance(result, Mapping):
        return None
    executions = result.get("executions")
    if not isinstance(executions, list):
        return None
    target = _command_tokens(command)
    for execution in executions:
        if not isinstance(execution, Mapping):
            continue
        raw_command = execution.get("command")
        if isinstance(raw_command, list):
            tokens = tuple(_text(item) for item in raw_command)
        else:
            tokens = _command_tokens(_text(raw_command))
        if tokens == target:
            return execution
    return None


def _diagnostic_codes(
    result: Mapping[str, Any] | None,
    package: Mapping[str, Any],
) -> tuple[str, ...]:
    codes: list[str] = []
    for item in _diagnostics(result):
        code = _text(item.get("code"))
        if code:
            codes.append(code)
    patch = package.get("promotion_patch")
    if isinstance(patch, Mapping):
        for item in _diagnostics(patch, key="factory_diagnostics"):
            code = _text(item.get("code"))
            if code:
                codes.append(code)
    return tuple(sorted(set(codes)))


def _diagnostics(
    doc: Mapping[str, Any] | None,
    *,
    key: str = "diagnostics",
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(doc, Mapping):
        return ()
    diagnostics = doc.get(key)
    if not isinstance(diagnostics, list):
        return ()
    return tuple(item for item in diagnostics if isinstance(item, Mapping))


def _next_action(
    result: Mapping[str, Any] | None,
    package: Mapping[str, Any],
) -> tuple[str | None, str]:
    sources = (
        (result, "next_actions"),
        (package.get("promotion_patch"), "factory_next_actions"),
    )
    for container, key in sources:
        if not isinstance(container, Mapping):
            continue
        actions = container.get(key)
        if not isinstance(actions, list):
            continue
        for action in actions:
            if not isinstance(action, Mapping):
                continue
            code = _text(action.get("action_code")) or None
            summary = _text(action.get("summary_ko"))
            if code or summary:
                return code, summary or "다음 안전 진단 action을 확인한다."
    return (
        "inspect_validation_failure",
        "종료 코드와 제한된 출력을 바탕으로 실패 원인을 더 좁힌다.",
    )


def _retryable(result: Mapping[str, Any] | None, package: Mapping[str, Any]) -> bool:
    if isinstance(result, Mapping) and result.get("retryable") is True:
        return True
    for diagnostic in _diagnostics(result):
        if diagnostic.get("retryable") is True:
            return True
    patch = package.get("promotion_patch")
    if isinstance(patch, Mapping):
        if patch.get("factory_retryable") is True:
            return True
        for diagnostic in _diagnostics(patch, key="factory_diagnostics"):
            if diagnostic.get("retryable") is True:
                return True
    return False


def _command_tokens(command: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(command))
    except ValueError:
        return ()


def _row_sort_key(row: CommandReplayRow) -> tuple[str, str, int]:
    return (row.candidate_id, row.package_id, row.command_index)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(text: str) -> str:
    return hashlib.sha256(_redact_text(text).encode("utf-8")).hexdigest()[:16]


def _excerpt(text: str, *, limit: int = 240) -> str:
    cleaned = " ".join(_redact_text(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _redact_text(text: str) -> str:
    masked = mask_sensitive_values(text)
    masked = re.sub(
        r"(?i)(['\"]?\b(?:access_token|app_key|app_secret|token)\b['\"]?\s*[:=]\s*)"
        r"['\"]?[^,'\"\s)}\]]+['\"]?",
        r'\1"[REDACTED]"',
        masked,
    )
    return masked


def _table(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
