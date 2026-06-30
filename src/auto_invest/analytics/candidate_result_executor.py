"""스펙 071 — 후보 결과 실행기.

후보 구현 공장이 만든 검증 패키지를 안전한 실행 증거로 바꾼다. 패키지의 문자열
명령을 임의 셸로 실행하지 않고, 허용된 no-live 검증 명령만 토큰화해서 실행한다.
주문, 자본, live 설정, whitelist, caps, sentinel, 브로커 API는 건드리지 않는다.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from auto_invest.analytics.candidate_factory import (
    EVIDENCE_FAIL,
    EVIDENCE_PASS,
    EVIDENCE_PENDING,
    KIND_ANALYTICS_VALIDATION,
    KIND_DATA_COLLECTION,
    KIND_DATA_QUALITY,
    KIND_EXECUTION_QUALITY,
    KIND_GATE_ALIGNMENT,
    KIND_OPS_LIVENESS,
    KIND_PORTFOLIO_BACKTEST,
    KIND_REVIEW_LEDGER,
    KIND_STRATEGY_BACKTEST,
    SCHEMA_VERSION,
)
from auto_invest.analytics.evolution_loop import mask_sensitive_values

OVERALL_OK = "ok"
OVERALL_DEGRADED = "degraded"

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_PENDING = "pending"
STATUS_BLOCKED = "blocked"

DIAG_DATA_HISTORY_MISSING = "data_history_missing"
DIAG_COMMAND_CONTRACT_ERROR = "command_contract_error"
DIAG_INSUFFICIENT_PASS_EVIDENCE = "insufficient_pass_evidence"
DIAG_TIMEOUT = "timeout"
DIAG_UNSAFE_COMMAND = "unsafe_command"
DIAG_UNSUPPORTED_PACKAGE = "unsupported_package"
DIAG_MISSING_COMMAND = "missing_command"
DIAG_EXECUTION_FAILED = "execution_failed"
DIAG_MISSING_INPUT = "missing_input"

_STRATEGY_KINDS = {KIND_STRATEGY_BACKTEST, KIND_PORTFOLIO_BACKTEST}

_SUPPORTED_KINDS = {
    KIND_STRATEGY_BACKTEST,
    KIND_PORTFOLIO_BACKTEST,
    KIND_GATE_ALIGNMENT,
    KIND_OPS_LIVENESS,
    KIND_REVIEW_LEDGER,
    KIND_ANALYTICS_VALIDATION,
    KIND_EXECUTION_QUALITY,
    KIND_DATA_QUALITY,
    KIND_DATA_COLLECTION,
}

_ALLOWED_PREFIXES: dict[str, tuple[tuple[str, ...], ...]] = {
    KIND_STRATEGY_BACKTEST: (
        ("uv", "run", "auto-invest", "portfolio-walk-forward"),
        ("uv", "run", "python", "scripts/deep_walk_forward_probe.py"),
    ),
    KIND_PORTFOLIO_BACKTEST: (
        ("uv", "run", "auto-invest", "portfolio-walk-forward"),
    ),
    KIND_GATE_ALIGNMENT: (("uv", "run", "python", "scripts/money_path_probe.py"),),
    KIND_OPS_LIVENESS: (("uv", "run", "python", "scripts/pipeline_liveness_probe.py"),),
    KIND_REVIEW_LEDGER: (("uv", "run", "python", "scripts/evolution_loop_probe.py"),),
    KIND_ANALYTICS_VALIDATION: (("uv", "run", "auto-invest", "macro-regime"),),
    KIND_EXECUTION_QUALITY: (("uv", "run", "python", "scripts/money_path_probe.py"),),
    KIND_DATA_QUALITY: (
        ("uv", "run", "auto-invest", "bars-status"),
        ("uv", "run", "python", "scripts/pipeline_liveness_probe.py"),
    ),
    KIND_DATA_COLLECTION: (("uv", "run", "auto-invest", "collect-public-data"),),
}

_UNSAFE_FRAGMENTS = (
    "--mode live",
    "--confirm-live",
    "rebalance-live.request",
    "rebalance-micro-gtaa.request",
    "auto-invest-deploy",
    "deploy/sync-units.sh",
    "whitelist",
    "caps.toml",
    "KIS_",
    "VULTR_SSH",
    " ssh ",
    "ssh -",
)

_SUCCESS_VERDICT_MARKERS = (
    "강건한 엣지 신호",
    "ROBUST_DEFENSE_EDGE",
    "RETURN_EDGE",
    "EDGE_CONFIRMED",
)

_FAIL_VERDICT_MARKERS = (
    "강건한 엣지 없음",
    "NO_ROBUST_EDGE",
    "NO_EDGE",
)


@dataclass(frozen=True)
class CommandExecution:
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": list(self.command),
            "exit_code": self.exit_code,
            "stdout_excerpt": _excerpt(self.stdout),
            "stderr_excerpt": _excerpt(self.stderr),
            "timed_out": self.timed_out,
        }


Runner = Callable[[Sequence[str], int], CommandExecution]


@dataclass(frozen=True)
class CandidateNextAction:
    action_code: str
    summary_ko: str
    owner: str
    safe_to_auto_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_code": self.action_code,
            "summary_ko": self.summary_ko,
            "owner": self.owner,
            "safe_to_auto_run": self.safe_to_auto_run,
        }


@dataclass(frozen=True)
class CandidateEvidenceDiagnostic:
    code: str
    severity: str
    retryable: bool
    summary_ko: str
    evidence_source: str
    next_actions: tuple[CandidateNextAction, ...]
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "retryable": self.retryable,
            "summary_ko": self.summary_ko,
            "evidence_source": self.evidence_source,
            "next_actions": [action.to_dict() for action in self.next_actions],
            "details": _safe_detail(self.details),
        }


@dataclass(frozen=True)
class CandidateResultRow:
    candidate_id: str
    package_id: str
    package_kind: str
    status: str
    source_ref: str
    historical_backtest: str | None
    recent_oos: str | None
    walk_forward: str | None
    factory_validation: str | None
    block_reason_ko: str | None
    output_summary_ko: str
    raw_metrics: Mapping[str, Any]
    executions: tuple[CommandExecution, ...]
    diagnostics: tuple[CandidateEvidenceDiagnostic, ...]

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "package_id": self.package_id,
            "package_kind": self.package_kind,
            "status": self.status,
            "source_ref": self.source_ref,
            "block_reason_ko": self.block_reason_ko,
            "output_summary_ko": self.output_summary_ko,
            "raw_metrics": dict(self.raw_metrics),
            "executions": [execution.to_dict() for execution in self.executions],
        }
        if self.diagnostics:
            out["diagnostics"] = [
                diagnostic.to_dict() for diagnostic in self.diagnostics
            ]
            out["next_actions"] = [
                action.to_dict() for action in _flatten_next_actions(self.diagnostics)
            ]
            out["retryable"] = self.retryable
        if self.historical_backtest is not None:
            out["historical_backtest"] = self.historical_backtest
        if self.recent_oos is not None:
            out["recent_oos"] = self.recent_oos
        if self.walk_forward is not None:
            out["walk_forward"] = self.walk_forward
        if self.factory_validation is not None:
            out["factory_validation"] = self.factory_validation
        return out

    @property
    def retryable(self) -> bool:
        return self.status != STATUS_PASS and any(
            diagnostic.retryable for diagnostic in self.diagnostics
        )


@dataclass(frozen=True)
class CandidateResultExecutorRun:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    results: tuple[CandidateResultRow, ...]
    missing_inputs: tuple[str, ...]

    @property
    def counts(self) -> dict[str, int]:
        counts = {
            STATUS_PASS: 0,
            STATUS_FAIL: 0,
            STATUS_PENDING: 0,
            STATUS_BLOCKED: 0,
        }
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts

    @property
    def diagnostic_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.missing_inputs:
            if item:
                counts[DIAG_MISSING_INPUT] = counts.get(DIAG_MISSING_INPUT, 0) + 1
        for result in self.results:
            for diagnostic in result.diagnostics:
                counts[diagnostic.code] = counts.get(diagnostic.code, 0) + 1
        return dict(sorted(counts.items()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "counts": self.counts,
            "diagnostic_counts": self.diagnostic_counts,
            "missing_inputs": list(self.missing_inputs),
            "results": [result.to_dict() for result in self.results],
        }

    def results_document(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "results": [result.to_dict() for result in self.results],
        }

    def as_markdown(self) -> str:
        lines = [
            "# 후보 결과 실행기 최신 실행",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| schema_version | {self.schema_version} |",
            f"| run_id | {self.run_id} |",
            f"| commit | {self.commit} |",
            f"| timestamp_utc | {self.timestamp_utc} |",
            f"| overall_status | {self.overall_status} |",
            "",
            "## 한 줄 결론",
            "",
            "후보 구현 공장이 만든 검증 패키지를 안전한 실행 결과로 바꾸고, "
            "기계 판독 가능한 candidate result evidence를 발행했다.",
            "",
            "## 집계",
            "",
        ]
        for key, value in self.counts.items():
            lines.append(f"- `{key}`: {value}")
        if self.missing_inputs:
            lines += ["", "## 누락 입력", ""]
            for item in self.missing_inputs:
                lines.append(f"- `{item}`")
        if self.diagnostic_counts:
            lines += ["", "## 진단 집계", ""]
            for code, count in self.diagnostic_counts.items():
                lines.append(f"- `{code}`: {count}")
        lines += ["", "## 후보별 결과", ""]
        if not self.results:
            lines.append("- 후보 패키지 없음")
        for result in self.results:
            lines.append(
                f"- `{result.status}` {result.package_kind}: "
                f"`{result.candidate_id}` / `{result.package_id}`"
            )
            if result.block_reason_ko:
                lines.append(f"  - 사유: {result.block_reason_ko}")
            lines.append(f"  - 요약: {result.output_summary_ko}")
            if result.diagnostics:
                first = result.diagnostics[0]
                lines.append(f"  - 진단: `{first.code}` — {first.summary_ko}")
                actions = _flatten_next_actions(result.diagnostics)
                if actions:
                    lines.append(f"  - 다음 행동: {actions[0].summary_ko}")
        lines += [
            "",
            "## 안전 문구",
            "",
            "이 실행은 허용된 no-live 검증만 수행한다. 주문, 자본 사다리, "
            "live 전략 설정, whitelist, caps, 실거래 sentinel, 브로커 API를 변경하지 않는다.",
        ]
        return mask_sensitive_values("\n".join(lines))


def build_candidate_result_executor_run(
    *,
    package_plan: Mapping[str, Any] | None,
    now: datetime | None = None,
    commit: str = "unknown",
    run_id: str = "local",
    timeout_seconds: int = 120,
    runner: Runner | None = None,
) -> CandidateResultExecutorRun:
    now = _ensure_utc(now or datetime.now(UTC))
    rows = _package_rows(package_plan)
    missing_inputs: list[str] = []
    if package_plan is None or "packages" not in package_plan:
        missing_inputs.append("candidate_packages.packages")

    actual_runner = runner or _run_command
    results = tuple(
        _execute_package(row, timeout_seconds=timeout_seconds, runner=actual_runner)
        for row in rows
    )
    overall = (
        OVERALL_DEGRADED
        if missing_inputs
        or any(result.status in {STATUS_FAIL, STATUS_PENDING, STATUS_BLOCKED} for result in results)
        else OVERALL_OK
    )
    return CandidateResultExecutorRun(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=_iso(now),
        overall_status=overall,
        results=results,
        missing_inputs=tuple(missing_inputs),
    )


def write_candidate_result_artifacts(
    run: CandidateResultExecutorRun,
    *,
    summary_out: Path | None = None,
    json_out: Path | None = None,
    results_out: Path | None = None,
) -> None:
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(run.as_markdown() + "\n", encoding="utf-8")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(run.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if results_out is not None:
        results_out.parent.mkdir(parents=True, exist_ok=True)
        results_out.write_text(
            json.dumps(run.results_document(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _execute_package(
    package: Mapping[str, Any],
    *,
    timeout_seconds: int,
    runner: Runner,
) -> CandidateResultRow:
    candidate_id = str(package.get("candidate_id") or "").strip()
    package_id = str(package.get("package_id") or "").strip()
    kind = str(package.get("package_kind") or "").strip()
    source_ref = f"candidate-result-executor:{package_id or 'unknown'}"
    commands = tuple(str(item) for item in package.get("commands") or () if str(item).strip())

    if not candidate_id or not package_id:
        return _blocked_result(
            candidate_id=candidate_id or "unknown",
            package_id=package_id or "unknown",
            kind=kind or "unknown",
            source_ref=source_ref,
            reason="candidate_id 또는 package_id가 없어 실행할 수 없다.",
        )
    if kind not in _SUPPORTED_KINDS:
        return _blocked_result(
            candidate_id=candidate_id,
            package_id=package_id,
            kind=kind or "unknown",
            source_ref=source_ref,
            reason=f"지원하지 않는 패키지 종류({kind})라 자동 실행하지 않는다.",
        )
    if str(package.get("status") or "") == STATUS_BLOCKED:
        return _blocked_result(
            candidate_id=candidate_id,
            package_id=package_id,
            kind=kind,
            source_ref=source_ref,
            reason="후보 구현 공장에서 이미 blocked 상태로 표시한 패키지다.",
        )
    unsafe_reason = _unsafe_reason(kind, commands)
    if unsafe_reason:
        return _blocked_result(
            candidate_id=candidate_id,
            package_id=package_id,
            kind=kind,
            source_ref=source_ref,
            reason=unsafe_reason,
        )

    executions: list[CommandExecution] = []
    for command in commands:
        tokens = tuple(shlex.split(command))
        executions.append(runner(tokens, timeout_seconds))

    if kind in _STRATEGY_KINDS:
        status, evidence_status, reason, summary, metrics, diagnostics = _strategy_result(
            executions
        )
        return CandidateResultRow(
            candidate_id=candidate_id,
            package_id=package_id,
            package_kind=kind,
            status=status,
            source_ref=source_ref,
            historical_backtest=evidence_status,
            recent_oos=evidence_status,
            walk_forward=evidence_status,
            factory_validation=None,
            block_reason_ko=reason,
            output_summary_ko=summary,
            raw_metrics=metrics,
            executions=tuple(executions),
            diagnostics=diagnostics,
        )

    status, validation, reason, summary, metrics, diagnostics = _non_strategy_result(
        executions
    )
    return CandidateResultRow(
        candidate_id=candidate_id,
        package_id=package_id,
        package_kind=kind,
        status=status,
        source_ref=source_ref,
        historical_backtest=None,
        recent_oos=None,
        walk_forward=None,
        factory_validation=validation,
        block_reason_ko=reason,
        output_summary_ko=summary,
        raw_metrics=metrics,
        executions=tuple(executions),
        diagnostics=diagnostics,
    )


def _blocked_result(
    *,
    candidate_id: str,
    package_id: str,
    kind: str,
    source_ref: str,
    reason: str,
) -> CandidateResultRow:
    return CandidateResultRow(
        candidate_id=candidate_id,
        package_id=package_id,
        package_kind=kind,
        status=STATUS_BLOCKED,
        source_ref=source_ref,
        historical_backtest=None,
        recent_oos=None,
        walk_forward=None,
        factory_validation=None,
        block_reason_ko=reason,
        output_summary_ko="안전 또는 지원 범위 밖이라 실행하지 않았다.",
        raw_metrics={},
        executions=(),
        diagnostics=(_blocked_diagnostic(kind=kind, reason=reason),),
    )


def _strategy_result(
    executions: Sequence[CommandExecution],
) -> tuple[
    str,
    str,
    str | None,
    str,
    Mapping[str, Any],
    tuple[CandidateEvidenceDiagnostic, ...],
]:
    if not executions:
        diagnostics = (_diagnostic(DIAG_MISSING_COMMAND, evidence_source="package"),)
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "실행할 검증 명령이 없다.",
            "검증 명령 부재로 보류했다.",
            {},
            diagnostics,
        )
    if any(execution.timed_out for execution in executions):
        diagnostics = _diagnostics_from_executions(executions)
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "검증 명령이 시간 초과됐다.",
            "시간 초과로 증거를 확정하지 못했다.",
            _execution_metrics(executions),
            diagnostics,
        )
    if all(execution.exit_code != 0 for execution in executions):
        diagnostics = _diagnostics_from_executions(executions)
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "검증 명령이 실행됐지만 데이터 또는 환경 부족으로 실패했다.",
            "명령 실패를 통과로 보지 않고 보류했다.",
            _execution_metrics(executions),
            diagnostics,
        )

    combined = "\n".join(f"{execution.stdout}\n{execution.stderr}" for execution in executions)
    metrics = _extract_json_metrics(executions) or _execution_metrics(executions)
    verdict_text = _verdict_text(metrics, combined)
    if _has_verdict_marker(verdict_text, _SUCCESS_VERDICT_MARKERS):
        return (
            STATUS_PASS,
            EVIDENCE_PASS,
            None,
            "전략 검증 출력이 강건한 엣지 기준을 통과했다.",
            metrics,
            (),
        )
    if _has_verdict_marker(verdict_text, _FAIL_VERDICT_MARKERS):
        return (
            STATUS_FAIL,
            EVIDENCE_FAIL,
            "전략 검증 출력이 엣지 없음 또는 실패를 보고했다.",
            "검증 결과가 전략 엣지 실패를 보고했다.",
            metrics,
            (),
        )
    if _numeric_dsr_pass(metrics):
        return (
            STATUS_PASS,
            EVIDENCE_PASS,
            None,
            "전략 검증의 디플레이티드 샤프가 통과 기준을 넘었다.",
            metrics,
            (),
        )
    diagnostics = _dedupe_diagnostics(
        _diagnostics_from_executions(executions)
        + (_diagnostic(DIAG_INSUFFICIENT_PASS_EVIDENCE, evidence_source="output"),)
    )
    return (
        STATUS_PENDING,
        EVIDENCE_PENDING,
        "검증 출력이 충분한 통과 증거를 제공하지 않았다.",
        "실행은 됐지만 승격용 통과 증거로는 부족하다.",
        metrics,
        diagnostics,
    )


def _non_strategy_result(
    executions: Sequence[CommandExecution],
) -> tuple[
    str,
    str,
    str | None,
    str,
    Mapping[str, Any],
    tuple[CandidateEvidenceDiagnostic, ...],
]:
    if not executions:
        diagnostics = (_diagnostic(DIAG_MISSING_COMMAND, evidence_source="package"),)
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "실행할 검증 명령이 없다.",
            "검증 명령 부재로 보류했다.",
            {},
            diagnostics,
        )
    if any(execution.timed_out for execution in executions):
        diagnostics = _diagnostics_from_executions(executions)
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "검증 명령이 시간 초과됐다.",
            "시간 초과로 factory validation을 확정하지 못했다.",
            _execution_metrics(executions),
            diagnostics,
        )
    if any(execution.exit_code != 0 for execution in executions):
        diagnostics = _diagnostics_from_executions(executions)
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "no-live 검증 명령이 비정상 종료했다.",
            "검증 명령 실패를 통과로 보지 않고 보류했다.",
            _execution_metrics(executions),
            diagnostics,
        )
    return (
        STATUS_PASS,
        EVIDENCE_PASS,
        None,
        "no-live 검증 명령이 정상 종료했다.",
        _extract_json_metrics(executions) or _execution_metrics(executions),
        (),
    )


def _unsafe_reason(kind: str, commands: Sequence[str]) -> str | None:
    if not commands:
        return "패키지에 실행 명령이 없다."
    allowed = _ALLOWED_PREFIXES.get(kind, ())
    for command in commands:
        padded = f" {command} "
        for fragment in _UNSAFE_FRAGMENTS:
            if fragment in command or fragment in padded:
                return f"안전하지 않은 명령 조각({fragment.strip()})이 포함되어 실행하지 않는다."
        try:
            tokens = tuple(shlex.split(command))
        except ValueError as exc:
            return f"명령을 안전하게 토큰화할 수 없다: {exc}"
        if not any(tokens[: len(prefix)] == prefix for prefix in allowed):
            return f"허용되지 않은 명령 표면이다: {tokens[:4]}"
    return None


def _run_command(tokens: Sequence[str], timeout_seconds: int) -> CommandExecution:
    try:
        completed = subprocess.run(
            list(tokens),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandExecution(
            command=tuple(tokens),
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandExecution(
            command=tuple(tokens),
            exit_code=124,
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr if isinstance(exc.stderr, str) else "",
            timed_out=True,
        )
    except OSError as exc:
        return CommandExecution(
            command=tuple(tokens),
            exit_code=127,
            stdout="",
            stderr=str(exc),
        )


def _package_rows(package_plan: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(package_plan, Mapping) or not isinstance(package_plan.get("packages"), list):
        return ()
    return tuple(item for item in package_plan["packages"] if isinstance(item, Mapping))


def _extract_json_metrics(executions: Sequence[CommandExecution]) -> Mapping[str, Any] | None:
    for execution in executions:
        for text in (execution.stdout, execution.stderr):
            parsed = _try_json(text)
            if parsed is not None:
                return parsed
    return None


def _try_json(text: str) -> Mapping[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _verdict_text(metrics: Mapping[str, Any], combined: str) -> str:
    verdict = metrics.get("verdict")
    if verdict is not None:
        return str(verdict)
    champion = metrics.get("champion")
    if isinstance(champion, Mapping):
        champ_verdict = champion.get("verdict")
        if champ_verdict is not None:
            return str(champ_verdict)
    return combined


def _has_verdict_marker(text: str, markers: Sequence[str]) -> bool:
    folded = text.upper()
    return any(marker in text or marker.upper() in folded for marker in markers)


def _numeric_dsr_pass(metrics: Mapping[str, Any]) -> bool:
    raw = metrics.get("strategy_dsr")
    if raw is None:
        return False
    try:
        return Decimal(str(raw)) >= Decimal("0.95")
    except (InvalidOperation, ValueError):
        return False


def _diagnostics_from_executions(
    executions: Sequence[CommandExecution],
) -> tuple[CandidateEvidenceDiagnostic, ...]:
    diagnostics: list[CandidateEvidenceDiagnostic] = []
    for execution in executions:
        if execution.timed_out:
            diagnostics.append(
                _diagnostic(
                    DIAG_TIMEOUT,
                    evidence_source="command",
                    details=_execution_details(execution),
                )
            )
            continue
        if execution.exit_code == 0:
            continue
        text = f"{execution.stdout}\n{execution.stderr}".lower()
        if "no ingested datasets" in text or "ingest-history" in text:
            code = DIAG_DATA_HISTORY_MISSING
        elif (
            "usage:" in text
            or "the following arguments are required" in text
            or "unrecognized arguments" in text
            or "가 필요" in text
        ):
            code = DIAG_COMMAND_CONTRACT_ERROR
        else:
            code = DIAG_EXECUTION_FAILED
        diagnostics.append(
            _diagnostic(
                code,
                evidence_source="command",
                details=_execution_details(execution),
            )
        )
    if not diagnostics and executions:
        return ()
    return _dedupe_diagnostics(tuple(diagnostics))


def _blocked_diagnostic(*, kind: str, reason: str) -> CandidateEvidenceDiagnostic:
    lowered = reason.lower()
    if "지원하지 않는 패키지" in reason:
        code = DIAG_UNSUPPORTED_PACKAGE
    elif "실행 명령이 없다" in reason:
        code = DIAG_MISSING_COMMAND
    elif "안전하지 않은" in reason or "허용되지 않은" in reason:
        code = DIAG_UNSAFE_COMMAND
    else:
        code = DIAG_EXECUTION_FAILED
    return _diagnostic(
        code,
        evidence_source="package",
        details={"package_kind": kind, "reason": lowered or reason},
    )


def _diagnostic(
    code: str,
    *,
    evidence_source: str,
    details: Mapping[str, Any] | None = None,
) -> CandidateEvidenceDiagnostic:
    action = _next_action_for(code)
    retryable = code in {
        DIAG_DATA_HISTORY_MISSING,
        DIAG_TIMEOUT,
        DIAG_EXECUTION_FAILED,
        DIAG_MISSING_INPUT,
    }
    severity = "blocked" if code in {
        DIAG_UNSAFE_COMMAND,
        DIAG_UNSUPPORTED_PACKAGE,
        DIAG_MISSING_COMMAND,
    } else "warning"
    summaries = {
        DIAG_DATA_HISTORY_MISSING: "과거 가격 데이터가 준비되지 않았다.",
        DIAG_COMMAND_CONTRACT_ERROR: "검증 명령 계약에 필요한 입력이 빠져 있다.",
        DIAG_INSUFFICIENT_PASS_EVIDENCE: "실행 출력에 통과 verdict가 충분히 없다.",
        DIAG_TIMEOUT: "검증 명령이 제한 시간 안에 끝나지 않았다.",
        DIAG_UNSAFE_COMMAND: "자동 실행 안전 범위 밖의 명령이다.",
        DIAG_UNSUPPORTED_PACKAGE: "지원하지 않는 후보 패키지 종류다.",
        DIAG_MISSING_COMMAND: "패키지에 실행 가능한 검증 명령이 없다.",
        DIAG_EXECUTION_FAILED: "검증 명령이 비정상 종료했다.",
        DIAG_MISSING_INPUT: "필수 입력 sidecar 또는 JSON이 없다.",
    }
    return CandidateEvidenceDiagnostic(
        code=code,
        severity=severity,
        retryable=retryable,
        summary_ko=summaries.get(code, "검증 결과를 확정할 수 없다."),
        evidence_source=evidence_source,
        next_actions=(action,),
        details=dict(details or {}),
    )


def _next_action_for(code: str) -> CandidateNextAction:
    actions = {
        DIAG_DATA_HISTORY_MISSING: CandidateNextAction(
            action_code="prepare_history_dataset",
            summary_ko="안전한 데이터 수집 또는 ingest-history 실행 경로를 준비한다.",
            owner="automation",
            safe_to_auto_run=True,
        ),
        DIAG_COMMAND_CONTRACT_ERROR: CandidateNextAction(
            action_code="repair_candidate_package_command",
            summary_ko="후보 공장의 no-live 검증 명령 인자 계약을 보정한다.",
            owner="candidate_factory",
            safe_to_auto_run=False,
        ),
        DIAG_INSUFFICIENT_PASS_EVIDENCE: CandidateNextAction(
            action_code="emit_machine_readable_verdict",
            summary_ko="검증 명령이 명확한 pass/fail verdict와 핵심 통계를 내도록 보강한다.",
            owner="future_spec",
            safe_to_auto_run=False,
        ),
        DIAG_TIMEOUT: CandidateNextAction(
            action_code="bound_or_extend_validation_runtime",
            summary_ko="검증 범위를 줄이거나 별도 시간 예산이 있는 검증 경로로 분리한다.",
            owner="candidate_factory",
            safe_to_auto_run=False,
        ),
        DIAG_UNSAFE_COMMAND: CandidateNextAction(
            action_code="remove_unsafe_command_surface",
            summary_ko="live, broker, SSH, 자본, whitelist/caps, sentinel 표면을 제거한다.",
            owner="operator",
            safe_to_auto_run=False,
        ),
        DIAG_UNSUPPORTED_PACKAGE: CandidateNextAction(
            action_code="add_package_kind_contract",
            summary_ko="새 package kind의 no-live 검증 계약과 allowlist를 별도 스펙으로 정의한다.",
            owner="future_spec",
            safe_to_auto_run=False,
        ),
        DIAG_MISSING_COMMAND: CandidateNextAction(
            action_code="add_no_live_validation_command",
            summary_ko="후보 패키지에 안전한 no-live 검증 명령을 추가한다.",
            owner="candidate_factory",
            safe_to_auto_run=False,
        ),
        DIAG_EXECUTION_FAILED: CandidateNextAction(
            action_code="inspect_validation_failure",
            summary_ko="종료 코드와 제한된 출력을 바탕으로 실패 원인을 더 좁힌다.",
            owner="automation",
            safe_to_auto_run=True,
        ),
        DIAG_MISSING_INPUT: CandidateNextAction(
            action_code="restore_candidate_package_sidecar",
            summary_ko="후보 패키지 sidecar 수집 경로와 JSON 형식을 복구한다.",
            owner="automation",
            safe_to_auto_run=True,
        ),
    }
    return actions.get(code, actions[DIAG_EXECUTION_FAILED])


def _execution_details(execution: CommandExecution) -> dict[str, Any]:
    return {
        "command": list(execution.command),
        "exit_code": execution.exit_code,
        "stderr_excerpt": _excerpt(execution.stderr, limit=400),
        "stdout_excerpt": _excerpt(execution.stdout, limit=400),
        "timed_out": execution.timed_out,
    }


def _dedupe_diagnostics(
    diagnostics: Sequence[CandidateEvidenceDiagnostic],
) -> tuple[CandidateEvidenceDiagnostic, ...]:
    seen: set[str] = set()
    out: list[CandidateEvidenceDiagnostic] = []
    for diagnostic in diagnostics:
        if diagnostic.code in seen:
            continue
        seen.add(diagnostic.code)
        out.append(diagnostic)
    return tuple(out)


def _flatten_next_actions(
    diagnostics: Sequence[CandidateEvidenceDiagnostic],
) -> tuple[CandidateNextAction, ...]:
    seen: set[str] = set()
    actions: list[CandidateNextAction] = []
    for diagnostic in diagnostics:
        for action in diagnostic.next_actions:
            if action.action_code in seen:
                continue
            seen.add(action.action_code)
            actions.append(action)
    return tuple(actions)


def _safe_detail(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _safe_detail(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_safe_detail(item) for item in value]
    if isinstance(value, str):
        return mask_sensitive_values(value)
    return value


def _execution_metrics(executions: Sequence[CommandExecution]) -> dict[str, Any]:
    return {
        "executions": [execution.to_dict() for execution in executions],
    }


def _excerpt(text: str, limit: int = 1000) -> str:
    clean = mask_sensitive_values(text.strip())
    return clean[:limit]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _ensure_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "CandidateResultExecutorRun",
    "CandidateResultRow",
    "CandidateEvidenceDiagnostic",
    "CandidateNextAction",
    "CommandExecution",
    "DIAG_COMMAND_CONTRACT_ERROR",
    "DIAG_DATA_HISTORY_MISSING",
    "DIAG_EXECUTION_FAILED",
    "DIAG_INSUFFICIENT_PASS_EVIDENCE",
    "DIAG_MISSING_COMMAND",
    "DIAG_MISSING_INPUT",
    "DIAG_TIMEOUT",
    "DIAG_UNSAFE_COMMAND",
    "DIAG_UNSUPPORTED_PACKAGE",
    "OVERALL_DEGRADED",
    "OVERALL_OK",
    "STATUS_BLOCKED",
    "STATUS_FAIL",
    "STATUS_PASS",
    "STATUS_PENDING",
    "build_candidate_result_executor_run",
    "write_candidate_result_artifacts",
]
