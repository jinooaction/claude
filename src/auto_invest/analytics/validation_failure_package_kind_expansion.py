"""Validation failure package-kind expansion contract.

This module turns current broad validation failures into deterministic
package-kind buckets. It does not execute validation commands. It only joins
candidate package plans and existing result evidence to separate strategy
backtest failures from portfolio backtest failures and to suggest no-live
experiment axes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from auto_invest.analytics.evolution_loop import mask_sensitive_values

SCHEMA_VERSION = "1.0"
COMPLETED_CANDIDATE_ID = (
    "candidate-broad-validation-failure-package-kind-expansion-contract"
)

STATUS_CONTRACT_READY = "CONTRACT_READY"
STATUS_WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
STATUS_READY_FOR_AXIS_EXPANSION = "READY_FOR_AXIS_EXPANSION"

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
class ExperimentAxis:
    axis_key: str
    label_ko: str
    reason_ko: str
    applies_to_package_kinds: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "axis_key": self.axis_key,
            "label_ko": self.label_ko,
            "reason_ko": self.reason_ko,
            "applies_to_package_kinds": list(self.applies_to_package_kinds),
        }


@dataclass(frozen=True)
class PackageFailureRef:
    candidate_id: str
    package_id: str
    package_kind: str
    domain_key: str | None
    title_ko: str | None
    package_status: str
    result_status: str
    diagnostic_codes: tuple[str, ...]
    next_action_codes: tuple[str, ...]
    retryable: bool
    command_count: int
    execution_count: int
    command_digests: tuple[str, ...]
    metric_highlights: Mapping[str, Any]
    text_hints: tuple[str, ...]
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "package_id": self.package_id,
            "package_kind": self.package_kind,
            "domain_key": self.domain_key,
            "title_ko": self.title_ko,
            "package_status": self.package_status,
            "result_status": self.result_status,
            "diagnostic_codes": list(self.diagnostic_codes),
            "next_action_codes": list(self.next_action_codes),
            "retryable": self.retryable,
            "command_count": self.command_count,
            "execution_count": self.execution_count,
            "command_digests": list(self.command_digests),
            "metric_highlights": _json_ready(dict(self.metric_highlights)),
            "text_hints": list(self.text_hints),
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class PackageKindBucket:
    package_kind: str
    bucket_status: str
    domain_keys: tuple[str, ...]
    package_count: int
    retryable_count: int
    command_count: int
    execution_evidence_count: int
    failure_codes: tuple[str, ...]
    result_statuses: tuple[str, ...]
    review_axes: tuple[str, ...]
    experiment_axes: tuple[ExperimentAxis, ...]
    metric_summary: Mapping[str, Any]
    package_refs: tuple[PackageFailureRef, ...]
    next_action_code: str
    next_action_ko: str
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_kind": self.package_kind,
            "bucket_status": self.bucket_status,
            "domain_keys": list(self.domain_keys),
            "package_count": self.package_count,
            "retryable_count": self.retryable_count,
            "command_count": self.command_count,
            "execution_evidence_count": self.execution_evidence_count,
            "failure_codes": list(self.failure_codes),
            "result_statuses": list(self.result_statuses),
            "review_axes": list(self.review_axes),
            "experiment_axes": [axis.to_dict() for axis in self.experiment_axes],
            "metric_summary": _json_ready(dict(self.metric_summary)),
            "package_refs": [ref.to_dict() for ref in self.package_refs],
            "next_action_code": self.next_action_code,
            "next_action_ko": self.next_action_ko,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class ValidationFailurePackageKindExpansionReport:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    package_count: int
    bucket_count: int
    retryable_count: int
    command_count: int
    execution_evidence_count: int
    buckets: tuple[PackageKindBucket, ...]
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
            "bucket_count": self.bucket_count,
            "retryable_count": self.retryable_count,
            "command_count": self.command_count,
            "execution_evidence_count": self.execution_evidence_count,
            "missing_inputs": list(self.missing_inputs),
            "safety_invariants": list(self.safety_invariants),
            "package_kind_expansion_contract": [
                bucket.to_dict() for bucket in self.buckets
            ],
        }

    def as_markdown(self) -> str:
        lines = [
            "# 검증 실패 패키지 종류별 확장 계약",
            "",
            "읽기 전용 계약입니다. 이 보고서는 검증 명령을 실행하지 않고, "
            "기존 candidate package와 result evidence만 읽어 다음 no-live "
            "후보 축을 패키지 종류별로 나눕니다.",
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
            f"| bucket_count | {self.bucket_count} |",
            f"| retryable_count | {self.retryable_count} |",
            f"| command_count | {self.command_count} |",
            f"| execution_evidence_count | {self.execution_evidence_count} |",
            "",
            "## 패키지 종류별 실패 구조",
            "",
            "| 종류 | 상태 | 패키지 | 명령 | 실행증거 | 검토 축 | 다음 행동 |",
            "|------|------|-------:|-----:|---------:|---------|-----------|",
        ]
        if not self.buckets:
            lines.append("| - | - | 0 | 0 | 0 | - | - |")
        for bucket in self.buckets:
            lines.append(
                "| "
                f"{_table(bucket.package_kind)} | "
                f"{bucket.bucket_status} | "
                f"{bucket.package_count} | "
                f"{bucket.command_count} | "
                f"{bucket.execution_evidence_count} | "
                f"{_table(', '.join(bucket.review_axes))} | "
                f"{_table(bucket.next_action_ko)} |"
            )
        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        if self.missing_inputs:
            lines += ["", "## 누락 입력", ""]
            for item in self.missing_inputs:
                lines.append(f"- `{item}`")
        return mask_sensitive_values("\n".join(lines))


def build_validation_failure_package_kind_expansion(
    *,
    package_plan: Mapping[str, Any] | None,
    result_evidence: Mapping[str, Any] | None,
    now: datetime | None = None,
    run_id: str = "local",
    commit: str = "unknown",
) -> ValidationFailurePackageKindExpansionReport:
    timestamp = _iso(now or datetime.now(UTC))
    missing_inputs: list[str] = []
    packages = _packages(package_plan)
    results = _results_by_package(result_evidence)

    if package_plan is None or not isinstance(package_plan.get("packages"), list):
        missing_inputs.append("candidate_packages.packages")
    if result_evidence is None or not isinstance(result_evidence.get("results"), list):
        missing_inputs.append("candidate_results.results")

    refs = tuple(
        sorted(
            (
                _package_ref_for_package(
                    package,
                    result=results.get(_package_key(package)),
                )
                for package in packages
            ),
            key=_ref_sort_key,
        )
    )
    buckets = _buckets_for_refs(refs)
    execution_evidence_count = sum(ref.execution_count for ref in refs)
    command_count = sum(ref.command_count for ref in refs)
    retryable_count = sum(1 for ref in refs if ref.retryable)

    if missing_inputs or not refs or any(
        bucket.bucket_status == STATUS_WAITING_FOR_EVIDENCE for bucket in buckets
    ):
        overall = STATUS_WAITING_FOR_EVIDENCE
    else:
        overall = STATUS_CONTRACT_READY

    return ValidationFailurePackageKindExpansionReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        overall_status=overall,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        package_count=len(refs),
        bucket_count=len(buckets),
        retryable_count=retryable_count,
        command_count=command_count,
        execution_evidence_count=execution_evidence_count,
        buckets=buckets,
        missing_inputs=tuple(missing_inputs),
        safety_invariants=SAFETY_INVARIANTS,
    )


def write_validation_failure_package_kind_expansion_artifacts(
    report: ValidationFailurePackageKindExpansionReport,
    *,
    summary_out: Any = None,
    json_out: Any = None,
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


def _package_ref_for_package(
    package: Mapping[str, Any],
    *,
    result: Mapping[str, Any] | None,
) -> PackageFailureRef:
    commands = tuple(
        _text(item) for item in package.get("commands") or () if _text(item)
    )
    executions = _executions(result)
    diagnostics = (*_diagnostics(package), *_diagnostics(result))
    diagnostic_codes = _unique(
        _text(item.get("code")) or "execution_failed"
        for item in diagnostics
        if isinstance(item, Mapping)
    ) or ("execution_failed",)
    next_action_codes = _unique(
        _text(action.get("action_code"))
        for item in diagnostics
        if isinstance(item, Mapping)
        for action in item.get("next_actions", ())
        if isinstance(action, Mapping)
    )
    retryable = _retryable(package, result, diagnostics)
    metric_highlights, text_hints = _metrics_and_text_hints(result)
    package_id = _text(package.get("package_id")) or "unknown"

    return PackageFailureRef(
        candidate_id=_text(package.get("candidate_id")) or "unknown",
        package_id=package_id,
        package_kind=_text(package.get("package_kind")) or "unknown",
        domain_key=_text(package.get("domain_key")) or None,
        title_ko=_text(package.get("title_ko")) or None,
        package_status=_text(package.get("status")) or "unknown",
        result_status=_text(result.get("status")) if result is not None else "missing",
        diagnostic_codes=diagnostic_codes,
        next_action_codes=next_action_codes,
        retryable=retryable,
        command_count=len(commands),
        execution_count=len(executions),
        command_digests=tuple(_digest(command) for command in commands),
        metric_highlights=metric_highlights,
        text_hints=text_hints,
        source_refs=(
            f"candidate-packages:{package_id}",
            f"candidate-result-executor:{package_id}",
        ),
    )


def _buckets_for_refs(refs: tuple[PackageFailureRef, ...]) -> tuple[PackageKindBucket, ...]:
    by_kind: dict[str, list[PackageFailureRef]] = {}
    for ref in refs:
        by_kind.setdefault(ref.package_kind, []).append(ref)

    buckets = []
    for kind, items in by_kind.items():
        ordered = tuple(sorted(items, key=_ref_sort_key))
        bucket_status = (
            STATUS_WAITING_FOR_EVIDENCE
            if any(ref.result_status == "missing" for ref in ordered)
            else STATUS_READY_FOR_AXIS_EXPANSION
        )
        axes = _review_axes(kind)
        experiment_axes = _experiment_axes(kind)
        buckets.append(
            PackageKindBucket(
                package_kind=kind,
                bucket_status=bucket_status,
                domain_keys=_unique(ref.domain_key for ref in ordered if ref.domain_key),
                package_count=len(ordered),
                retryable_count=sum(1 for ref in ordered if ref.retryable),
                command_count=sum(ref.command_count for ref in ordered),
                execution_evidence_count=sum(ref.execution_count for ref in ordered),
                failure_codes=_unique(
                    code for ref in ordered for code in ref.diagnostic_codes
                ),
                result_statuses=_unique(ref.result_status for ref in ordered),
                review_axes=axes,
                experiment_axes=experiment_axes,
                metric_summary=_bucket_metric_summary(ordered),
                package_refs=ordered,
                next_action_code="expand_no_live_axes",
                next_action_ko=_next_action_ko(kind),
                source_refs=_unique(ref.source_refs[0] for ref in ordered),
            )
        )
    return tuple(sorted(buckets, key=lambda item: item.package_kind))


def _review_axes(kind: str) -> tuple[str, ...]:
    if kind == "strategy_backtest":
        return (
            "strategy_family",
            "signal_family",
            "holding_period",
            "benchmark_comparison",
            "evidence_output",
        )
    if kind == "portfolio_backtest":
        return (
            "portfolio_design",
            "asset_universe",
            "holding_period",
            "benchmark_comparison",
            "cost_regime_robustness",
        )
    return ("package_kind", "validation_command", "evidence_output")


def _experiment_axes(kind: str) -> tuple[ExperimentAxis, ...]:
    if kind == "strategy_backtest":
        return (
            ExperimentAxis(
                "strategy_family",
                "전략군 재검토",
                "micro GTAA 실패와 장기 walk-forward 힌트를 분리해 신호군을 넓힌다.",
                (kind,),
            ),
            ExperimentAxis(
                "signal_family",
                "신호군 다변화",
                "momentum 하나에 갇히지 않도록 방어·추세·역변동성 신호를 분리한다.",
                (kind,),
            ),
            ExperimentAxis(
                "holding_period",
                "보유 기간 재검토",
                "짧은 forward 실패와 긴 OOS 힌트가 다르므로 기간 축을 분리한다.",
                (kind,),
            ),
            ExperimentAxis(
                "evidence_output",
                "산출 증거 재정렬",
                "텍스트 힌트와 기계 판독 metric을 별도 승격 증거로 구분한다.",
                (kind,),
            ),
        )
    if kind == "portfolio_backtest":
        return (
            ExperimentAxis(
                "portfolio_design",
                "포트폴리오 구성 재검토",
                "비상관 포트폴리오 후보의 자산 조합과 가중 방식을 다시 나눈다.",
                (kind,),
            ),
            ExperimentAxis(
                "asset_universe",
                "자산군 방어성 확장",
                "주식·채권·원자재·현금성 자산 조합을 같은 실패로 뭉개지 않는다.",
                (kind,),
            ),
            ExperimentAxis(
                "holding_period",
                "보유 기간 재검토",
                "3개 구간 과반 실패가 기간 선택 문제인지 분리한다.",
                (kind,),
            ),
            ExperimentAxis(
                "cost_regime_robustness",
                "비용·레짐 견고성 검토",
                "평균 샤프 열세가 비용 또는 레짐 전환에서 심해지는지 확인한다.",
                (kind,),
            ),
        )
    return (
        ExperimentAxis(
            "package_kind",
            "알 수 없는 패키지 종류 분리",
            "지원되지 않는 패키지 종류는 자동 실행하지 않고 별도 검토한다.",
            (kind,),
        ),
    )


def _next_action_ko(kind: str) -> str:
    if kind == "strategy_backtest":
        return (
            "전략군, 신호군, 보유 기간, 산출 증거를 나눠 다음 no-live 전략 "
            "후보를 설계한다."
        )
    if kind == "portfolio_backtest":
        return (
            "포트폴리오 구성, 자산군, 보유 기간, 비용·레짐 견고성을 나눠 "
            "다음 no-live 포트폴리오 후보를 설계한다."
        )
    return "알 수 없는 패키지 종류를 실행하지 않고 별도 no-live 검토 후보로 둔다."


def _bucket_metric_summary(refs: tuple[PackageFailureRef, ...]) -> dict[str, Any]:
    highlights = [dict(ref.metric_highlights) for ref in refs]
    return {
        "verdicts": _unique(
            value for item in highlights for value in _list_values(item.get("verdicts"))
        ),
        "segment_win_values": _unique(
            value
            for item in highlights
            for value in _list_values(item.get("segment_win_values"))
        ),
        "strategy_psr_values": _unique(
            value
            for item in highlights
            for value in _list_values(item.get("strategy_psr_values"))
        ),
        "strategy_dsr_values": _unique(
            value
            for item in highlights
            for value in _list_values(item.get("strategy_dsr_values"))
        ),
        "sharpe_comparisons": _unique(
            value
            for item in highlights
            for value in _list_values(item.get("sharpe_comparisons"))
        ),
        "text_hints": _unique(hint for ref in refs for hint in ref.text_hints),
    }


def _metrics_and_text_hints(
    result: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    metrics: dict[str, Any] = {}
    text_hints: list[str] = []
    if result is None:
        return metrics, ()

    metric_payloads: list[Mapping[str, Any]] = []
    raw_metrics = result.get("raw_metrics")
    if isinstance(raw_metrics, Mapping):
        metric_payloads.append(raw_metrics)

    for execution in _executions(result):
        stdout = _text(execution.get("stdout_excerpt"))
        stderr = _text(execution.get("stderr_excerpt"))
        parsed = _json_object(stdout)
        if parsed:
            metric_payloads.append(parsed)
        else:
            hint = _limited_hint(stdout)
            if hint:
                text_hints.append(hint)
        err_hint = _limited_hint(stderr)
        if err_hint and err_hint not in text_hints:
            text_hints.append(err_hint)

    subsets = [_metric_subset(payload) for payload in metric_payloads]
    metrics["verdicts"] = _unique(
        _text(item.get("verdict")) for item in subsets if item.get("verdict")
    )
    metrics["segment_win_values"] = _unique(
        _segment_win_value(item) for item in subsets
    )
    metrics["strategy_psr_values"] = _unique(
        _text(item.get("strategy_psr")) for item in subsets if item.get("strategy_psr")
    )
    metrics["strategy_dsr_values"] = _unique(
        _text(item.get("strategy_dsr")) for item in subsets if item.get("strategy_dsr")
    )
    metrics["sharpe_comparisons"] = _unique(_sharpe_comparison(item) for item in subsets)
    metrics["metric_json_count"] = len(subsets)
    return metrics, tuple(_unique(text_hints))


def _metric_subset(payload: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "segments_strategy_wins",
        "n_segments",
        "mean_strategy_sharpe",
        "mean_benchmark_sharpe",
        "strategy_psr",
        "strategy_dsr",
        "verdict",
    )
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def _segment_win_value(payload: Mapping[str, Any]) -> str:
    wins = _text(payload.get("segments_strategy_wins"))
    segments = _text(payload.get("n_segments"))
    return f"{wins}/{segments}" if wins and segments else ""


def _sharpe_comparison(payload: Mapping[str, Any]) -> str:
    strategy_sharpe = _text(payload.get("mean_strategy_sharpe"))
    benchmark_sharpe = _text(payload.get("mean_benchmark_sharpe"))
    return (
        f"{strategy_sharpe} vs {benchmark_sharpe}"
        if strategy_sharpe and benchmark_sharpe
        else ""
    )


def _list_values(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,) if value else ()


def _diagnostics(source: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if source is None:
        return ()
    diagnostics: list[Mapping[str, Any]] = []
    raw = source.get("diagnostics")
    if isinstance(raw, list):
        diagnostics.extend(item for item in raw if isinstance(item, Mapping))
    patch = source.get("promotion_patch")
    if isinstance(patch, Mapping):
        nested = patch.get("factory_diagnostics")
        if isinstance(nested, list):
            diagnostics.extend(item for item in nested if isinstance(item, Mapping))
    return tuple(diagnostics)


def _retryable(
    package: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    diagnostics: tuple[Mapping[str, Any], ...],
) -> bool:
    if result is not None and bool(result.get("retryable")):
        return True
    patch = package.get("promotion_patch")
    if isinstance(patch, Mapping) and bool(patch.get("factory_retryable")):
        return True
    return any(bool(item.get("retryable")) for item in diagnostics)


def _packages(source: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if source is None:
        return ()
    packages = source.get("packages")
    if not isinstance(packages, list):
        return ()
    return tuple(item for item in packages if isinstance(item, Mapping))


def _results_by_package(
    source: Mapping[str, Any] | None,
) -> dict[tuple[str, str], Mapping[str, Any]]:
    if source is None:
        return {}
    results = source.get("results")
    if not isinstance(results, list):
        return {}
    return {
        _package_key(result): result
        for result in results
        if isinstance(result, Mapping)
    }


def _executions(source: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if source is None:
        return ()
    executions = source.get("executions")
    if not isinstance(executions, list):
        return ()
    return tuple(item for item in executions if isinstance(item, Mapping))


def _package_key(source: Mapping[str, Any]) -> tuple[str, str]:
    return (
        _text(source.get("candidate_id")) or "unknown",
        _text(source.get("package_id")) or "unknown",
    )


def _json_object(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _limited_hint(raw: str) -> str | None:
    if not raw:
        return None
    compact = " ".join(raw.split())
    return mask_sensitive_values(compact[:220]) if compact else None


def _unique(values: Any) -> tuple[Any, ...]:
    seen = set()
    result = []
    for value in values:
        if value is None or value == "":
            continue
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return tuple(sorted(result, key=lambda item: str(item)))


def _digest(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()[:12]


def _ref_sort_key(ref: PackageFailureRef) -> tuple[str, str, str]:
    return (ref.package_kind, ref.candidate_id, ref.package_id)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else "" if value is None else str(value)


def _table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
