"""스펙 103 — 브로커 거부 분류 계약.

이미 발행된 sidecar 스냅샷만 읽어 브로커 거부 코드, KIS smoke, micro GTAA
live intent gate를 하나의 읽기 전용 taxonomy 보고서로 묶는다. 브로커 API,
주문, 자본 배분, live 설정, whitelist/caps, 비밀값, 헌법/커널, 외부 유료
서비스는 건드리지 않는다.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

CONTRACT_READY = "CONTRACT_READY"
OBSERVATION_WAIT = "OBSERVATION_WAIT"
BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_PRESENT = "present"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

GATE_PASS = "PASS"
GATE_WAIT = "WAIT"
GATE_FAIL = "FAIL"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"

RECURRENCE_RECURRENT = "OBSERVED_RECURRENT"
RECURRENCE_SINGLE = "OBSERVED_SINGLE"
RECURRENCE_UNKNOWN = "UNKNOWN"

ACTION_NO_AUTO_RETRY = "NO_AUTO_RETRY"
ACTION_OBSERVE = "OBSERVE"
ACTION_REPAIR_EVIDENCE = "REPAIR_EVIDENCE"

COMPLETED_CANDIDATE_ID = "candidate-broker-rejection-taxonomy-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "candidate-execution-cost-basis-contract"

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("execution-quality", "automation/execution-quality-last-run:LAST_RUN.md"),
    ("kis-smoke", "automation/kis-smoke-last-run:LAST_RUN.md"),
    ("rebalance-micro-gtaa", "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run:LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
    (
        "capital-path-readiness",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
    ),
)

_REPO_SIDECAR_PATHS: Mapping[str, str] = {
    "execution-quality": "automation/execution-quality-last-run/LAST_RUN.md",
    "kis-smoke": "automation/kis-smoke-last-run/LAST_RUN.md",
    "rebalance-micro-gtaa": "automation/rebalance-micro-gtaa-last-run/LAST_RUN.md",
    "pipeline-liveness": "automation/pipeline-liveness-last-run/LAST_RUN.md",
    "released-work": "automation/released-work-last-run/released_work.json",
    "capital-path-readiness": (
        "automation/capital-path-readiness-last-run/capital_path_readiness.json"
    ),
}

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no constitution/kernel modification",
    "no fresh external collection",
    "no external paid service",
    "read-only broker rejection taxonomy contract only",
)

_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(?P<body>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_JSON_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)
_RELEASED_STATUSES = {"released", "release", "complete", "completed", "done"}


@dataclass(frozen=True)
class EvidenceSurface:
    """보고서가 소비한 sidecar 입력 하나."""

    key: str
    source_ref: str
    present: bool
    parse_status: str
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source_ref": self.source_ref,
            "present": self.present,
            "parse_status": self.parse_status,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class QualityGate:
    """분류 계약 조건 하나의 판정."""

    gate_id: str
    status: str
    summary_ko: str
    evidence_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "summary_ko": self.summary_ko,
            "evidence_keys": list(self.evidence_keys),
        }


@dataclass(frozen=True)
class BrokerRejectionClass:
    """관측된 브로커 거부 signature의 안정 분류."""

    signature: str
    taxonomy_key: str
    label_ko: str
    count: int
    confidence: str
    recurrence_risk: str
    action_category: str
    reason_ko: str
    next_action_ko: str
    evidence_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature": self.signature,
            "taxonomy_key": self.taxonomy_key,
            "label_ko": self.label_ko,
            "count": self.count,
            "confidence": self.confidence,
            "recurrence_risk": self.recurrence_risk,
            "action_category": self.action_category,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "evidence_keys": list(self.evidence_keys),
        }


@dataclass(frozen=True)
class BrokerRejectionTaxonomyReport:
    """브로커 거부 분류 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    rejection_summary: dict[str, Any]
    taxonomy: tuple[BrokerRejectionClass, ...]
    live_intent_context: dict[str, Any]
    broker_smoke_summary: dict[str, Any]
    quality_gates: tuple[QualityGate, ...]
    released_work_summary: dict[str, Any]
    capital_path_summary: dict[str, Any]
    safety_invariants: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "completed_candidate_id": self.completed_candidate_id,
            "next_candidate_id": self.next_candidate_id,
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "rejection_summary": self.rejection_summary,
            "taxonomy": [entry.to_dict() for entry in self.taxonomy],
            "live_intent_context": self.live_intent_context,
            "broker_smoke_summary": self.broker_smoke_summary,
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "capital_path_summary": self.capital_path_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 브로커 거부 분류 계약 (as of {self.timestamp_utc})",
            "",
            (
                "기존 sidecar 스냅샷만 읽는 보고입니다. 주문, 자본 배분, live 설정, "
                "브로커 재시도는 하지 않습니다."
            ),
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| next_candidate_id | {self.next_candidate_id} |",
        ]

        lines += ["", "## 검증 게이트", ""]
        lines += ["| 게이트 | 상태 | 요약 |", "|--------|------|------|"]
        for gate in self.quality_gates:
            lines.append(
                f"| {_table(gate.gate_id)} | {gate.status} | {_table(gate.summary_ko)} |"
            )

        lines += ["", "## 브로커 거부 분류", ""]
        if self.taxonomy:
            lines += [
                "| signature | 분류 | 건수 | 신뢰도 | 재발 위험 | 행동 | 이유 |",
                "|-----------|------|-----:|--------|-----------|------|------|",
            ]
            for entry in self.taxonomy:
                lines.append(
                    f"| {_table(entry.signature)} | {_table(entry.taxonomy_key)} | "
                    f"{entry.count} | {entry.confidence} | {entry.recurrence_risk} | "
                    f"{entry.action_category} | {_table(entry.reason_ko)} |"
                )
        else:
            lines.append("- 분류할 브로커 거부 signature가 없습니다.")

        lines += [
            "",
            "## 라이브 의도 게이트",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
        ]
        for key in (
            "present",
            "gate_ok",
            "reason",
            "verdict",
            "latest_signal",
            "blocks_live_orders",
        ):
            lines.append(f"| {key} | {_table(self.live_intent_context.get(key))} |")

        lines += ["", "## 입력 증거", ""]
        lines += ["| 입력 | 파싱 | 출처 | 요약 |", "|------|------|------|------|"]
        for surface in self.evidence_surfaces:
            lines.append(
                f"| {_table(surface.key)} | {surface.parse_status} | "
                f"{_table(surface.source_ref)} | {_table(surface.summary_ko)} |"
            )

        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)


