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
    KIND_DATA_QUALITY: (("uv", "run", "auto-invest", "bars-status"),),
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
        if self.historical_backtest is not None:
            out["historical_backtest"] = self.historical_backtest
        if self.recent_oos is not None:
            out["recent_oos"] = self.recent_oos
        if self.walk_forward is not None:
            out["walk_forward"] = self.walk_forward
        if self.factory_validation is not None:
            out["factory_validation"] = self.factory_validation
        return out


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "counts": self.counts,
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
        status, evidence_status, reason, summary, metrics = _strategy_result(executions)
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
        )

    status, validation, reason, summary, metrics = _non_strategy_result(executions)
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
    )


def _strategy_result(
    executions: Sequence[CommandExecution],
) -> tuple[str, str, str | None, str, Mapping[str, Any]]:
    if not executions:
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "실행할 검증 명령이 없다.",
            "검증 명령 부재로 보류했다.",
            {},
        )
    if any(execution.timed_out for execution in executions):
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "검증 명령이 시간 초과됐다.",
            "시간 초과로 증거를 확정하지 못했다.",
            _execution_metrics(executions),
        )
    if all(execution.exit_code != 0 for execution in executions):
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "검증 명령이 실행됐지만 데이터 또는 환경 부족으로 실패했다.",
            "명령 실패를 통과로 보지 않고 보류했다.",
            _execution_metrics(executions),
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
        )
    if _has_verdict_marker(verdict_text, _FAIL_VERDICT_MARKERS):
        return (
            STATUS_FAIL,
            EVIDENCE_FAIL,
            "전략 검증 출력이 엣지 없음 또는 실패를 보고했다.",
            "검증 결과가 전략 엣지 실패를 보고했다.",
            metrics,
        )
    if _numeric_dsr_pass(metrics):
        return (
            STATUS_PASS,
            EVIDENCE_PASS,
            None,
            "전략 검증의 디플레이티드 샤프가 통과 기준을 넘었다.",
            metrics,
        )
    return (
        STATUS_PENDING,
        EVIDENCE_PENDING,
        "검증 출력이 충분한 통과 증거를 제공하지 않았다.",
        "실행은 됐지만 승격용 통과 증거로는 부족하다.",
        metrics,
    )


def _non_strategy_result(
    executions: Sequence[CommandExecution],
) -> tuple[str, str, str | None, str, Mapping[str, Any]]:
    if not executions:
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "실행할 검증 명령이 없다.",
            "검증 명령 부재로 보류했다.",
            {},
        )
    if any(execution.timed_out for execution in executions):
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "검증 명령이 시간 초과됐다.",
            "시간 초과로 factory validation을 확정하지 못했다.",
            _execution_metrics(executions),
        )
    if any(execution.exit_code != 0 for execution in executions):
        return (
            STATUS_PENDING,
            EVIDENCE_PENDING,
            "no-live 검증 명령이 비정상 종료했다.",
            "검증 명령 실패를 통과로 보지 않고 보류했다.",
            _execution_metrics(executions),
        )
    return (
        STATUS_PASS,
        EVIDENCE_PASS,
        None,
        "no-live 검증 명령이 정상 종료했다.",
        _extract_json_metrics(executions) or _execution_metrics(executions),
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
    "CommandExecution",
    "OVERALL_DEGRADED",
    "OVERALL_OK",
    "STATUS_BLOCKED",
    "STATUS_FAIL",
    "STATUS_PASS",
    "STATUS_PENDING",
    "build_candidate_result_executor_run",
    "write_candidate_result_artifacts",
]
