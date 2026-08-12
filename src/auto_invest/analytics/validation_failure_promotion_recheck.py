"""Validation failure promotion recheck contract.

This module decides when rejected validation-failure candidates can be
reconsidered. It never runs validation commands. It only reads existing
learning-ledger, autonomous-promotion, and candidate-result evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from auto_invest.analytics.evolution_loop import mask_sensitive_values

SCHEMA_VERSION = "1.0"
COMPLETED_CANDIDATE_ID = (
    "candidate-broad-validation-failure-promotion-recheck-contract"
)

STATUS_CONTRACT_READY = "CONTRACT_READY"
STATUS_WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
STATUS_SUPPRESSION_ACTIVE = "SUPPRESSION_ACTIVE"
STATUS_RECHECK_ALLOWED = "RECHECK_ALLOWED"

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

_FAILED_RESULT_STATUSES = {
    "blocked",
    "discard",
    "discarded",
    "fail",
    "failed",
    "reject",
    "rejected",
}
_PASS_RESULT_STATUSES = {"complete", "completed", "ok", "pass", "passed", "success"}
_REJECTED_LEDGER_DECISIONS = {"discard", "discarded", "reject", "rejected"}


@dataclass(frozen=True)
class RecheckCondition:
    condition_key: str
    label_ko: str
    description_ko: str
    is_currently_met: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_key": self.condition_key,
            "label_ko": self.label_ko,
            "description_ko": self.description_ko,
            "is_currently_met": self.is_currently_met,
        }


@dataclass(frozen=True)
class CandidateRecheckRule:
    candidate_id: str
    decision_status: str
    ledger_decision: str
    ledger_entry_id: str | None
    ledger_evidence_package_id: str | None
    ledger_recheck_condition: str | None
    historical_recheck_conditions: tuple[str, ...]
    promotion_stage: str
    promotion_source_status: str
    promotion_package_id: str | None
    promotion_package_kind: str | None
    promotion_retryable: bool
    promotion_blocked_reason_ko: str | None
    result_status: str
    validation_layers: Mapping[str, str]
    metric_highlights: Mapping[str, Any]
    failure_fingerprint: str
    recheck_conditions: tuple[RecheckCondition, ...]
    missing_evidence: tuple[str, ...]
    next_action_code: str
    next_action_ko: str
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision_status": self.decision_status,
            "ledger_decision": self.ledger_decision,
            "ledger_entry_id": self.ledger_entry_id,
            "ledger_evidence_package_id": self.ledger_evidence_package_id,
            "ledger_recheck_condition": self.ledger_recheck_condition,
            "historical_recheck_conditions": list(
                self.historical_recheck_conditions
            ),
            "promotion_stage": self.promotion_stage,
            "promotion_source_status": self.promotion_source_status,
            "promotion_package_id": self.promotion_package_id,
            "promotion_package_kind": self.promotion_package_kind,
            "promotion_retryable": self.promotion_retryable,
            "promotion_blocked_reason_ko": self.promotion_blocked_reason_ko,
            "result_status": self.result_status,
            "validation_layers": dict(self.validation_layers),
            "metric_highlights": _json_ready(dict(self.metric_highlights)),
            "failure_fingerprint": self.failure_fingerprint,
            "recheck_conditions": [
                condition.to_dict() for condition in self.recheck_conditions
            ],
            "missing_evidence": list(self.missing_evidence),
            "next_action_code": self.next_action_code,
            "next_action_ko": self.next_action_ko,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class ValidationFailurePromotionRecheckReport:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    candidate_count: int
    suppressed_count: int
    allowed_recheck_count: int
    waiting_count: int
    candidate_rules: tuple[CandidateRecheckRule, ...]
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
            "candidate_count": self.candidate_count,
            "suppressed_count": self.suppressed_count,
            "allowed_recheck_count": self.allowed_recheck_count,
            "waiting_count": self.waiting_count,
            "missing_inputs": list(self.missing_inputs),
            "safety_invariants": list(self.safety_invariants),
            "promotion_recheck_contract": [
                rule.to_dict() for rule in self.candidate_rules
            ],
        }

    def as_markdown(self) -> str:
        lines = [
            "# 검증 실패 승격 재검토 계약",
            "",
            "읽기 전용 계약입니다. 이 보고서는 learning ledger, "
            "autonomous-promotion, candidate-result evidence만 읽어 억제된 "
            "후보를 언제 다시 열 수 있는지 결정합니다.",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| schema_version | {self.schema_version} |",
            f"| run_id | {self.run_id} |",
            f"| commit | {self.commit} |",
            f"| timestamp_utc | {self.timestamp_utc} |",
            f"| overall_status | {self.overall_status} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| candidate_count | {self.candidate_count} |",
            f"| suppressed_count | {self.suppressed_count} |",
            f"| allowed_recheck_count | {self.allowed_recheck_count} |",
            f"| waiting_count | {self.waiting_count} |",
            "",
            "## 후보별 재검토 상태",
            "",
            "| 후보 | 상태 | ledger | promotion | result | package | fingerprint | 다음 행동 |",
            "|------|------|--------|-----------|--------|---------|-------------|-----------|",
        ]
        if not self.candidate_rules:
            lines.append("| - | - | - | - | - | - | - | - |")
        for rule in self.candidate_rules:
            package = rule.promotion_package_id or "-"
            if rule.promotion_package_kind:
                package = f"{package} / {rule.promotion_package_kind}"
            lines.append(
                "| "
                f"{_table(rule.candidate_id)} | "
                f"{rule.decision_status} | "
                f"{_table(rule.ledger_decision)} | "
                f"{_table(rule.promotion_stage)} | "
                f"{_table(rule.result_status)} | "
                f"{_table(package)} | "
                f"{rule.failure_fingerprint} | "
                f"{_table(rule.next_action_ko)} |"
            )
        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        if self.missing_inputs:
            lines += ["", "## 누락 입력", ""]
            for item in self.missing_inputs:
                lines.append(f"- `{item}`")
        return mask_sensitive_values("\n".join(lines))


def build_validation_failure_promotion_recheck(
    *,
    learning_ledger: Mapping[str, Any] | None,
    promotion_summary: Mapping[str, Any] | None,
    result_evidence: Mapping[str, Any] | None,
    now: datetime | None = None,
    run_id: str = "local",
    commit: str = "unknown",
) -> ValidationFailurePromotionRecheckReport:
    timestamp = _iso(now or datetime.now(UTC))
    missing_inputs: list[str] = []
    if learning_ledger is None or not isinstance(learning_ledger.get("entries"), list):
        missing_inputs.append("learning_ledger.entries")
    if promotion_summary is None or not isinstance(
        promotion_summary.get("assessments"), list
    ):
        missing_inputs.append("promotion_summary.assessments")
    if result_evidence is None or not isinstance(result_evidence.get("results"), list):
        missing_inputs.append("candidate_results.results")

    ledger_entries = _ledger_entries_by_candidate(learning_ledger)
    promotion_assessments = _promotion_assessments_by_candidate(promotion_summary)
    results = _results_by_candidate(result_evidence)
    candidate_ids = _target_candidate_ids(
        ledger_entries=ledger_entries,
        promotion_assessments=promotion_assessments,
        results=results,
    )
    rules = tuple(
        _rule_for_candidate(
            candidate_id,
            ledger_entries=ledger_entries.get(candidate_id, ()),
            promotion=promotion_assessments.get(candidate_id),
            result=results.get(candidate_id),
        )
        for candidate_id in candidate_ids
    )
    suppressed_count = sum(
        rule.decision_status == STATUS_SUPPRESSION_ACTIVE for rule in rules
    )
    allowed_count = sum(rule.decision_status == STATUS_RECHECK_ALLOWED for rule in rules)
    waiting_count = sum(
        rule.decision_status == STATUS_WAITING_FOR_EVIDENCE for rule in rules
    )
    overall_status = (
        STATUS_WAITING_FOR_EVIDENCE
        if missing_inputs or not rules or waiting_count == len(rules)
        else STATUS_CONTRACT_READY
    )
    return ValidationFailurePromotionRecheckReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        overall_status=overall_status,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        candidate_count=len(rules),
        suppressed_count=suppressed_count,
        allowed_recheck_count=allowed_count,
        waiting_count=waiting_count,
        candidate_rules=rules,
        missing_inputs=tuple(missing_inputs),
        safety_invariants=SAFETY_INVARIANTS,
    )


def write_validation_failure_promotion_recheck_artifacts(
    report: ValidationFailurePromotionRecheckReport,
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


def _rule_for_candidate(
    candidate_id: str,
    *,
    ledger_entries: tuple[Mapping[str, Any], ...],
    promotion: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
) -> CandidateRecheckRule:
    latest_ledger = ledger_entries[-1] if ledger_entries else None
    candidate = promotion.get("candidate") if isinstance(promotion, Mapping) else None
    candidate = candidate if isinstance(candidate, Mapping) else {}
    promotion_evidence = candidate.get("promotion_evidence")
    promotion_evidence = (
        promotion_evidence if isinstance(promotion_evidence, Mapping) else {}
    )

    missing = _candidate_missing_evidence(latest_ledger, promotion, result)
    conditions = _recheck_conditions(
        latest_ledger=latest_ledger,
        promotion=promotion,
        candidate=candidate,
        result=result,
    )
    if missing:
        decision_status = STATUS_WAITING_FOR_EVIDENCE
        next_action_code = "collect_missing_evidence"
        next_action_ko = "누락된 sidecar 증거를 먼저 확보한 뒤 재검토 조건을 판정한다."
    elif any(condition.is_currently_met for condition in conditions):
        decision_status = STATUS_RECHECK_ALLOWED
        next_action_code = "allow_recheck"
        next_action_ko = (
            "현재 증거가 이전 실패 지문과 달라졌으므로 no-live 재검토 후보로 "
            "되살릴 수 있다."
        )
    else:
        decision_status = STATUS_SUPPRESSION_ACTIVE
        next_action_code = "keep_suppression"
        next_action_ko = (
            "같은 실패 지문과 폐기 결정이 유지되므로 자동 재활성화하지 않는다. "
            "아래 재검토 조건 중 하나가 충족될 때만 다시 연다."
        )

    historical_conditions = _historical_recheck_conditions(ledger_entries)
    layers = _validation_layers(result)
    metrics = _metric_highlights(result)
    fingerprint = _failure_fingerprint(
        candidate_id,
        latest_ledger=latest_ledger,
        promotion=promotion,
        result=result,
        metric_highlights=metrics,
    )
    return CandidateRecheckRule(
        candidate_id=candidate_id,
        decision_status=decision_status,
        ledger_decision=_text(latest_ledger.get("decision")) if latest_ledger else "missing",
        ledger_entry_id=_text(latest_ledger.get("entry_id")) if latest_ledger else None,
        ledger_evidence_package_id=(
            _text(latest_ledger.get("evidence_package_id")) if latest_ledger else None
        ),
        ledger_recheck_condition=(
            _text(latest_ledger.get("next_recheck_condition"))
            if latest_ledger
            else None
        ),
        historical_recheck_conditions=historical_conditions,
        promotion_stage=_text(promotion.get("stage")) if promotion else "missing",
        promotion_source_status=_text(candidate.get("source_status")) or "missing",
        promotion_package_id=_text(promotion_evidence.get("factory_package_id")) or None,
        promotion_package_kind=_text(promotion_evidence.get("factory_kind")) or None,
        promotion_retryable=_bool(promotion_evidence.get("factory_retryable")),
        promotion_blocked_reason_ko=(
            _text(promotion.get("blocked_reason_ko")) if promotion else None
        ),
        result_status=_text(result.get("status")) if result else "missing",
        validation_layers=layers,
        metric_highlights=metrics,
        failure_fingerprint=fingerprint,
        recheck_conditions=conditions,
        missing_evidence=missing,
        next_action_code=next_action_code,
        next_action_ko=next_action_ko,
        source_refs=_source_refs(candidate_id, promotion_evidence, result),
    )


def _recheck_conditions(
    *,
    latest_ledger: Mapping[str, Any] | None,
    promotion: Mapping[str, Any] | None,
    candidate: Mapping[str, Any],
    result: Mapping[str, Any] | None,
) -> tuple[RecheckCondition, ...]:
    ledger_condition = (
        _text(latest_ledger.get("next_recheck_condition")) if latest_ledger else ""
    )
    promotion_stage = _text(promotion.get("stage")).upper() if promotion else ""
    source_status = _text(candidate.get("source_status")).lower()
    return (
        RecheckCondition(
            "candidate_result_not_failed",
            "candidate-result 실패 해소",
            "candidate-result status가 fail/blocked/rejected 계열이 아니어야 한다.",
            _result_not_failed(result),
        ),
        RecheckCondition(
            "validation_layers_not_all_failed",
            "검증 단계 실패 해소",
            "historical_backtest, recent_oos, walk_forward가 모두 실패인 상태에서 벗어나야 한다.",
            _validation_layers_not_all_failed(result),
        ),
        RecheckCondition(
            "promotion_not_discard",
            "승격 평가 DISCARD 해소",
            (
                "autonomous-promotion stage가 DISCARD가 아니고 "
                "source_status가 rejected가 아니어야 한다."
            ),
            (
                bool(promotion)
                and promotion_stage != "DISCARD"
                and source_status != "rejected"
            ),
        ),
        RecheckCondition(
            "latest_ledger_recheck_condition_present",
            "최신 장부 재검토 조건 존재",
            "latest learning-ledger entry에 next_recheck_condition이 명시되어야 한다.",
            bool(ledger_condition),
        ),
        RecheckCondition(
            "failure_fingerprint_changed",
            "실패 지문 변화",
            (
                "package id, package kind, promotion diagnostics, result layers, "
                "metrics, execution digests 중 하나가 이 계약의 fingerprint와 "
                "달라져야 한다."
            ),
            False,
        ),
    )


def _candidate_missing_evidence(
    latest_ledger: Mapping[str, Any] | None,
    promotion: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    missing = []
    if latest_ledger is None:
        missing.append("learning-ledger")
    if promotion is None:
        missing.append("autonomous-promotion")
    if result is None:
        missing.append("candidate-result-executor")
    return tuple(missing)


def _target_candidate_ids(
    *,
    ledger_entries: Mapping[str, tuple[Mapping[str, Any], ...]],
    promotion_assessments: Mapping[str, Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    ids: set[str] = set()
    for candidate_id, entries in ledger_entries.items():
        if entries and _text(entries[-1].get("decision")).lower() in _REJECTED_LEDGER_DECISIONS:
            ids.add(candidate_id)
    for candidate_id, assessment in promotion_assessments.items():
        candidate = assessment.get("candidate")
        candidate = candidate if isinstance(candidate, Mapping) else {}
        stage = _text(assessment.get("stage")).upper()
        source_status = _text(candidate.get("source_status")).lower()
        if stage == "DISCARD" and source_status == "rejected":
            ids.add(candidate_id)
    for candidate_id, result in results.items():
        if (
            _text(result.get("status")).lower() in _FAILED_RESULT_STATUSES
            and (candidate_id in ledger_entries or candidate_id in promotion_assessments)
        ):
            ids.add(candidate_id)
    return tuple(sorted(ids))


def _ledger_entries_by_candidate(
    ledger: Mapping[str, Any] | None,
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    by_candidate: dict[str, list[Mapping[str, Any]]] = {}
    if not isinstance(ledger, Mapping):
        return {}
    raw_entries = ledger.get("entries")
    if not isinstance(raw_entries, list):
        return {}
    for item in raw_entries:
        if not isinstance(item, Mapping):
            continue
        candidate_id = _text(item.get("candidate_id"))
        if not candidate_id:
            continue
        by_candidate.setdefault(candidate_id, []).append(item)
    return {
        candidate_id: tuple(sorted(items, key=_ledger_sort_key))
        for candidate_id, items in by_candidate.items()
    }


def _promotion_assessments_by_candidate(
    promotion_summary: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    assessments: dict[str, Mapping[str, Any]] = {}
    if not isinstance(promotion_summary, Mapping):
        return assessments
    raw_assessments = promotion_summary.get("assessments")
    if not isinstance(raw_assessments, list):
        return assessments
    for item in raw_assessments:
        if not isinstance(item, Mapping):
            continue
        candidate_id = _text(item.get("candidate_id"))
        if not candidate_id:
            candidate = item.get("candidate")
            if isinstance(candidate, Mapping):
                candidate_id = _text(candidate.get("candidate_id"))
        if candidate_id:
            assessments[candidate_id] = item
    return assessments


def _results_by_candidate(
    result_evidence: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    results: dict[str, Mapping[str, Any]] = {}
    if not isinstance(result_evidence, Mapping):
        return results
    raw_results = result_evidence.get("results")
    if not isinstance(raw_results, list):
        return results
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue
        candidate_id = _text(item.get("candidate_id"))
        if candidate_id:
            results[candidate_id] = item
    return results


def _ledger_sort_key(item: Mapping[str, Any]) -> tuple[str, str]:
    return (_text(item.get("created_at_utc")), _text(item.get("entry_id")))


def _historical_recheck_conditions(
    entries: Iterable[Mapping[str, Any]],
) -> tuple[str, ...]:
    return _unique(_text(item.get("next_recheck_condition")) for item in entries)


def _validation_layers(result: Mapping[str, Any] | None) -> dict[str, str]:
    if result is None:
        return {}
    return {
        "historical_backtest": _text(result.get("historical_backtest")) or "missing",
        "recent_oos": _text(result.get("recent_oos")) or "missing",
        "walk_forward": _text(result.get("walk_forward")) or "missing",
    }


def _result_not_failed(result: Mapping[str, Any] | None) -> bool:
    if result is None:
        return False
    status = _text(result.get("status")).lower()
    return bool(status) and status not in _FAILED_RESULT_STATUSES


def _validation_layers_not_all_failed(result: Mapping[str, Any] | None) -> bool:
    if result is None:
        return False
    layers = _validation_layers(result)
    values = tuple(value.lower() for value in layers.values() if value != "missing")
    if not values:
        return False
    if all(value in _FAILED_RESULT_STATUSES for value in values):
        return False
    return any(value in _PASS_RESULT_STATUSES for value in values)


def _metric_highlights(result: Mapping[str, Any] | None) -> dict[str, Any]:
    if result is None:
        return {}
    raw_metrics = result.get("raw_metrics")
    raw_metrics = raw_metrics if isinstance(raw_metrics, Mapping) else {}
    keys = (
        "dataset_version",
        "eval_window",
        "segments_strategy_wins",
        "n_segments",
        "mean_strategy_sharpe",
        "mean_benchmark_sharpe",
        "strategy_psr",
        "strategy_dsr",
        "verdict",
    )
    return {key: raw_metrics.get(key) for key in keys if raw_metrics.get(key) is not None}


def _failure_fingerprint(
    candidate_id: str,
    *,
    latest_ledger: Mapping[str, Any] | None,
    promotion: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
    metric_highlights: Mapping[str, Any],
) -> str:
    candidate = promotion.get("candidate") if isinstance(promotion, Mapping) else None
    candidate = candidate if isinstance(candidate, Mapping) else {}
    promotion_evidence = candidate.get("promotion_evidence")
    promotion_evidence = (
        promotion_evidence if isinstance(promotion_evidence, Mapping) else {}
    )
    payload = {
        "candidate_id": candidate_id,
        "ledger_decision": _text(latest_ledger.get("decision"))
        if latest_ledger
        else "missing",
        "ledger_recheck_condition": _text(
            latest_ledger.get("next_recheck_condition")
        )
        if latest_ledger
        else "",
        "promotion_stage": _text(promotion.get("stage")) if promotion else "missing",
        "promotion_source_status": _text(candidate.get("source_status")),
        "promotion_package_id": _text(promotion_evidence.get("factory_package_id")),
        "promotion_package_kind": _text(promotion_evidence.get("factory_kind")),
        "promotion_status": _text(promotion_evidence.get("factory_status")),
        "promotion_diagnostic_codes": _promotion_diagnostic_codes(promotion_evidence),
        "result_package_id": _text(result.get("package_id")) if result else "missing",
        "result_package_kind": _text(result.get("package_kind")) if result else "missing",
        "result_status": _text(result.get("status")) if result else "missing",
        "validation_layers": _validation_layers(result),
        "metric_highlights": _json_ready(dict(metric_highlights)),
        "execution_digests": _execution_digests(result),
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _promotion_diagnostic_codes(evidence: Mapping[str, Any]) -> tuple[str, ...]:
    diagnostics = evidence.get("factory_diagnostics")
    if not isinstance(diagnostics, list):
        return ()
    return _unique(
        _text(item.get("code"))
        for item in diagnostics
        if isinstance(item, Mapping)
    )


def _execution_digests(result: Mapping[str, Any] | None) -> tuple[str, ...]:
    if result is None:
        return ()
    executions = result.get("executions")
    if not isinstance(executions, list):
        return ()
    digests = []
    for execution in executions:
        if not isinstance(execution, Mapping):
            continue
        payload = {
            "command": execution.get("command"),
            "exit_code": execution.get("exit_code"),
            "timed_out": execution.get("timed_out"),
            "stdout_digest": _digest(_text(execution.get("stdout_excerpt"))),
            "stderr_digest": _digest(_text(execution.get("stderr_excerpt"))),
        }
        digests.append(_digest(json.dumps(_json_ready(payload), sort_keys=True)))
    return tuple(sorted(digests))


def _source_refs(
    candidate_id: str,
    promotion_evidence: Mapping[str, Any],
    result: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    package_id = _text(promotion_evidence.get("factory_package_id"))
    if not package_id and result is not None:
        package_id = _text(result.get("package_id"))
    refs = [
        f"learning-ledger:{candidate_id}",
        f"autonomous-promotion:{candidate_id}",
    ]
    if package_id:
        refs.append(f"candidate-result-executor:{package_id}")
    else:
        refs.append(f"candidate-result-executor:{candidate_id}")
    return tuple(refs)


def _unique(values: Iterable[Any]) -> tuple[Any, ...]:
    seen: set[Any] = set()
    output: list[Any] = []
    for value in values:
        if value in (None, "") or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(val) for key, val in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_ready(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _table(value: Any) -> str:
    return _text(value).replace("|", "\\|").replace("\n", " ")


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