def build_broker_rejection_taxonomy_report(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> BrokerRejectionTaxonomyReport:
    """수집된 sidecar 원문으로 브로커 거부 taxonomy 계약을 만든다."""

    now = _as_utc(now)
    parsed = {key: _parse_for_key(key, evidence_texts.get(key)) for key, _ in REQUIRED_INPUTS}
    surfaces = tuple(
        _surface_for(key, source_ref, evidence_texts.get(key), parsed[key])
        for key, source_ref in REQUIRED_INPUTS
    )
    execution_doc = parsed["execution-quality"]
    rejection_summary = _rejection_summary(execution_doc)
    live_context = _live_intent_context(
        execution_doc,
        parsed["rebalance-micro-gtaa"],
    )
    smoke_summary = _broker_smoke_summary(execution_doc, parsed["kis-smoke"])
    taxonomy = _taxonomy(
        rejection_summary,
        smoke_summary=smoke_summary,
        live_context=live_context,
    )
    gates = (
        _required_evidence_gate(surfaces),
        _broker_rejection_evidence_gate(rejection_summary),
        _taxonomy_gate(taxonomy),
        _kis_smoke_gate(smoke_summary),
        _live_intent_gate(live_context),
        _safety_boundary_gate(),
    )

    return BrokerRejectionTaxonomyReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=_overall_status(gates),
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_AUTONOMOUS_CANDIDATE_ID,
        evidence_surfaces=surfaces,
        rejection_summary=rejection_summary,
        taxonomy=taxonomy,
        live_intent_context=live_context,
        broker_smoke_summary=smoke_summary,
        quality_gates=gates,
        released_work_summary=_released_work_summary(parsed["released-work"]),
        capital_path_summary=_capital_path_summary(parsed["capital-path-readiness"]),
        safety_invariants=SAFETY_INVARIANTS,
    )


