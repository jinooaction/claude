"""스펙 077 — 자율 작업 실행 루프.

기존 자율 루프가 발행한 sidecar를 읽어 "다음 Codex 작업 패킷"을 만든다.

안전 경계: 읽기 전용·순수·결정론. 이 모듈은 브로커, 주문, 자본 배분, live 설정,
whitelist/caps, 헌법/커널, 외부 유료 서비스를 변경하지 않는다. 산출물은 작업 인계용
sidecar이며, 실제 코드 수정과 PR/머지는 기존 Codex 작업 절차가 수행한다.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from auto_invest.analytics.evolution_loop import (
    classify_safety_surfaces,
    mask_sensitive_values,
    risk_grade_for_surfaces,
)

SCHEMA_VERSION = "1.0"

PARSE_OK = "ok"
PARSE_PRESENT = "present"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

STATUS_EXECUTION_READY = "EXECUTION_READY"
STATUS_OPERATOR_APPROVAL_REQUIRED = "OPERATOR_APPROVAL_REQUIRED"
STATUS_OBSERVATION_WAIT = "OBSERVATION_WAIT"
STATUS_SUPPRESSED = "SUPPRESSED"
STATUS_BLOCKED = "BLOCKED"

_REJECTED_STATUSES = {
    "reject",
    "rejected",
    "discard",
    "discarded",
    "unsafe",
    "do_not_run",
}
_BLOCKED_STATUSES = {"blocked", "missing_input", "missing_inputs"}
_OPERATOR_STATUSES = {"operator_review", "operator_approval", "approval_required"}

_SOURCE_REFS: dict[str, str] = {
    "capital-path-readiness": (
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
    ),
    "evolution-backlog": "automation/autonomous-evolution-last-run:candidate_backlog.json",
    "evolution-ledger": "automation/autonomous-evolution-last-run:learning_ledger.json",
    "autonomous-promotion": "automation/autonomous-promotion-last-run:promotion_summary.json",
    "candidate-implementation-factory": (
        "automation/candidate-implementation-factory-last-run:candidate_factory.json"
    ),
    "candidate-packages": (
        "automation/candidate-implementation-factory-last-run:candidate_packages.json"
    ),
    "candidate-result-executor": (
        "automation/candidate-implementation-results:candidate_results.json"
    ),
    "pipeline-liveness": "automation/pipeline-liveness-last-run:LAST_RUN.md",
}

_DOMAIN_WORK_TYPES: dict[str, str] = {
    "live_readiness": "gate_alignment",
    "execution_quality": "execution_quality",
    "data_quality": "data_quality",
    "data_collection": "data_collection",
    "analysis": "analytics_validation",
    "strategy_design": "strategy_validation",
    "portfolio_design": "portfolio_validation",
    "agent_ops": "agent_operating_system",
    "review": "review_learning",
}

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "work packet only; code/PR/merge stays in Codex review path",
)


@dataclass(frozen=True)
class EvidenceSurface:
    """입력 sidecar 한 개의 존재·파싱 상태."""

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
class WorkPacket:
    """다음 Codex 작업으로 넘길 최소 실행 단위."""

    packet_id: str
    candidate_id: str
    domain_key: str
    title_ko: str
    work_type: str
    risk_grade: int
    safety_impact: tuple[str, ...]
    priority_score: int
    status: str
    reason_ko: str
    next_action_ko: str
    required_inputs: tuple[str, ...]
    safety_boundary: tuple[str, ...]
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "candidate_id": self.candidate_id,
            "domain_key": self.domain_key,
            "title_ko": self.title_ko,
            "work_type": self.work_type,
            "risk_grade": self.risk_grade,
            "safety_impact": list(self.safety_impact),
            "priority_score": self.priority_score,
            "status": self.status,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "required_inputs": list(self.required_inputs),
            "safety_boundary": list(self.safety_boundary),
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class AutonomousWorkExecutionReport:
    """자율 작업 실행 루프의 최종 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    selected_work: WorkPacket | None
    ranked_work: tuple[WorkPacket, ...]
    suppressed_work: tuple[WorkPacket, ...]
    evidence_surfaces: tuple[EvidenceSurface, ...]
    safety_invariants: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "selected_work": (
                self.selected_work.to_dict() if self.selected_work is not None else None
            ),
            "ranked_work": [packet.to_dict() for packet in self.ranked_work],
            "suppressed_work": [packet.to_dict() for packet in self.suppressed_work],
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 자율 작업 실행 루프 (as of {self.timestamp_utc})",
            "",
            "읽기 전용 보고입니다. 이 루프는 다음 Codex 작업 패킷만 발행합니다.",
            "주문, 자본 배분, live 설정 변경, 코드 자동 수정, PR 자동 생성은 하지 않습니다.",
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
        ]
        if self.selected_work is None:
            lines.append("| selected_work | 없음 |")
        else:
            packet = self.selected_work
            lines += [
                f"| selected_work | {_table(packet.candidate_id)} |",
                f"| title_ko | {_table(packet.title_ko)} |",
                f"| status | {packet.status} |",
                f"| risk_grade | {packet.risk_grade} |",
                f"| priority_score | {packet.priority_score} |",
                f"| next_action_ko | {_table(packet.next_action_ko)} |",
            ]

        lines += ["", "## 실행 가능 후보", ""]
        if self.ranked_work:
            lines += [
                "| 후보 | 영역 | 상태 | 위험 | 점수 | 이유 |",
                "|------|------|------|-----:|-----:|------|",
            ]
            for packet in self.ranked_work:
                lines.append(
                    f"| {_table(packet.candidate_id)} | {_table(packet.domain_key)} | "
                    f"{packet.status} | {packet.risk_grade} | {packet.priority_score} | "
                    f"{_table(packet.reason_ko)} |"
                )
        else:
            lines.append("- 현재 실행 가능한 안전 후보가 없습니다.")

        lines += ["", "## 승인 필요 또는 억제 후보", ""]
        if self.suppressed_work:
            lines += [
                "| 후보 | 영역 | 상태 | 위험 | 안전 표면 | 이유 |",
                "|------|------|------|-----:|-----------|------|",
            ]
            for packet in self.suppressed_work:
                impacts = ", ".join(packet.safety_impact) or "-"
                lines.append(
                    f"| {_table(packet.candidate_id)} | {_table(packet.domain_key)} | "
                    f"{packet.status} | {packet.risk_grade} | {_table(impacts)} | "
                    f"{_table(packet.reason_ko)} |"
                )
        else:
            lines.append("- 승인 필요 또는 억제 후보가 없습니다.")

        lines += [
            "",
            "## 입력 증거",
            "",
            "| 증거 | 존재 | 파싱 | 요약 |",
            "|------|:----:|------|------|",
        ]
        for surface in self.evidence_surfaces:
            present = "yes" if surface.present else "no"
            lines.append(
                f"| {surface.key} | {present} | {surface.parse_status} | "
                f"{_table(surface.summary_ko)} |"
            )

        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        return "\n".join(lines)


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _clean(value: object, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return mask_sensitive_values(text)


def _table(value: object) -> str:
    return _clean(value).replace("|", "/").replace("\n", " ")


def _json_value(text: str | None) -> Any | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _json_from_fence(text: str, headers: Sequence[str]) -> Any | None:
    lines = text.splitlines()
    starts: list[int] = []
    if headers:
        for i, line in enumerate(lines):
            if any(header in line for header in headers):
                starts.append(i + 1)
    starts.append(0)

    for start in starts:
        in_block = False
        buf: list[str] = []
        for line in lines[start:]:
            stripped = line.strip()
            if not in_block:
                if stripped.startswith("```"):
                    in_block = True
                continue
            if stripped.startswith("```"):
                parsed = _json_value("\n".join(buf))
                if parsed is not None:
                    return parsed
                break
            buf.append(line)
    return None


def _json_any(text: str | None, *headers: str) -> Any | None:
    parsed = _json_value(text)
    if parsed is not None:
        return parsed
    if text:
        return _json_from_fence(text, headers)
    return None


def _items(value: Any, keys: Sequence[str]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []
    for key in keys:
        raw = value.get(key)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    return []


def _candidate_id(item: Mapping[str, Any], fallback_prefix: str) -> str:
    raw = (
        item.get("candidate_id")
        or item.get("id")
        or item.get("candidate")
        or item.get("candidate_key")
        or item.get("package_id")
        or item.get("result_id")
    )
    if raw:
        return _clean(raw)
    digest = hashlib.sha256(
        json.dumps(dict(item), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"{fallback_prefix}-{digest}"


def _candidate_status(item: Mapping[str, Any]) -> str:
    return _clean(
        item.get("status")
        or item.get("decision")
        or item.get("action")
        or item.get("outcome")
        or "new"
    )


def _candidate_score(item: Mapping[str, Any]) -> int:
    for key in ("priority_score", "composite_score", "score"):
        raw = item.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return 0


def _candidate_title(item: Mapping[str, Any]) -> str:
    return _clean(
        item.get("title_ko")
        or item.get("title")
        or item.get("name")
        or item.get("summary_ko")
        or item.get("package_kind")
        or "제목 없음"
    )


def _candidate_reason(item: Mapping[str, Any], fallback: str) -> str:
    return _clean(
        item.get("reason_ko")
        or item.get("problem_ko")
        or item.get("expected_benefit")
        or item.get("block_reason_ko")
        or item.get("summary_ko")
        or fallback
    )


def _candidate_next_action(item: Mapping[str, Any], fallback: str) -> str:
    return _clean(
        item.get("next_action_ko")
        or item.get("next_action")
        or item.get("action_ko")
        or item.get("recommended_action_ko")
        or fallback
    )


def _candidate_domain(item: Mapping[str, Any], fallback: str) -> str:
    return _clean(
        item.get("domain_key") or item.get("domain") or item.get("category") or fallback
    )


def _strings(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (_clean(raw),) if raw.strip() else ()
    if isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray)):
        return tuple(_clean(item) for item in raw if _clean(item))
    return (_clean(raw),)


def _safety_impact(item: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = set(_strings(item.get("safety_impact")))
    text = "\n".join(
        _clean(item.get(key))
        for key in (
            "title_ko",
            "title",
            "problem_ko",
            "expected_benefit",
            "next_action_ko",
            "next_action",
            "reason_ko",
            "safety_note_ko",
        )
    )
    detected = set(classify_safety_surfaces(text))
    return tuple(
        sorted(surface for surface in explicit | detected if surface and surface != "none")
    )


def _risk_grade(item: Mapping[str, Any], safety_impact: Sequence[str]) -> int:
    try:
        explicit = int(item.get("risk_grade"))
    except (TypeError, ValueError):
        explicit = None
    inferred = risk_grade_for_surfaces(safety_impact)
    return max(explicit or inferred, inferred)


def _work_type(domain_key: str, item: Mapping[str, Any]) -> str:
    raw = item.get("work_type") or item.get("package_kind") or item.get("breakthrough_type")
    return _clean(raw) if raw else _DOMAIN_WORK_TYPES.get(domain_key, "autonomous_improvement")


def _required_inputs(item: Mapping[str, Any], source_ref: str) -> tuple[str, ...]:
    values: list[str] = [source_ref]
    for key in ("required_inputs", "required_data", "evidence_refs", "produces_evidence"):
        values.extend(_strings(item.get(key)))
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return tuple(deduped)


def _status_for_candidate(
    source_status: str,
    risk_grade: int,
    safety_impact: Sequence[str],
) -> str:
    lowered = source_status.strip().lower()
    if lowered in _REJECTED_STATUSES:
        return STATUS_SUPPRESSED
    if lowered in _BLOCKED_STATUSES:
        return STATUS_BLOCKED
    if lowered in _OPERATOR_STATUSES or risk_grade >= 3 or safety_impact:
        return STATUS_OPERATOR_APPROVAL_REQUIRED
    return STATUS_EXECUTION_READY


def _packet_id(candidate_id: str, title_ko: str, source_refs: Sequence[str]) -> str:
    digest = hashlib.sha256(
        "|".join([candidate_id, title_ko, *source_refs]).encode("utf-8")
    ).hexdigest()[:12]
    return f"work-{digest}"


def _packet_from_item(
    item: Mapping[str, Any],
    *,
    source_key: str,
    source_weight: int,
    fallback_domain: str,
    fallback_reason: str,
    fallback_action: str,
) -> WorkPacket:
    source_ref = _SOURCE_REFS[source_key]
    candidate_id = _candidate_id(item, source_key)
    domain_key = _candidate_domain(item, fallback_domain)
    title = _candidate_title(item)
    source_status = _candidate_status(item)
    safety_impact = _safety_impact(item)
    risk_grade = _risk_grade(item, safety_impact)
    status = _status_for_candidate(source_status, risk_grade, safety_impact)
    reason = _candidate_reason(item, fallback_reason)
    next_action = _candidate_next_action(item, fallback_action)
    source_refs = (source_ref,)
    score = source_weight + _candidate_score(item)
    return WorkPacket(
        packet_id=_packet_id(candidate_id, title, source_refs),
        candidate_id=candidate_id,
        domain_key=domain_key,
        title_ko=title,
        work_type=_work_type(domain_key, item),
        risk_grade=risk_grade,
        safety_impact=safety_impact,
        priority_score=score,
        status=status,
        reason_ko=reason,
        next_action_ko=next_action,
        required_inputs=_required_inputs(item, source_ref),
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _generated_packet(
    *,
    candidate_id: str,
    domain_key: str,
    title_ko: str,
    priority_score: int,
    reason_ko: str,
    next_action_ko: str,
    source_ref: str,
    status: str = STATUS_EXECUTION_READY,
) -> WorkPacket:
    source_refs = (source_ref,)
    return WorkPacket(
        packet_id=_packet_id(candidate_id, title_ko, source_refs),
        candidate_id=candidate_id,
        domain_key=domain_key,
        title_ko=title_ko,
        work_type=_DOMAIN_WORK_TYPES.get(domain_key, "agent_operating_system"),
        risk_grade=2,
        safety_impact=(),
        priority_score=priority_score,
        status=status,
        reason_ko=reason_ko,
        next_action_ko=next_action_ko,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _evidence_surface(key: str, raw: str | None, parsed: Any) -> EvidenceSurface:
    source_ref = _SOURCE_REFS[key]
    if raw is None:
        return EvidenceSurface(
            key=key,
            source_ref=source_ref,
            present=False,
            parse_status=PARSE_MISSING,
            summary_ko="sidecar 없음",
        )
    if parsed is None:
        return EvidenceSurface(
            key=key,
            source_ref=source_ref,
            present=True,
            parse_status=PARSE_MALFORMED,
            summary_ko="원문 존재, 구조화 JSON 파싱 실패",
        )
    return EvidenceSurface(
        key=key,
        source_ref=source_ref,
        present=True,
        parse_status=PARSE_OK if isinstance(parsed, (dict, list)) else PARSE_PRESENT,
        summary_ko=_summary_for_parsed(parsed),
    )


def _summary_for_parsed(parsed: Any) -> str:
    if isinstance(parsed, list):
        return f"목록 {len(parsed)}개"
    if not isinstance(parsed, dict):
        return "구조화 값 존재"
    if parsed.get("overall") or parsed.get("overall_status"):
        return f"overall={parsed.get('overall') or parsed.get('overall_status')}"
    if parsed.get("readiness_state"):
        return (
            f"readiness={parsed.get('readiness_state')}, "
            f"live={parsed.get('live_money_status')}"
        )
    for key in ("candidates", "packages", "results", "actions", "assessments", "entries"):
        raw = parsed.get(key)
        if isinstance(raw, list):
            return f"{key}={len(raw)}"
    return "구조화 JSON 존재"


def _pipeline_packets(raw: str | None, parsed: Any) -> list[WorkPacket]:
    source_ref = _SOURCE_REFS["pipeline-liveness"]
    if raw is None:
        return [
            _generated_packet(
                candidate_id="ops-pipeline-liveness-missing",
                domain_key="agent_ops",
                title_ko="파이프라인 생존 감시 sidecar 미발행 복구",
                priority_score=10100,
                reason_ko="생존 감시 sidecar가 없어 자동 루프 전체 상태를 확인할 수 없다.",
                next_action_ko="pipeline-liveness workflow와 sidecar 발행 경로를 먼저 복구한다.",
                source_ref=source_ref,
            )
        ]
    if not isinstance(parsed, dict):
        return [
            _generated_packet(
                candidate_id="ops-pipeline-liveness-malformed",
                domain_key="agent_ops",
                title_ko="파이프라인 생존 감시 JSON 파싱 복구",
                priority_score=10050,
                reason_ko="생존 감시 원문은 있으나 기계 판독 JSON이 깨져 있다.",
                next_action_ko="pipeline-liveness LAST_RUN.md의 결정 JSON 발행 형식을 복구한다.",
                source_ref=source_ref,
            )
        ]
    overall = _clean(parsed.get("overall") or parsed.get("overall_status"))
    if overall != "CRITICAL":
        return []
    critical_checks = [
        _clean(check.get("key"))
        for check in _items(parsed, ("checks",))
        if _clean(check.get("status")) in {"STALE", "MISSING"} and bool(check.get("critical"))
    ]
    detail = ", ".join(critical_checks) if critical_checks else "핵심 sidecar 정지"
    return [
        _generated_packet(
            candidate_id="ops-pipeline-liveness-critical",
            domain_key="agent_ops",
            title_ko="핵심 자동 루프 정지 원인 복구",
            priority_score=11000,
            reason_ko=f"pipeline-liveness가 CRITICAL이다: {detail}",
            next_action_ko="멈춘 핵심 sidecar workflow 로그와 입력 비밀값/스케줄을 먼저 복구한다.",
            source_ref=source_ref,
        )
    ]


def _capital_health_packets(raw: str | None, parsed: Any) -> list[WorkPacket]:
    source_ref = _SOURCE_REFS["capital-path-readiness"]
    if raw is None:
        return [
            _generated_packet(
                candidate_id="ops-capital-path-readiness-missing",
                domain_key="agent_ops",
                title_ko="자본 경로 준비도 sidecar 미발행 복구",
                priority_score=9550,
                reason_ko="돈을 더 벌기 위한 자본 경로 준비도 보고가 없다.",
                next_action_ko=(
                    "capital-path-readiness workflow와 입력 sidecar 수집 경로를 복구한다."
                ),
                source_ref=source_ref,
            )
        ]
    if not isinstance(parsed, dict):
        return [
            _generated_packet(
                candidate_id="ops-capital-path-readiness-malformed",
                domain_key="agent_ops",
                title_ko="자본 경로 준비도 JSON 파싱 복구",
                priority_score=9500,
                reason_ko="자본 경로 준비도 원문은 있으나 기계 판독 JSON이 깨져 있다.",
                next_action_ko="capital-path-readiness JSON 발행 형식과 probe 출력을 복구한다.",
                source_ref=source_ref,
            )
        ]
    return []


def _candidate_packets(parsed: dict[str, Any]) -> list[WorkPacket]:
    packets: list[WorkPacket] = []
    capital = parsed.get("capital-path-readiness")
    if isinstance(capital, dict):
        for item in _items(capital, ("priority_candidates",)):
            packets.append(
                _packet_from_item(
                    item,
                    source_key="capital-path-readiness",
                    source_weight=3000,
                    fallback_domain="live_readiness",
                    fallback_reason="자본 경로 준비도 루프가 우선 후보로 올렸다.",
                    fallback_action="이 후보를 스펙/구현 작업 패킷으로 넘긴다.",
                )
            )
        for item in _items(capital, ("suppressed_candidates",)):
            suppressed = dict(item)
            suppressed.setdefault("status", "rejected")
            packets.append(
                _packet_from_item(
                    suppressed,
                    source_key="capital-path-readiness",
                    source_weight=1000,
                    fallback_domain="live_readiness",
                    fallback_reason="자본 경로 준비도 루프가 억제 후보로 표시했다.",
                    fallback_action="learning ledger와 억제 사유를 확인한다.",
                )
            )

    backlog = parsed.get("evolution-backlog")
    for item in _items(backlog, ("candidates", "backlog", "items")):
        packets.append(
            _packet_from_item(
                item,
                source_key="evolution-backlog",
                source_weight=2000,
                fallback_domain="agent_ops",
                fallback_reason="자율 성장 루프가 고레버리지 후보로 발굴했다.",
                fallback_action="후보를 스펙 또는 검증 패키지로 구체화한다.",
            )
        )

    promotion = parsed.get("autonomous-promotion")
    for item in _items(promotion, ("actions", "assessments", "candidates", "results")):
        packets.append(
            _packet_from_item(
                item,
                source_key="autonomous-promotion",
                source_weight=2400,
                fallback_domain="analysis",
                fallback_reason="자율 승격 루프가 후보 검증 단계를 제안했다.",
                fallback_action="승격 판단과 필요한 검증 evidence를 확인한다.",
            )
        )

    factory = parsed.get("candidate-implementation-factory")
    for item in _items(factory, ("packages",)):
        packets.append(
            _packet_from_item(
                item,
                source_key="candidate-implementation-factory",
                source_weight=2200,
                fallback_domain="analysis",
                fallback_reason="후보 구현 공장이 검증 패키지를 만들었다.",
                fallback_action="검증 패키지 결과를 확인하고 다음 구현 작업으로 연결한다.",
            )
        )

    packages = parsed.get("candidate-packages")
    for item in _items(packages, ("packages",)):
        packets.append(
            _packet_from_item(
                item,
                source_key="candidate-packages",
                source_weight=2100,
                fallback_domain="analysis",
                fallback_reason="후보 검증 패키지가 발행됐다.",
                fallback_action="허용된 no-live 검증 결과를 확인하고 후보 상태를 갱신한다.",
            )
        )

    results = parsed.get("candidate-result-executor")
    for item in _items(results, ("results", "candidate_results")):
        packets.append(
            _packet_from_item(
                item,
                source_key="candidate-result-executor",
                source_weight=2300,
                fallback_domain="review",
                fallback_reason="후보 결과 실행기가 검증 evidence를 남겼다.",
                fallback_action="검증 결과를 회고하고 통과 후보는 다음 단계로 연결한다.",
            )
        )
    return packets


def _ledger_rejections(ledger: Any) -> dict[str, str]:
    rejected: dict[str, str] = {}
    for item in _items(ledger, ("entries", "ledger", "decisions", "records")):
        candidate_id = _candidate_id(item, "ledger")
        status = _candidate_status(item).lower()
        if status not in _REJECTED_STATUSES:
            continue
        rejected[candidate_id] = _candidate_reason(
            item,
            "learning ledger가 이전 검증 실패 또는 거부 결정을 기록했다.",
        )
    return rejected


def _apply_ledger_rejections(
    packets: Sequence[WorkPacket],
    ledger: Any,
) -> tuple[WorkPacket, ...]:
    rejected = _ledger_rejections(ledger)
    if not rejected:
        return tuple(packets)
    updated: list[WorkPacket] = []
    for packet in packets:
        reason = rejected.get(packet.candidate_id)
        if reason is None:
            updated.append(packet)
            continue
        updated.append(
            replace(
                packet,
                status=STATUS_SUPPRESSED,
                reason_ko=(
                    "learning ledger가 이 후보를 억제했다: "
                    f"{reason}"
                ),
            )
        )
    return tuple(updated)


def _dedupe_packets(packets: Sequence[WorkPacket]) -> tuple[WorkPacket, ...]:
    by_candidate: dict[str, WorkPacket] = {}
    for packet in packets:
        existing = by_candidate.get(packet.candidate_id)
        if existing is None or _packet_sort_key(packet) < _packet_sort_key(existing):
            by_candidate[packet.candidate_id] = packet
    return tuple(sorted(by_candidate.values(), key=_packet_sort_key))


def _packet_sort_key(packet: WorkPacket) -> tuple[int, int, str]:
    status_rank = {
        STATUS_EXECUTION_READY: 0,
        STATUS_OPERATOR_APPROVAL_REQUIRED: 1,
        STATUS_BLOCKED: 2,
        STATUS_SUPPRESSED: 3,
    }.get(packet.status, 4)
    return (status_rank, -packet.priority_score, packet.candidate_id)


def _overall_status(
    selected: WorkPacket | None,
    ranked: Sequence[WorkPacket],
    suppressed: Sequence[WorkPacket],
    surfaces: Sequence[EvidenceSurface],
) -> str:
    if selected is not None:
        return selected.status
    if ranked:
        return STATUS_EXECUTION_READY
    if suppressed:
        return suppressed[0].status
    if all(surface.parse_status == PARSE_MISSING for surface in surfaces):
        return STATUS_BLOCKED
    return STATUS_OBSERVATION_WAIT


def build_autonomous_work_execution(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> AutonomousWorkExecutionReport:
    """수집된 sidecar 원문으로 다음 자율 작업 패킷을 만든다."""

    now = _as_utc(now)
    parsed: dict[str, Any] = {
        key: _json_any(raw, "결정 JSON", "decision JSON")
        for key, raw in evidence_texts.items()
    }
    for key in _SOURCE_REFS:
        parsed.setdefault(key, None)

    surfaces = tuple(
        _evidence_surface(key, evidence_texts.get(key), parsed.get(key))
        for key in _SOURCE_REFS
    )

    packets: list[WorkPacket] = []
    packets.extend(
        _pipeline_packets(
            evidence_texts.get("pipeline-liveness"),
            parsed["pipeline-liveness"],
        )
    )
    packets.extend(
        _capital_health_packets(
            evidence_texts.get("capital-path-readiness"),
            parsed["capital-path-readiness"],
        )
    )
    packets.extend(_candidate_packets(parsed))
    packets = list(_apply_ledger_rejections(packets, parsed.get("evolution-ledger")))

    ordered = _dedupe_packets(packets)
    ranked = tuple(packet for packet in ordered if packet.status == STATUS_EXECUTION_READY)[:10]
    suppressed = tuple(packet for packet in ordered if packet.status != STATUS_EXECUTION_READY)[:10]
    selected = ranked[0] if ranked else (suppressed[0] if suppressed else None)
    overall = _overall_status(selected, ranked, suppressed, surfaces)

    return AutonomousWorkExecutionReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        overall_status=overall,
        selected_work=selected,
        ranked_work=ranked,
        suppressed_work=suppressed,
        evidence_surfaces=surfaces,
        safety_invariants=SAFETY_INVARIANTS,
    )


__all__ = [
    "AutonomousWorkExecutionReport",
    "EvidenceSurface",
    "SAFETY_INVARIANTS",
    "SCHEMA_VERSION",
    "STATUS_BLOCKED",
    "STATUS_EXECUTION_READY",
    "STATUS_OBSERVATION_WAIT",
    "STATUS_OPERATOR_APPROVAL_REQUIRED",
    "STATUS_SUPPRESSED",
    "WorkPacket",
    "build_autonomous_work_execution",
]
