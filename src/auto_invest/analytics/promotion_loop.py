"""스펙 068 — 자율 승격 루프(read-only).

자율 성장 루프가 만든 후보를 다음 검증 단계로 분류한다. 이 모듈은 브로커 API,
주문, 자본, whitelist, caps, live 전략 설정을 건드리지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.evolution_loop import mask_sensitive_values

SCHEMA_VERSION = "1.0"

STAGE_EVIDENCE_MISSING = "EVIDENCE_MISSING"
STAGE_BACKTEST_REQUIRED = "BACKTEST_REQUIRED"
STAGE_FACTORY_PACKAGE_READY = "FACTORY_PACKAGE_READY"
STAGE_RECENT_OOS_REQUIRED = "RECENT_OOS_REQUIRED"
STAGE_FORWARD_REGISTRATION_READY = "FORWARD_REGISTRATION_READY"
STAGE_FORWARD_ACCUMULATING = "FORWARD_ACCUMULATING"
STAGE_CANARY_CANDIDATE = "CANARY_CANDIDATE"
STAGE_EXISTING_GATE_READY = "EXISTING_GATE_READY"
STAGE_OPERATOR_REVIEW = "OPERATOR_REVIEW"
STAGE_DISCARD = "DISCARD"

_RELEASED_STATUSES = {"released", "release", "completed", "complete", "done", "shipped"}

EVIDENCE_MISSING = "missing"
EVIDENCE_PENDING = "pending"
EVIDENCE_PASS = "pass"
EVIDENCE_FAIL = "fail"
EVIDENCE_UNKNOWN = "unknown"

OVERALL_OK = "ok"
OVERALL_DEGRADED = "degraded"

_BROKER_EXECUTION_GAPS: tuple[str, ...] = (
    "브로커 주문 거부",
    "부분 체결과 미체결",
    "실계좌 현금·결제·보유 종목 충돌",
    "장중 호가 스프레드와 슬리피지",
    "API 지연·장애·토큰 갱신",
    "append-only 감사 로그와 일일 정산",
)

_SAFETY_TO_GATE: dict[str, str] = {
    "capital": "spec-050-capital-ladder",
    "live_strategy": "spec-055-autonomous-reassignment",
}

_HARD_OPERATOR_SURFACES = {
    "orders",
    "whitelist",
    "caps",
    "secrets",
    "deploy",
    "kernel",
    "paid_service",
}

_FACTORY_STRATEGY_KINDS = {"strategy_backtest", "portfolio_backtest"}


@dataclass(frozen=True)
class EvidenceLayer:
    name: str
    status: str
    detail_ko: str
    source_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail_ko": self.detail_ko,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True)
class PromotionCandidate:
    candidate_id: str
    title_ko: str
    domain_key: str
    source_status: str
    risk_grade: int
    safety_impact: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    next_action_ko: str
    priority_score: int
    promotion_evidence: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title_ko": self.title_ko,
            "domain_key": self.domain_key,
            "source_status": self.source_status,
            "risk_grade": self.risk_grade,
            "safety_impact": list(self.safety_impact),
            "evidence_refs": list(self.evidence_refs),
            "next_action_ko": self.next_action_ko,
            "priority_score": self.priority_score,
            "promotion_evidence": dict(self.promotion_evidence),
        }


@dataclass(frozen=True)
class PromotionAssessment:
    candidate: PromotionCandidate
    stage: str
    allowed_next_action: str
    blocked_reason_ko: str
    strategy_validation_complete: bool
    execution_validation_complete: bool
    next_gate: str | None
    evidence_layers: tuple[EvidenceLayer, ...]

    @property
    def candidate_id(self) -> str:
        return self.candidate.candidate_id

    @property
    def priority_score(self) -> int:
        return self.candidate.priority_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "candidate_id": self.candidate_id,
            "stage": self.stage,
            "allowed_next_action": self.allowed_next_action,
            "blocked_reason_ko": self.blocked_reason_ko,
            "strategy_validation_complete": self.strategy_validation_complete,
            "execution_validation_complete": self.execution_validation_complete,
            "next_gate": self.next_gate,
            "priority_score": self.priority_score,
            "evidence_layers": [layer.to_dict() for layer in self.evidence_layers],
        }


@dataclass(frozen=True)
class PromotionRunSummary:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    assessments: tuple[PromotionAssessment, ...]
    missing_evidence: tuple[str, ...]

    @property
    def operator_review(self) -> tuple[str, ...]:
        return tuple(
            assessment.candidate_id
            for assessment in self.assessments
            if assessment.stage == STAGE_OPERATOR_REVIEW
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "operator_review": list(self.operator_review),
            "missing_evidence": list(self.missing_evidence),
            "assessments": [assessment.to_dict() for assessment in self.assessments],
        }

    def queue_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "queue": [
                {
                    "candidate_id": assessment.candidate_id,
                    "title_ko": assessment.candidate.title_ko,
                    "stage": assessment.stage,
                    "priority_score": assessment.priority_score,
                    "next_gate": assessment.next_gate,
                    "allowed_next_action": assessment.allowed_next_action,
                }
                for assessment in self.assessments
            ],
        }

    def as_markdown(self) -> str:
        lines = [
            "# 자율 승격 루프 최신 실행",
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
            "자율 성장 후보를 실제 돈 경로로 바로 보내지 않고, 백테스트·표본외·"
            "forward·캐너리·기존 게이트 중 다음 안전 단계로 자동 분류했다.",
            "",
            "## 백테스트와 소액 실거래가 다른 이유",
            "",
            "세계 최고 수준의 백테스트는 전략 논리와 과최적화 위험을 줄이는 필수 필터다. "
            "하지만 아래 실행 문제는 실제 브로커 경로에서만 확인된다.",
            "",
        ]
        for gap in _BROKER_EXECUTION_GAPS:
            lines.append(f"- {gap}")
        lines += [
            "",
            "따라서 백테스트 통과는 캐너리 후보 자격이지, 실계좌 실행 검증 완료가 아니다.",
            "",
            "## 승격 큐",
            "",
        ]
        if not self.assessments:
            lines.append("- 후보 없음")
        for idx, assessment in enumerate(self.assessments[:10], start=1):
            lines.append(
                f"{idx}. **{assessment.candidate.title_ko}** "
                f"(`{assessment.candidate_id}`, {assessment.stage}, "
                f"점수 {assessment.priority_score})"
            )
            lines.append(f"   - 다음 행동: {assessment.allowed_next_action}")
            if assessment.next_gate:
                lines.append(f"   - 기존 게이트: `{assessment.next_gate}`")
            lines.append(f"   - 차단/주의: {assessment.blocked_reason_ko}")
        lines += [
            "",
            "## 누락 증거",
            "",
        ]
        if self.missing_evidence:
            for item in self.missing_evidence:
                lines.append(f"- `{item}`")
        else:
            lines.append("- 없음")
        lines += [
            "",
            "## 안전 문구",
            "",
            "읽기 전용 실행입니다. 주문, 자본, whitelist, caps, live 전략, "
            "sentinels는 변경하지 않았습니다.",
        ]
        return mask_sensitive_values("\n".join(lines))


def scan_promotion(
    *,
    candidate_backlog: Mapping[str, Any] | None,
    evolution_summary: Mapping[str, Any] | None = None,
    evidence_texts: Mapping[str, str | None] | None = None,
    now: datetime | None = None,
    commit: str = "unknown",
    run_id: str = "local",
) -> PromotionRunSummary:
    now = _ensure_utc(now or datetime.now(UTC))
    evidence_texts = evidence_texts or {}
    candidates = parse_candidates(candidate_backlog, evolution_summary)
    assessments = tuple(
        sorted(
            (assess_candidate(candidate, evidence_texts) for candidate in candidates),
            key=lambda a: (_stage_sort(a.stage), -a.priority_score, a.candidate_id),
        )
    )
    missing = tuple(
        sorted(
            key
            for key in ("candidate_backlog",)
            if not _mapping_has_list(candidate_backlog, "candidates")
        )
    )
    has_operator_review = any(a.stage == STAGE_OPERATOR_REVIEW for a in assessments)
    overall = OVERALL_DEGRADED if missing or has_operator_review else OVERALL_OK
    return PromotionRunSummary(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=_iso(now),
        overall_status=overall,
        assessments=assessments,
        missing_evidence=missing,
    )


def parse_candidates(
    candidate_backlog: Mapping[str, Any] | None,
    evolution_summary: Mapping[str, Any] | None = None,
) -> tuple[PromotionCandidate, ...]:
    raw_candidates: Sequence[Any] = ()
    if _mapping_has_list(candidate_backlog, "candidates"):
        raw_candidates = candidate_backlog["candidates"]  # type: ignore[index]
    elif _mapping_has_list(evolution_summary, "candidates"):
        raw_candidates = evolution_summary["candidates"]  # type: ignore[index]
    candidates: list[PromotionCandidate] = []
    for item in raw_candidates:
        if not isinstance(item, Mapping):
            continue
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        candidates.append(
            PromotionCandidate(
                candidate_id=candidate_id,
                title_ko=str(item.get("title_ko") or candidate_id),
                domain_key=str(item.get("domain_key") or "unknown"),
                source_status=str(item.get("status") or "unknown"),
                risk_grade=_int(item.get("risk_grade"), default=2),
                safety_impact=tuple(str(x) for x in item.get("safety_impact") or ()),
                evidence_refs=tuple(str(x) for x in item.get("evidence_refs") or ()),
                next_action_ko=str(item.get("next_action_ko") or ""),
                priority_score=_int(
                    item.get("composite_score"),
                    default=_score_from_candidate(item),
                ),
                promotion_evidence=dict(item.get("promotion_evidence") or {}),
            )
        )
    return tuple(candidates)


def assess_candidate(
    candidate: PromotionCandidate,
    evidence_texts: Mapping[str, str | None],
) -> PromotionAssessment:
    layers = _evidence_layers(candidate, evidence_texts)
    layer_status = {layer.name: layer.status for layer in layers}
    next_gate = _next_gate(candidate.safety_impact)
    if candidate.source_status.lower() in _RELEASED_STATUSES:
        return _assessment(
            candidate,
            STAGE_DISCARD,
            layers,
            "이미 완료된 후보이므로 승격하지 않는다.",
            "상류 자율 성장 backlog가 완료 후보로 표시했다.",
            next_gate=None,
        )
    if candidate.source_status == "rejected":
        return _assessment(
            candidate,
            STAGE_DISCARD,
            layers,
            "학습 장부에서 폐기된 후보로 유지한다.",
            "기존 폐기 결정이 있고 재검토 조건이 없다.",
            next_gate=None,
        )
    hard_surfaces = set(candidate.safety_impact) & _HARD_OPERATOR_SURFACES
    if hard_surfaces:
        return _assessment(
            candidate,
            STAGE_OPERATOR_REVIEW,
            layers,
            "운영자 검토 또는 별도 SDD로 분리한다.",
            f"안전 경계({', '.join(sorted(hard_surfaces))})를 건드린다.",
            next_gate=None,
        )
    if _has_missing_source(candidate):
        return _assessment(
            candidate,
            STAGE_EVIDENCE_MISSING,
            layers,
            "후보 근거를 다시 수집한다.",
            "candidate backlog의 근거가 불충분하다.",
            next_gate=next_gate,
        )
    if _has_non_strategy_factory_package(candidate):
        return _assessment(
            candidate,
            STAGE_FACTORY_PACKAGE_READY,
            layers,
            "후보 구현 공장 패키지를 실행하고 결과 evidence를 누적한다.",
            "전략/포트폴리오 후보가 아니므로 forward paper 등록 대상은 아니다.",
            next_gate=next_gate,
        )
    factory_failure = _strategy_factory_failure_reason(candidate)
    if factory_failure:
        return _assessment(
            candidate,
            STAGE_DISCARD,
            layers,
            "검증 실패 후보를 승격하지 않고 재설계 또는 학습 장부 후보로 보낸다.",
            factory_failure,
            next_gate=None,
        )
    if layer_status["historical_backtest"] != EVIDENCE_PASS:
        return _assessment(
            candidate,
            STAGE_BACKTEST_REQUIRED,
            layers,
            "과거+비용+강건성 백테스트 패키지를 먼저 만든다.",
            "전략 논리 검증이 아직 없다.",
            next_gate=next_gate,
        )
    if layer_status["recent_oos"] != EVIDENCE_PASS or layer_status["walk_forward"] != EVIDENCE_PASS:
        return _assessment(
            candidate,
            STAGE_RECENT_OOS_REQUIRED,
            layers,
            "최근 표본외와 walk-forward 검증을 추가한다.",
            "과거 전체 성과만으로는 최근 regime과 과최적화 위험을 줄일 수 없다.",
            next_gate=next_gate,
        )
    if layer_status["forward_paper"] == EVIDENCE_MISSING:
        return _assessment(
            candidate,
            STAGE_FORWARD_REGISTRATION_READY,
            layers,
            "forward paper 트랙 등록 후보로 올린다.",
            "아직 보지 않은 미래 데이터로 검증되지 않았다.",
            strategy_complete=True,
            next_gate=next_gate,
        )
    if layer_status["forward_paper"] != EVIDENCE_PASS:
        return _assessment(
            candidate,
            STAGE_FORWARD_ACCUMULATING,
            layers,
            "forward paper 관측을 계속 누적한다.",
            "아직 EDGE_CONFIRMED가 아니다.",
            strategy_complete=True,
            next_gate=next_gate,
        )
    if layer_status["small_live_canary"] != EVIDENCE_PASS:
        return _assessment(
            candidate,
            STAGE_CANARY_CANDIDATE,
            layers,
            "소액 live canary 후보로 제출하되 주문 실행은 기존 게이트에 맡긴다.",
            "전략 검증은 통과했지만 브로커 실행 검증은 미완료다.",
            strategy_complete=True,
            next_gate=next_gate,
        )
    return _assessment(
        candidate,
        STAGE_EXISTING_GATE_READY,
        layers,
        "기존 돈 게이트 입력으로만 제출한다.",
        "전략 검증과 실행 경로 검증이 모두 충족됐다.",
        strategy_complete=True,
        execution_complete=True,
        next_gate=next_gate or "existing-promotion-gates",
    )


def backtest_vs_canary_explanation() -> tuple[str, ...]:
    return _BROKER_EXECUTION_GAPS


def write_promotion_artifacts(
    summary: PromotionRunSummary,
    *,
    summary_out: Path | None = None,
    json_out: Path | None = None,
    queue_out: Path | None = None,
) -> None:
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(summary.as_markdown() + "\n", encoding="utf-8")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(summary.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if queue_out is not None:
        queue_out.parent.mkdir(parents=True, exist_ok=True)
        queue_out.write_text(
            json.dumps(summary.queue_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _evidence_layers(
    candidate: PromotionCandidate,
    evidence_texts: Mapping[str, str | None],
) -> tuple[EvidenceLayer, ...]:
    promotion = candidate.promotion_evidence
    historical_backtest = _explicit_or_text_status(
        promotion,
        "historical_backtest",
        evidence_texts,
    )
    recent_oos = _explicit_or_text_status(promotion, "recent_oos", evidence_texts)
    walk_forward = _explicit_or_text_status(promotion, "walk_forward", evidence_texts)
    strategy_evidence_passed = (
        historical_backtest == EVIDENCE_PASS
        and recent_oos == EVIDENCE_PASS
        and walk_forward == EVIDENCE_PASS
    )
    forward_paper = (
        _forward_status(candidate, promotion, evidence_texts)
        if strategy_evidence_passed
        else EVIDENCE_MISSING
    )
    small_live_canary = (
        _canary_status(candidate, promotion, evidence_texts)
        if strategy_evidence_passed and forward_paper == EVIDENCE_PASS
        else EVIDENCE_MISSING
    )
    return (
        EvidenceLayer(
            "historical_backtest",
            historical_backtest,
            "과거 여러 구간에서 전략 논리와 비용 내성을 검증한다.",
            _source_for("historical_backtest", promotion),
        ),
        EvidenceLayer(
            "recent_oos",
            recent_oos,
            "최근 regime에서 완전히 죽은 전략인지 확인한다.",
            _source_for("recent_oos", promotion),
        ),
        EvidenceLayer(
            "walk_forward",
            walk_forward,
            "여러 표본외 구간으로 과최적화 위험을 줄인다.",
            _source_for("walk_forward", promotion),
        ),
        EvidenceLayer(
            "forward_paper",
            forward_paper,
            "전략 고정 후 아직 보지 않은 미래 데이터로 검증한다.",
            "rebalance-paper-forward",
        ),
        EvidenceLayer(
            "small_live_canary",
            small_live_canary,
            "실제 브로커·계좌·주문·체결 경로를 소액으로 검증한다.",
            "promotion-canary, reassign 또는 live canary sidecar",
        ),
    )


def _explicit_or_text_status(
    promotion: Mapping[str, Any],
    key: str,
    evidence_texts: Mapping[str, str | None],
) -> str:
    explicit = _status_value(promotion.get(key))
    if explicit != EVIDENCE_UNKNOWN:
        return explicit
    raw = "\n".join(text or "" for text in evidence_texts.values()).lower()
    token = key.replace("_", "-")
    has_key = token in raw or key in raw
    has_pass = "edge_confirmed" in raw or " pass" in raw or "pass" in raw
    if has_key and has_pass:
        return EVIDENCE_PASS
    return EVIDENCE_MISSING


def _forward_status(
    candidate: PromotionCandidate,
    promotion: Mapping[str, Any],
    evidence_texts: Mapping[str, str | None],
) -> str:
    explicit = _status_value(promotion.get("forward_paper"))
    if explicit != EVIDENCE_UNKNOWN:
        return explicit
    promotion_status = _candidate_window_status(
        evidence_texts.get("promotion-forward"),
        candidate.candidate_id,
        pass_tokens=("edge_confirmed", '"verdict":"edge_confirmed"', '"verdict": "edge_confirmed"'),
        fail_tokens=("no_edge", '"verdict":"no_edge"', '"verdict": "no_edge"'),
        pending_tokens=("insufficient_data", "premature", "관측 부족"),
    )
    if promotion_status != EVIDENCE_UNKNOWN:
        return promotion_status
    if (
        "rebalance-paper-forward" not in candidate.evidence_refs
        and "promotion-forward" not in candidate.evidence_refs
    ):
        return EVIDENCE_MISSING
    raw = (evidence_texts.get("rebalance-paper-forward") or "").lower()
    if "edge_confirmed" in raw:
        return EVIDENCE_PASS
    if "no_edge" in raw:
        return EVIDENCE_FAIL
    if "insufficient_data" in raw or "premature" in raw or "관측 부족" in raw:
        return EVIDENCE_PENDING
    return EVIDENCE_MISSING


def _canary_status(
    candidate: PromotionCandidate,
    promotion: Mapping[str, Any],
    evidence_texts: Mapping[str, str | None],
) -> str:
    explicit = _status_value(promotion.get("small_live_canary"))
    if explicit != EVIDENCE_UNKNOWN:
        return explicit
    promotion_status = _candidate_window_status(
        evidence_texts.get("promotion-canary"),
        candidate.candidate_id,
        pass_tokens=(
            '"verdict":"pass"',
            '"verdict": "pass"',
            "canary_verdict=pass",
            "canary_verdict: pass",
        ),
        fail_tokens=(
            '"verdict":"fail"',
            '"verdict": "fail"',
            '"verdict":"failed"',
            '"verdict": "failed"',
            "canary_verdict=fail",
            "canary_verdict: fail",
        ),
        pending_tokens=("pending", "wait_canary", "coverage", "none"),
    )
    if promotion_status != EVIDENCE_UNKNOWN:
        return promotion_status
    raw = "\n".join(
        text or "" for key, text in evidence_texts.items() if "canary" in key or key == "reassign"
    ).lower()
    if "canary_verdict" in raw and "pass" in raw:
        return EVIDENCE_PASS
    if "canary" in raw and "fail" in raw:
        return EVIDENCE_FAIL
    if raw:
        return EVIDENCE_PENDING
    return EVIDENCE_MISSING


def _candidate_window_status(
    text: str | None,
    candidate_id: str,
    *,
    pass_tokens: Sequence[str],
    fail_tokens: Sequence[str],
    pending_tokens: Sequence[str],
) -> str:
    raw = (text or "").lower()
    needle = candidate_id.lower()
    idx = raw.find(needle)
    if idx < 0:
        return EVIDENCE_UNKNOWN
    window = raw[max(0, idx - 300) : idx + 1500]
    if any(token in window for token in pass_tokens):
        return EVIDENCE_PASS
    if any(token in window for token in fail_tokens):
        return EVIDENCE_FAIL
    if any(token in window for token in pending_tokens):
        return EVIDENCE_PENDING
    return EVIDENCE_UNKNOWN


def _status_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {EVIDENCE_MISSING, EVIDENCE_PENDING, EVIDENCE_PASS, EVIDENCE_FAIL}:
        return text
    if text in {"ok", "passed", "edge_confirmed", "true"}:
        return EVIDENCE_PASS
    if text in {"failed", "no_edge", "false"}:
        return EVIDENCE_FAIL
    return EVIDENCE_UNKNOWN


def _assessment(
    candidate: PromotionCandidate,
    stage: str,
    layers: Sequence[EvidenceLayer],
    allowed_next_action: str,
    blocked_reason_ko: str,
    *,
    strategy_complete: bool = False,
    execution_complete: bool = False,
    next_gate: str | None = None,
) -> PromotionAssessment:
    return PromotionAssessment(
        candidate=candidate,
        stage=stage,
        allowed_next_action=allowed_next_action,
        blocked_reason_ko=blocked_reason_ko,
        strategy_validation_complete=strategy_complete,
        execution_validation_complete=execution_complete,
        next_gate=next_gate,
        evidence_layers=tuple(layers),
    )


def _next_gate(surfaces: Sequence[str]) -> str | None:
    for surface in surfaces:
        gate = _SAFETY_TO_GATE.get(surface)
        if gate:
            return gate
    return None


def _source_for(key: str, promotion: Mapping[str, Any]) -> str | None:
    value = promotion.get(f"{key}_source")
    return str(value) if value else None


def _has_non_strategy_factory_package(candidate: PromotionCandidate) -> bool:
    evidence = candidate.promotion_evidence
    kind = str(evidence.get("factory_kind") or "").strip()
    status = str(evidence.get("factory_status") or "").strip()
    if not kind or kind in _FACTORY_STRATEGY_KINDS:
        return False
    return status in {"ready", "pending", "evidence_passed", "pass"}


def _strategy_factory_failure_reason(candidate: PromotionCandidate) -> str | None:
    evidence = candidate.promotion_evidence
    kind = str(evidence.get("factory_kind") or "").strip()
    status = str(evidence.get("factory_status") or "").strip().lower()
    if kind not in _FACTORY_STRATEGY_KINDS:
        return None
    if status not in {"blocked", "fail", "failed", "no_edge", "false"}:
        return None
    reason = str(evidence.get("factory_block_reason_ko") or "").strip()
    if reason:
        return reason
    return "후보 구현 공장의 기계 판독 검증 결과가 실패했다."


def _has_missing_source(candidate: PromotionCandidate) -> bool:
    return not candidate.evidence_refs and not candidate.promotion_evidence


def _mapping_has_list(doc: Mapping[str, Any] | None, key: str) -> bool:
    return isinstance(doc, Mapping) and isinstance(doc.get(key), list)


def _score_from_candidate(item: Mapping[str, Any]) -> int:
    raw = item.get("priority_score")
    if raw is not None:
        return _int(raw, default=0)
    fields = (
        "growth_leverage",
        "capability_compounding",
        "capital_path_alignment",
        "evidence_confidence",
        "safety_preservation",
        "learning_velocity",
        "repeatability",
    )
    return sum(_int(item.get(field), default=0) for field in fields)


def _stage_sort(stage: str) -> int:
    order = {
        STAGE_EXISTING_GATE_READY: 0,
        STAGE_CANARY_CANDIDATE: 1,
        STAGE_FORWARD_REGISTRATION_READY: 2,
        STAGE_FORWARD_ACCUMULATING: 3,
        STAGE_RECENT_OOS_REQUIRED: 4,
        STAGE_BACKTEST_REQUIRED: 5,
        STAGE_FACTORY_PACKAGE_READY: 6,
        STAGE_EVIDENCE_MISSING: 7,
        STAGE_OPERATOR_REVIEW: 8,
        STAGE_DISCARD: 9,
    }
    return order.get(stage, 99)


def _int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _ensure_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_id(prefix: str, *parts: object) -> str:
    text = "\n".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}"


__all__ = [
    "EVIDENCE_FAIL",
    "EVIDENCE_MISSING",
    "EVIDENCE_PASS",
    "EVIDENCE_PENDING",
    "OVERALL_DEGRADED",
    "OVERALL_OK",
    "SCHEMA_VERSION",
    "STAGE_BACKTEST_REQUIRED",
    "STAGE_CANARY_CANDIDATE",
    "STAGE_DISCARD",
    "STAGE_EVIDENCE_MISSING",
    "STAGE_EXISTING_GATE_READY",
    "STAGE_FACTORY_PACKAGE_READY",
    "STAGE_FORWARD_ACCUMULATING",
    "STAGE_FORWARD_REGISTRATION_READY",
    "STAGE_OPERATOR_REVIEW",
    "STAGE_RECENT_OOS_REQUIRED",
    "EvidenceLayer",
    "PromotionAssessment",
    "PromotionCandidate",
    "PromotionRunSummary",
    "assess_candidate",
    "backtest_vs_canary_explanation",
    "parse_candidates",
    "scan_promotion",
    "stable_id",
    "write_promotion_artifacts",
]