def read_evidence_manifest(manifest_path: Path, *, repo_root: Path) -> dict[str, str | None]:
    """탭 구분 manifest를 읽어 probe 입력 원문을 만든다."""

    evidence: dict[str, str | None] = {key: None for key, _ in REQUIRED_INPUTS}
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"manifest line must be key<TAB>branch<TAB>path: {raw_line}")
        key, branch, path = parts
        if key not in evidence:
            raise ValueError(f"unknown manifest key: {key}")
        local_path = repo_root / branch / path
        evidence[key] = local_path.read_text(encoding="utf-8") if local_path.exists() else None
    return evidence


def read_repo_sidecars(repo_root: Path) -> dict[str, str | None]:
    """저장소 checkout 안에 존재하는 automation sidecar 파일을 읽는다."""

    return {
        key: _read_optional(repo_root / path)
        for key, path in _REPO_SIDECAR_PATHS.items()
    }


def _parse_for_key(key: str, raw: str | None) -> Any:
    if raw is None:
        return None
    if key == "kis-smoke":
        return _kis_smoke_markdown(raw) or _parse_markdown_json(raw)
    if key == "rebalance-micro-gtaa":
        return _json_after_marker(raw, "## 라이브 전 전략 의도 게이트") or _parse_markdown_json(raw)
    if key in {"execution-quality", "pipeline-liveness"}:
        return _parse_markdown_json(raw)
    return _parse_json(raw)


def _surface_for(
    key: str,
    source_ref: str,
    raw: str | None,
    parsed: Any,
) -> EvidenceSurface:
    if raw is None:
        return EvidenceSurface(key, source_ref, False, PARSE_MISSING, "sidecar 파일 없음")
    if parsed is None:
        return EvidenceSurface(
            key,
            source_ref,
            True,
            PARSE_MALFORMED,
            "원문은 있으나 구조화 파싱 실패",
        )
    return EvidenceSurface(
        key,
        source_ref,
        True,
        PARSE_OK if isinstance(parsed, (dict, list)) else PARSE_PRESENT,
        _summary_for(key, parsed),
    )


def _rejection_summary(execution_doc: Any) -> dict[str, Any]:
    rejections = _mapping_value(execution_doc, "broker_rejections")
    if not isinstance(rejections, Mapping):
        return {
            "parseable": False,
            "rejected_orders": 0,
            "parsed_broker_errors": 0,
            "unparsed_reasons": 0,
            "broker_error_observation_rate": None,
            "kis_msg_codes": {},
            "exception_types": {},
            "http_statuses": {},
        }
    rejected = _int(rejections.get("rejected_orders"), 0)
    parsed = _int(rejections.get("parsed_broker_errors"), 0)
    return {
        "parseable": True,
        "rejected_orders": rejected,
        "parsed_broker_errors": parsed,
        "unparsed_reasons": _int(rejections.get("unparsed_reasons"), 0),
        "broker_error_observation_rate": _float_or_none(
            rejections.get("broker_error_observation_rate")
        ),
        "kis_msg_codes": _count_dict(rejections.get("kis_msg_codes")),
        "exception_types": _count_dict(rejections.get("exception_types")),
        "http_statuses": _count_dict(rejections.get("http_statuses")),
    }


def _taxonomy(
    rejection_summary: Mapping[str, Any],
    *,
    smoke_summary: Mapping[str, Any],
    live_context: Mapping[str, Any],
) -> tuple[BrokerRejectionClass, ...]:
    codes = rejection_summary.get("kis_msg_codes")
    if not isinstance(codes, Mapping):
        return ()
    rows = [
        _taxonomy_row(
            signature=str(code),
            count=_int(count, 0),
            rejection_summary=rejection_summary,
            smoke_summary=smoke_summary,
            live_context=live_context,
        )
        for code, count in sorted(codes.items())
        if _int(count, 0) > 0
    ]
    if rows:
        return tuple(rows)
    exceptions = rejection_summary.get("exception_types")
    if not isinstance(exceptions, Mapping):
        return ()
    return tuple(
        _unknown_row(
            signature=f"exception:{exception}",
            count=_int(count, 0),
            live_context=live_context,
        )
        for exception, count in sorted(exceptions.items())
        if _int(count, 0) > 0
    )


def _taxonomy_row(
    *,
    signature: str,
    count: int,
    rejection_summary: Mapping[str, Any],
    smoke_summary: Mapping[str, Any],
    live_context: Mapping[str, Any],
) -> BrokerRejectionClass:
    if signature == "APBK1672":
        taxonomy_key = "kis_order_response_rejection"
        label = "KIS 주문 응답 거부"
        reason = (
            "거부 주문 reason에서 KIS msg code APBK1672가 구조적으로 파싱됐다. "
            "KIS smoke가 성공이면 전체 브로커 장애가 아니라 관측된 주문 응답 거부로 분류한다."
        )
    else:
        return _unknown_row(signature=signature, count=count, live_context=live_context)

    rate = _float_or_none(rejection_summary.get("broker_error_observation_rate")) or 0.0
    smoke_healthy = bool(smoke_summary.get("healthy"))
    confidence = (
        CONFIDENCE_HIGH
        if rate >= 0.8 and smoke_healthy
        else CONFIDENCE_MEDIUM
        if count > 0
        else CONFIDENCE_LOW
    )
    recurrence = RECURRENCE_RECURRENT if count >= 2 else RECURRENCE_SINGLE
    action = _action_category(live_context)
    return BrokerRejectionClass(
        signature=signature,
        taxonomy_key=taxonomy_key,
        label_ko=label,
        count=count,
        confidence=confidence,
        recurrence_risk=recurrence,
        action_category=action,
        reason_ko=reason,
        next_action_ko=_next_action_for(action),
        evidence_keys=("execution-quality", "kis-smoke", "rebalance-micro-gtaa"),
    )


def _unknown_row(
    *,
    signature: str,
    count: int,
    live_context: Mapping[str, Any],
) -> BrokerRejectionClass:
    action = _action_category(live_context)
    return BrokerRejectionClass(
        signature=signature,
        taxonomy_key="unknown_broker_response",
        label_ko="알 수 없는 브로커 응답",
        count=count,
        confidence=CONFIDENCE_MEDIUM if count > 0 else CONFIDENCE_LOW,
        recurrence_risk=RECURRENCE_RECURRENT if count >= 2 else RECURRENCE_SINGLE,
        action_category=action,
        reason_ko="KIS code 사전에 없는 브로커 응답 signature라 집계값만 보존한다.",
        next_action_ko=_next_action_for(action),
        evidence_keys=("execution-quality", "rebalance-micro-gtaa"),
    )


def _live_intent_context(execution_doc: Any, rebalance_doc: Any) -> dict[str, Any]:
    live_gate = _mapping_value(execution_doc, "live_gate")
    source = rebalance_doc if isinstance(rebalance_doc, Mapping) else live_gate
    if not isinstance(source, Mapping):
        return {
            "present": False,
            "gate_ok": None,
            "reason": None,
            "verdict": None,
            "latest_signal": None,
            "blocks_live_orders": None,
            "next_action_ko": "micro GTAA live intent gate 증거를 먼저 복구합니다.",
        }
    gate_ok = source.get("ok")
    latest_signal = _clean(source.get("latest_signal"))
    reason = _clean(source.get("reason"))
    blocks = gate_ok is False or latest_signal == "INTENT_LOSS" or reason == "latest_intent_loss"
    return {
        "present": True,
        "gate_ok": gate_ok if isinstance(gate_ok, bool) else None,
        "reason": reason or None,
        "verdict": _none_if_blank(source.get("verdict")),
        "latest_signal": latest_signal or None,
        "blocks_live_orders": blocks,
        "next_action_ko": _clean(
            source.get("next_action_ko"),
            "실주문 재시도 없이 forward 토너먼트·전략 검토 증거를 기다립니다.",
        ),
    }


def _broker_smoke_summary(execution_doc: Any, kis_smoke_doc: Any) -> dict[str, Any]:
    execution_smoke = _mapping_value(execution_doc, "broker_smoke")
    direct = kis_smoke_doc if isinstance(kis_smoke_doc, Mapping) else {}
    smoke_state = _clean(
        direct.get("smoke_state")
        or _mapping_value(execution_smoke, "smoke_state")
        or "unknown"
    )
    smoke_exit = _int_or_none(
        direct.get("smoke_exit") or _mapping_value(execution_smoke, "smoke_exit")
    )
    tests_total = _int_or_none(_mapping_value(execution_smoke, "tests_total"))
    tests_failed = _int_or_none(_mapping_value(execution_smoke, "tests_failed"))
    healthy = smoke_state == "success" and (smoke_exit is None or smoke_exit == 0)
    return {
        "present": bool(direct) or isinstance(execution_smoke, Mapping),
        "direct_present": bool(direct),
        "execution_quality_present": isinstance(execution_smoke, Mapping),
        "smoke_state": smoke_state,
        "smoke_exit": smoke_exit,
        "key_valid": _bool_or_none(
            direct.get("key_valid") or _mapping_value(execution_smoke, "key_valid")
        ),
        "tests_total": tests_total,
        "tests_failed": tests_failed,
        "smoke_error_rate": _float_or_none(_mapping_value(execution_smoke, "smoke_error_rate")),
        "healthy": healthy,
    }


def _required_evidence_gate(surfaces: tuple[EvidenceSurface, ...]) -> QualityGate:
    bad = [
        f"{surface.key}:{surface.parse_status}"
        for surface in surfaces
        if surface.parse_status in {PARSE_MISSING, PARSE_MALFORMED}
    ]
    if bad:
        return QualityGate(
            "required_evidence_parse",
            GATE_FAIL,
            f"필수 입력 결손 또는 파싱 실패: {', '.join(bad)}",
            tuple(surface.key for surface in surfaces),
        )
    return QualityGate(
        "required_evidence_parse",
        GATE_PASS,
        "필수 sidecar가 모두 존재하고 구조화 파싱됐다.",
        tuple(surface.key for surface in surfaces),
    )


def _broker_rejection_evidence_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            "broker_rejection_evidence",
            GATE_FAIL,
            "execution-quality의 broker_rejections 블록을 읽을 수 없다.",
            ("execution-quality",),
        )
    rejected = _int(summary.get("rejected_orders"), 0)
    parsed = _int(summary.get("parsed_broker_errors"), 0)
    if rejected <= 0:
        return QualityGate(
            "broker_rejection_evidence",
            GATE_WAIT,
            "분류할 거부 주문 표본이 아직 없다.",
            ("execution-quality",),
        )
    if parsed <= 0:
        return QualityGate(
            "broker_rejection_evidence",
            GATE_WAIT,
            "거부 주문은 있지만 구조적으로 파싱된 브로커 오류가 없다.",
            ("execution-quality",),
        )
    return QualityGate(
        "broker_rejection_evidence",
        GATE_PASS,
        f"거부 주문 {rejected}건 중 브로커 오류 {parsed}건을 파싱했다.",
        ("execution-quality",),
    )


def _taxonomy_gate(taxonomy: tuple[BrokerRejectionClass, ...]) -> QualityGate:
    if not taxonomy:
        return QualityGate(
            "taxonomy_classification",
            GATE_WAIT,
            "분류 가능한 브로커 거부 signature가 없다.",
            ("execution-quality",),
        )
    signatures = ", ".join(entry.signature for entry in taxonomy)
    return QualityGate(
        "taxonomy_classification",
        GATE_PASS,
        f"브로커 거부 signature 분류 완료: {signatures}",
        ("execution-quality",),
    )


def _kis_smoke_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("present"):
        return QualityGate("kis_smoke_health", GATE_FAIL, "KIS smoke 증거가 없다.", ("kis-smoke",))
    if not summary.get("healthy"):
        return QualityGate(
            "kis_smoke_health",
            GATE_WAIT,
            f"KIS smoke 상태가 success가 아니다: {summary.get('smoke_state')}",
            ("kis-smoke",),
        )
    return QualityGate("kis_smoke_health", GATE_PASS, "KIS smoke가 성공 상태다.", ("kis-smoke",))


def _live_intent_gate(context: Mapping[str, Any]) -> QualityGate:
    if not context.get("present"):
        return QualityGate(
            "live_intent_context",
            GATE_WAIT,
            "micro GTAA live intent gate 증거가 없다.",
            ("rebalance-micro-gtaa",),
        )
    if context.get("blocks_live_orders"):
        return QualityGate(
            "live_intent_context",
            GATE_PASS,
            "latest intent gate가 실주문 재시도를 막고 있다.",
            ("rebalance-micro-gtaa",),
        )
    return QualityGate(
        "live_intent_context",
        GATE_PASS,
        "live intent gate 문맥을 읽었다.",
        ("rebalance-micro-gtaa",),
    )


def _safety_boundary_gate() -> QualityGate:
    return QualityGate(
        "safety_boundary",
        GATE_PASS,
        "읽기 전용 계약이며 브로커, 주문, 자본, live 설정, 비밀값을 건드리지 않는다.",
        (),
    )


def _overall_status(gates: tuple[QualityGate, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if GATE_FAIL in statuses:
        return BLOCKED
    if GATE_WAIT in statuses:
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _released_work_summary(parsed: Any) -> dict[str, Any]:
    released = {
        str(item.get("candidate_id") or "")
        for item in _items(parsed, "released_work")
        if str(item.get("status", "")).lower() in _RELEASED_STATUSES
    }
    return {
        "parseable": isinstance(parsed, Mapping),
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "completed_candidate_released": COMPLETED_CANDIDATE_ID in released,
        "released_count": len(released),
    }


def _capital_path_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, Mapping):
        return {
            "parseable": False,
            "live_money_status": None,
            "readiness_state": None,
            "money_path_mutation": False,
        }
    return {
        "parseable": True,
        "live_money_status": parsed.get("live_money_status"),
        "readiness_state": parsed.get("readiness_state"),
        "capital_ladder_status": _lookup(parsed, "capital_ladder_status", None),
        "money_path_mutation": False,
    }


def _action_category(live_context: Mapping[str, Any]) -> str:
    if live_context.get("blocks_live_orders"):
        return ACTION_NO_AUTO_RETRY
    if not live_context.get("present"):
        return ACTION_REPAIR_EVIDENCE
    return ACTION_OBSERVE


def _next_action_for(action: str) -> str:
    if action == ACTION_NO_AUTO_RETRY:
        return "실주문 재시도 없이 forward 토너먼트·전략 검토 증거를 기다린다."
    if action == ACTION_REPAIR_EVIDENCE:
        return "live intent gate와 execution-quality 입력 증거를 먼저 복구한다."
    return "거부 코드 분류를 관측 증거로 보존하고 다음 체결 품질 후보로 넘긴다."


def _summary_for(key: str, parsed: Any) -> str:
    if isinstance(parsed, list):
        return f"목록 {len(parsed)}개"
    if not isinstance(parsed, Mapping):
        return "구조화 값 존재"
    if key == "execution-quality":
        rejections = _mapping_value(parsed, "broker_rejections")
        return (
            f"overall={parsed.get('overall_status')}, "
            f"rejected={_mapping_value(rejections, 'rejected_orders')}, "
            f"codes={_mapping_value(rejections, 'kis_msg_codes')}"
        )
    if key == "kis-smoke":
        return f"state={parsed.get('smoke_state')}, exit={parsed.get('smoke_exit')}"
    if key == "rebalance-micro-gtaa":
        return f"signal={parsed.get('latest_signal')}, reason={parsed.get('reason')}"
    if key == "pipeline-liveness":
        return f"overall={parsed.get('overall') or parsed.get('overall_status')}"
    if key == "released-work":
        return f"released_count={len(_items(parsed, 'released_work'))}"
    if key == "capital-path-readiness":
        return (
            f"readiness={parsed.get('readiness_state')}, "
            f"live={parsed.get('live_money_status')}"
        )
    return "구조화 JSON 존재"


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _parse_markdown_json(raw: str) -> Any:
    parsed = _parse_json(raw)
    if parsed is not None:
        return parsed
    matches = _FENCED_JSON_RE.findall(raw)
    for body in matches:
        parsed = _parse_json(body.strip())
        if parsed is not None:
            return parsed
        match = _JSON_OBJECT_RE.search(body)
        if match:
            parsed = _parse_json(match.group(1))
            if parsed is not None:
                return parsed
    return None


def _json_after_marker(raw: str, marker: str) -> Any:
    marker_index = raw.find(marker)
    if marker_index < 0:
        return None
    object_index = raw.find("{", marker_index)
    if object_index < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(raw[object_index:])
    except json.JSONDecodeError:
        return None
    return parsed


def _kis_smoke_markdown(raw: str) -> dict[str, Any] | None:
    keys = (
        "run_id",
        "commit",
        "trigger",
        "timestamp_utc",
        "secrets_present",
        "key_valid",
        "smoke_state",
        "smoke_exit",
    )
    parsed = {
        key: value
        for key in keys
        if (value := _markdown_table_value(raw, key)) is not None
    }
    return parsed or None


def _markdown_table_value(text: str, key: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "|" not in stripped[1:]:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == key:
            return cells[1]
    return None


def _count_dict(raw: Any) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        return {}
    counts: dict[str, int] = {}
    for key, value in raw.items():
        count = _int(value, 0)
        if count:
            counts[str(key)] = count
    return dict(sorted(counts.items()))


def _items(parsed: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(parsed, Mapping):
        return []
    raw = parsed.get(key)
    if isinstance(raw, Mapping):
        if all(isinstance(value, Mapping) for value in raw.values()):
            return [
                {"key": str(item_key), **value}
                for item_key, value in raw.items()
                if isinstance(value, Mapping)
            ]
        return [dict(raw)]
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _mapping_value(parsed: Any, key: str) -> Any:
    return parsed.get(key) if isinstance(parsed, Mapping) else None


def _lookup(parsed: Any, key: str, default: Any) -> Any:
    if isinstance(parsed, Mapping):
        if key in parsed:
            return parsed[key]
        for value in parsed.values():
            found = _lookup(value, key, None)
            if found is not None:
                return found
    elif isinstance(parsed, list):
        for value in parsed:
            found = _lookup(value, key, None)
            if found is not None:
                return found
    return default


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _clean(value: object, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _none_if_blank(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _int(value: Any, default: int) -> int:
    parsed = _int_or_none(value)
    return parsed if parsed is not None else default


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return None


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


__all__ = [
    "ACTION_NO_AUTO_RETRY",
    "BLOCKED",
    "BrokerRejectionClass",
    "BrokerRejectionTaxonomyReport",
    "COMPLETED_CANDIDATE_ID",
    "CONTRACT_READY",
    "EvidenceSurface",
    "GATE_FAIL",
    "GATE_PASS",
    "GATE_WAIT",
    "NEXT_AUTONOMOUS_CANDIDATE_ID",
    "OBSERVATION_WAIT",
    "QualityGate",
    "REQUIRED_INPUTS",
    "SAFETY_INVARIANTS",
    "SCHEMA_VERSION",
    "build_broker_rejection_taxonomy_report",
    "read_evidence_manifest",
    "read_repo_sidecars",
]
