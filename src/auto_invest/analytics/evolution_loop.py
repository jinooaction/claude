"""스펙 067 — 영구 자율 성장 루프(read-only).

이 모듈은 sidecar와 handoff 같은 이미 발행된 증거를 읽어, 전 영역 고레버리지
돌파 후보를 결정론적으로 만든다. 브로커 API, 주문, 자본, whitelist, caps, live
전략 설정은 건드리지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

STATUS_NEW = "new"
STATUS_PLANNED = "planned"
STATUS_EVIDENCE_DEPENDENT = "evidence_dependent"
STATUS_PROMOTED = "promoted"
STATUS_REJECTED = "rejected"
STATUS_OPERATOR_REVIEW = "operator_review"

DECISION_DISCARD = "discard"
DECISION_OBSERVE = "observe"
DECISION_CREATE_SPEC = "create_spec"
DECISION_OPEN_PR = "open_pr"
DECISION_FEED_EXISTING_GATE = "feed_existing_gate"
DECISION_OPERATOR_REVIEW = "operator_review"

EVIDENCE_NONE = "none"
EVIDENCE_MARKET_OBSERVATION = "market_observation"
EVIDENCE_SIDECAR_FRESHNESS = "sidecar_freshness"
EVIDENCE_EXTERNAL_DATA = "external_data"
EVIDENCE_OPERATOR_REVIEW = "operator_review"
EVIDENCE_NEW_EXPERIMENT = "new_experiment"

OVERALL_OK = "ok"
OVERALL_DEGRADED = "degraded"
OVERALL_BLOCKED = "blocked"

_TS_RE = re.compile(r"timestamp_utc[^0-9]*?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)")

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b(kis_(?:app_)?(?:key|secret)|app(?:key|secret)|"
        r"telegram_(?:bot_)?token|telegram_chat_id|authorization|"
        r"secret|token|account(?:_no|_number)?)\b\s*[:=|]\s*"
        r"([A-Za-z0-9_./:+@-]{6,})"
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{10,}"),
    re.compile(r"\b\d{8,}-\d{2}\b"),
)

_SAFETY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "orders": (
        "place order",
        "submit order",
        "retry order",
        "cancel order",
        "broker order",
        "실주문 실행",
        "실주문 전환",
        "주문 제출",
        "주문 재시도",
        "주문 취소",
    ),
    "capital": (
        "increase capital",
        "capital increase",
        "capital scaling",
        "capital allocation",
        "자본 증액",
        "자본 배분",
        "자본 확대",
        "레버리지 적용",
    ),
    "whitelist": (
        "widen whitelist",
        "whitelist expansion",
        "allowlist",
        "허용 종목 확대",
        "화이트리스트 확대",
    ),
    "caps": (
        "relax cap",
        "cap relaxation",
        "position cap",
        "한도 완화",
        "포지션 한도 완화",
    ),
    "secrets": (
        "secret handling",
        "kis secret",
        "telegram token",
        "비밀값",
        "시크릿",
    ),
    "deploy": (
        "deployment restriction",
        "market-hours deploy",
        "deploy guard",
        "배포 제한",
        "장중 배포",
    ),
    "kernel": (
        "constitution",
        "kernel",
        "헌법",
        "커널",
        "safety perimeter",
    ),
    "live_strategy": (
        "live strategy swap",
        "replace live strategy",
        "live 전략 교체",
        "라이브 전략 교체",
        "실거래 전략 교체",
    ),
    "paid_service": (
        "paid service",
        "paid data",
        "external paid",
        "유료 데이터",
        "유료 서비스",
        "외부 서비스 비용",
    ),
}


@dataclass(frozen=True)
class EvidenceRequirement:
    key: str
    branch: str
    filename: str
    max_age_hours: float
    kind: str = "sidecar"


DEFAULT_EVIDENCE_REQUIREMENTS: tuple[EvidenceRequirement, ...] = (
    EvidenceRequirement("money-path", "automation/money-path-last-run", "LAST_RUN.md", 30.0),
    EvidenceRequirement(
        "rebalance-micro-gtaa",
        "automation/rebalance-micro-gtaa-last-run",
        "LAST_RUN.md",
        80.0,
    ),
    EvidenceRequirement("kis-smoke", "automation/kis-smoke-last-run", "LAST_RUN.md", 30.0),
    EvidenceRequirement(
        "execution-quality",
        "automation/execution-quality-last-run",
        "execution_quality.json",
        30.0,
        "sidecar-json",
    ),
    EvidenceRequirement("reassign", "automation/reassign-last-run", "LAST_RUN.md", 80.0),
    EvidenceRequirement(
        "pipeline-liveness",
        "automation/pipeline-liveness-last-run",
        "LAST_RUN.md",
        30.0,
    ),
    EvidenceRequirement(
        "rebalance-paper-forward",
        "automation/rebalance-paper-forward-last-run",
        "LAST_RUN.md",
        80.0,
    ),
    EvidenceRequirement("edge-autoarm", "automation/edge-autoarm-last-run", "LAST_RUN.md", 80.0),
    EvidenceRequirement("public-data", "automation/public-data", "LAST_RUN.md", 80.0),
    EvidenceRequirement(
        "regime-stratify",
        "automation/regime-stratify-last-run",
        "LAST_RUN.md",
        80.0,
    ),
    EvidenceRequirement(
        "promote-readiness",
        "automation/promote-readiness-last-run",
        "LAST_RUN.md",
        30.0,
    ),
    EvidenceRequirement(
        "promotion-summary",
        "automation/autonomous-promotion-last-run",
        "promotion_summary.json",
        30.0,
        "sidecar-json",
    ),
)


@dataclass(frozen=True)
class EvolutionDomain:
    key: str
    label_ko: str
    description: str
    default_priority: int
    safety_notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label_ko": self.label_ko,
            "description": self.description,
            "default_priority": self.default_priority,
            "safety_notes": self.safety_notes,
        }


@dataclass(frozen=True)
class EvidenceSurface:
    key: str
    kind: str
    source_ref: str
    observed_at_utc: str | None
    producer_commit: str | None
    freshness_status: str
    summary_ko: str
    machine_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "source_ref": self.source_ref,
            "observed_at_utc": self.observed_at_utc,
            "producer_commit": self.producer_commit,
            "freshness_status": self.freshness_status,
            "summary_ko": self.summary_ko,
            "machine_payload": self.machine_payload,
        }


@dataclass(frozen=True)
class BreakthroughCandidate:
    candidate_id: str
    domain_key: str
    title_ko: str
    problem_ko: str
    evidence_refs: tuple[str, ...]
    expected_benefit: str
    breakthrough_type: str
    growth_leverage: int
    capability_compounding: int
    capital_path_alignment: int
    evidence_confidence: int
    safety_preservation: int
    learning_velocity: int
    repeatability: int
    evidence_dependency: str
    confidence: str
    risk_grade: int
    safety_impact: tuple[str, ...]
    status: str
    next_action_ko: str
    expires_at_utc: str | None = None
    recheck_condition: str | None = None

    @property
    def composite_score(self) -> int:
        return (
            self.growth_leverage
            + self.capability_compounding
            + self.capital_path_alignment
            + self.evidence_confidence
            + self.safety_preservation
            + self.learning_velocity
            + self.repeatability
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "domain_key": self.domain_key,
            "title_ko": self.title_ko,
            "problem_ko": self.problem_ko,
            "evidence_refs": list(self.evidence_refs),
            "expected_benefit": self.expected_benefit,
            "breakthrough_type": self.breakthrough_type,
            "growth_leverage": self.growth_leverage,
            "capability_compounding": self.capability_compounding,
            "capital_path_alignment": self.capital_path_alignment,
            "evidence_confidence": self.evidence_confidence,
            "safety_preservation": self.safety_preservation,
            "learning_velocity": self.learning_velocity,
            "repeatability": self.repeatability,
            "composite_score": self.composite_score,
            "evidence_dependency": self.evidence_dependency,
            "confidence": self.confidence,
            "risk_grade": self.risk_grade,
            "safety_impact": list(self.safety_impact),
            "status": self.status,
            "next_action_ko": self.next_action_ko,
            "expires_at_utc": self.expires_at_utc,
            "recheck_condition": self.recheck_condition,
        }


@dataclass(frozen=True)
class ExperimentPlan:
    experiment_id: str
    candidate_id: str
    goal_ko: str
    non_goals_ko: str
    required_data: tuple[str, ...]
    success_metrics: tuple[str, ...]
    failure_criteria: tuple[str, ...]
    allowed_stage: str
    affected_paths: tuple[str, ...]
    rollback_or_discard_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "candidate_id": self.candidate_id,
            "goal_ko": self.goal_ko,
            "non_goals_ko": self.non_goals_ko,
            "required_data": list(self.required_data),
            "success_metrics": list(self.success_metrics),
            "failure_criteria": list(self.failure_criteria),
            "allowed_stage": self.allowed_stage,
            "affected_paths": list(self.affected_paths),
            "rollback_or_discard_ko": self.rollback_or_discard_ko,
        }


@dataclass(frozen=True)
class EvidencePackage:
    package_id: str
    experiment_id: str
    result: str
    baseline: str
    measurements: Mapping[str, Any]
    limitations_ko: str
    safety_review_ko: str
    recommended_decision: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "experiment_id": self.experiment_id,
            "result": self.result,
            "baseline": self.baseline,
            "measurements": dict(self.measurements),
            "limitations_ko": self.limitations_ko,
            "safety_review_ko": self.safety_review_ko,
            "recommended_decision": self.recommended_decision,
        }


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    decision: str
    next_gate: str | None
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "next_gate": self.next_gate,
            "reason_ko": self.reason_ko,
        }


@dataclass(frozen=True)
class LearningLedgerEntry:
    entry_id: str
    candidate_id: str
    decision: str
    reason_ko: str
    evidence_package_id: str | None
    next_recheck_condition: str | None
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "reason_ko": self.reason_ko,
            "evidence_package_id": self.evidence_package_id,
            "next_recheck_condition": self.next_recheck_condition,
            "created_at_utc": self.created_at_utc,
        }


@dataclass(frozen=True)
class PromotionFailureSignal:
    candidate_id: str
    title_ko: str
    reason_ko: str
    evidence_package_id: str | None


@dataclass(frozen=True)
class EvolutionRunSummary:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    domains: tuple[EvolutionDomain, ...]
    evidence_surfaces: tuple[EvidenceSurface, ...]
    candidates: tuple[BreakthroughCandidate, ...]
    experiment_plans: tuple[ExperimentPlan, ...]
    learning_ledger: tuple[LearningLedgerEntry, ...]
    stale_evidence: tuple[str, ...]

    @property
    def top_breakthrough_candidates(self) -> tuple[str, ...]:
        return tuple(candidate.candidate_id for candidate in self.candidates[:8])

    @property
    def safe_high_leverage_work(self) -> tuple[str, ...]:
        return tuple(
            c.candidate_id
            for c in self.candidates
            if c.status in {STATUS_NEW, STATUS_PLANNED}
            and c.risk_grade <= 2
            and not c.safety_impact
        )

    @property
    def operator_review(self) -> tuple[str, ...]:
        return tuple(
            c.candidate_id
            for c in self.candidates
            if c.status == STATUS_OPERATOR_REVIEW or c.safety_impact
        )

    @property
    def evidence_dependencies(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for candidate in self.candidates:
            if candidate.evidence_dependency == EVIDENCE_NONE:
                continue
            grouped.setdefault(candidate.evidence_dependency, []).append(candidate.candidate_id)
        return grouped

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "top_breakthrough_candidates": list(self.top_breakthrough_candidates),
            "safe_high_leverage_work": list(self.safe_high_leverage_work),
            "evidence_dependencies": self.evidence_dependencies,
            "operator_review": list(self.operator_review),
            "stale_evidence": list(self.stale_evidence),
            "domains": [domain.to_dict() for domain in self.domains],
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "experiment_plans": [plan.to_dict() for plan in self.experiment_plans],
            "learning_ledger": [entry.to_dict() for entry in self.learning_ledger],
        }

    def as_markdown(self) -> str:
        lines = [
            "# 자율 성장 루프 최신 실행",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| schema_version | {self.schema_version} |",
            f"| run_id | {self.run_id} |",
            f"| commit | {self.commit} |",
            f"| timestamp_utc | {self.timestamp_utc} |",
            f"| overall_status | {self.overall_status} |",
            "",
            "## 상위 고레버리지 돌파 후보",
            "",
        ]
        for idx, candidate in enumerate(self.candidates[:8], start=1):
            lines.append(
                f"{idx}. **{candidate.title_ko}** "
                f"(`{candidate.candidate_id}`, 점수 {candidate.composite_score})"
            )
            lines.append(f"   - 다음 행동: {candidate.next_action_ko}")
            lines.append(
                "   - 기준: "
                f"수익력 {candidate.growth_leverage}, "
                f"증거 {candidate.evidence_confidence}, "
                f"자본 경로 {candidate.capital_path_alignment}, "
                f"학습 복리 {candidate.capability_compounding}"
            )
        lines += [
            "",
            "## 안전한 고레버리지 작업",
            "",
        ]
        if self.safe_high_leverage_work:
            for candidate_id in self.safe_high_leverage_work[:8]:
                candidate = _candidate_by_id(self.candidates, candidate_id)
                lines.append(f"- `{candidate_id}` — {candidate.title_ko}")
        else:
            lines.append("- 없음")
        lines += [
            "",
            "## 증거 의존성",
            "",
        ]
        if self.evidence_dependencies:
            for dependency, ids in sorted(self.evidence_dependencies.items()):
                lines.append(
                    f"- `{dependency}`: {', '.join(f'`{candidate_id}`' for candidate_id in ids)}"
                )
        else:
            lines.append("- 없음")
        lines += [
            "",
            "## 안전 경계 검토",
            "",
        ]
        if self.operator_review:
            for candidate_id in self.operator_review:
                candidate = _candidate_by_id(self.candidates, candidate_id)
                impacts = ", ".join(candidate.safety_impact) or "operator_review"
                lines.append(f"- `{candidate_id}` — {candidate.title_ko} ({impacts})")
        else:
            lines.append("- 없음")
        lines += [
            "",
            "## 오래되었거나 누락된 증거",
            "",
        ]
        if self.stale_evidence:
            for key in self.stale_evidence:
                lines.append(f"- `{key}`")
        else:
            lines.append("- 없음")
        lines += [
            "",
            "## 안전 문구",
            "",
            "읽기 전용 실행입니다. 주문, 자본, whitelist, caps, live 전략은 변경하지 않았습니다.",
        ]
        text = "\n".join(lines)
        assert_no_secret_like_values(text)
        return text


def default_domains() -> tuple[EvolutionDomain, ...]:
    return (
        EvolutionDomain(
            "data_collection",
            "데이터 수집",
            "가격·거시·브로커·sidecar 입력 수집 경로",
            10,
            "새 외부 비용 또는 비밀값은 운영자 검토",
        ),
        EvolutionDomain(
            "data_quality",
            "데이터 품질",
            "신선도·출처·교차 검증",
            20,
            "오래된 증거는 성과 실패로 보지 않음",
        ),
        EvolutionDomain(
            "analysis", "분석", "레짐·성과·강건성 분석", 30, "측정 전용, 거래 변경 금지"
        ),
        EvolutionDomain(
            "strategy_design",
            "전략 설계",
            "후보 전략과 엣지 검증",
            40,
            "live 전략 교체는 스펙 055만",
        ),
        EvolutionDomain(
            "portfolio_design",
            "포트폴리오 설계",
            "비상관·자산 배분·재지정 후보",
            50,
            "whitelist/caps 확대 금지",
        ),
        EvolutionDomain(
            "execution_quality",
            "실행 품질",
            "주문 거부·체결 품질·브로커 오류",
            60,
            "주문 재시도/취소 직접 실행 금지",
        ),
        EvolutionDomain(
            "live_readiness",
            "실시간 매매 준비도",
            "money-path·무장·게이트 상태",
            70,
            "자본 사다리 우회 금지",
        ),
        EvolutionDomain(
            "review", "회고", "학습 장부·폐기 조건·재검토 조건", 80, "감사 로그 삭제 금지"
        ),
        EvolutionDomain(
            "agent_ops",
            "에이전트 운영 품질",
            "handoff·하네스·자동화 생존",
            90,
            "운영 체계 변경은 등급 2 이상",
        ),
    )


def parse_timestamp_utc(text: str | None) -> str | None:
    if not text:
        return None
    match = _TS_RE.search(text)
    return match.group(1) if match else None


def mask_sensitive_values(text: str) -> str:
    masked = text
    for pattern in _SECRET_PATTERNS:
        if "Bearer" in pattern.pattern:
            masked = pattern.sub("Bearer <MASKED>", masked)
        elif "d{8" in pattern.pattern:
            masked = pattern.sub("<ACCOUNT_MASKED>", masked)
        else:
            masked = pattern.sub(lambda m: f"{m.group(1)}=<MASKED>", masked)
    return masked


def assert_no_secret_like_values(text: str) -> None:
    if mask_sensitive_values(text) != text:
        raise ValueError("secret-like or account-sensitive value detected in output")


def classify_safety_surfaces(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    found: list[str] = []
    for surface, keywords in _SAFETY_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            found.append(surface)
    return tuple(found)


def risk_grade_for_surfaces(surfaces: Sequence[str]) -> int:
    if not surfaces:
        return 2
    if any(s in surfaces for s in ("orders", "capital", "whitelist", "caps", "live_strategy")):
        return 4
    if any(s in surfaces for s in ("secrets", "deploy", "kernel", "paid_service")):
        return 3
    return 2


def build_evidence_surfaces(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    requirements: Sequence[EvidenceRequirement] = DEFAULT_EVIDENCE_REQUIREMENTS,
) -> tuple[EvidenceSurface, ...]:
    surfaces: list[EvidenceSurface] = []
    seen: set[str] = set()
    for req in requirements:
        seen.add(req.key)
        raw = evidence_texts.get(req.key)
        surfaces.append(_surface_from_text(req, raw, now))
    for key in sorted(set(evidence_texts) - seen):
        req = EvidenceRequirement(key, key, f"{key}.md", 80.0, "manual_note")
        surfaces.append(_surface_from_text(req, evidence_texts.get(key), now))
    return tuple(surfaces)


def scan_evolution(
    evidence_texts: Mapping[str, str | None],
    *,
    ledger_doc: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    commit: str = "unknown",
    run_id: str = "local",
) -> EvolutionRunSummary:
    now = _ensure_utc(now or datetime.now(UTC))
    timestamp = _iso(now)
    domains = default_domains()
    surfaces = build_evidence_surfaces(evidence_texts, now=now)
    candidates = _generate_candidates(surfaces)
    ledger_entries = parse_learning_ledger(ledger_doc)
    promotion_failures = parse_promotion_failure_signals(evidence_texts.get("promotion-summary"))
    candidates = apply_promotion_failure_signals(candidates, promotion_failures)
    candidates = apply_learning_ledger(candidates, ledger_entries)
    plans = tuple(generate_experiment_plan(candidate) for candidate in candidates)
    ledger_entries = update_learning_ledger(
        ledger_entries,
        candidates,
        timestamp,
        promotion_failures=promotion_failures,
    )
    stale = tuple(
        surface.key
        for surface in surfaces
        if surface.freshness_status in {"late", "stale", "missing"}
    )
    if any(candidate.status == STATUS_OPERATOR_REVIEW for candidate in candidates) or stale:
        overall = OVERALL_DEGRADED
    else:
        overall = OVERALL_OK
    return EvolutionRunSummary(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        overall_status=overall,
        domains=domains,
        evidence_surfaces=surfaces,
        candidates=candidates,
        experiment_plans=plans,
        learning_ledger=ledger_entries,
        stale_evidence=stale,
    )


def generate_experiment_plan(candidate: BreakthroughCandidate) -> ExperimentPlan:
    if candidate.status == STATUS_OPERATOR_REVIEW:
        allowed_stage = "operator_review"
    elif candidate.evidence_dependency == EVIDENCE_MARKET_OBSERVATION:
        allowed_stage = "read_only"
    elif candidate.breakthrough_type in {"profit_power", "capital_path"}:
        allowed_stage = "backtest"
    else:
        allowed_stage = "read_only"

    success = [
        "사전 선언한 비교 기준 대비 개선",
        "증거 출처와 한계가 evidence package에 기록됨",
        "주문·자본·whitelist·caps·live 전략 직접 변경 없음",
    ]
    failure = [
        "표본 부족 또는 기준선 대비 우위 없음",
        "안전 경계가 필요하면 자동 승격 중단",
    ]
    if candidate.evidence_dependency == EVIDENCE_MARKET_OBSERVATION:
        failure.append("추가 관측 전에는 변경 계획으로 승격하지 않음")

    return ExperimentPlan(
        experiment_id=_stable_id("exp", candidate.candidate_id),
        candidate_id=candidate.candidate_id,
        goal_ko=f"{candidate.title_ko}가 장기 성장 능력을 높이는지 검증한다.",
        non_goals_ko="실주문, 자본 증액, 허용 종목 확대, 한도 완화, live 전략 교체는 비목표다.",
        required_data=candidate.evidence_refs,
        success_metrics=tuple(success),
        failure_criteria=tuple(failure),
        allowed_stage=allowed_stage,
        affected_paths=("src/auto_invest/analytics/evolution_loop.py",),
        rollback_or_discard_ko="기준 미달이면 학습 장부에 폐기 또는 증거 의존 상태로 남긴다.",
    )


def decide_promotion(
    candidate: BreakthroughCandidate,
    package: EvidencePackage,
) -> PromotionDecision:
    impacts = set(candidate.safety_impact)
    if "live_strategy" in impacts:
        return PromotionDecision(
            candidate.candidate_id,
            DECISION_FEED_EXISTING_GATE,
            "spec-055-autonomous-reassignment",
            "live 전략 교체는 기존 5중 재지정 게이트로만 보낸다.",
        )
    if "capital" in impacts:
        return PromotionDecision(
            candidate.candidate_id,
            DECISION_FEED_EXISTING_GATE,
            "spec-050-capital-ladder",
            "자본 확대는 기존 자본 사다리와 운영자 낙폭 예산 밖에서 처리하지 않는다.",
        )
    if impacts:
        return PromotionDecision(
            candidate.candidate_id,
            DECISION_OPERATOR_REVIEW,
            None,
            "안전 경계 후보라 자동 승격하지 않는다.",
        )
    if package.result == "pass":
        return PromotionDecision(
            candidate.candidate_id,
            DECISION_CREATE_SPEC if candidate.risk_grade >= 2 else DECISION_OPEN_PR,
            None,
            "사전 기준을 통과했으므로 구현 작업으로 승격 가능하다.",
        )
    if package.result == "fail":
        return PromotionDecision(candidate.candidate_id, DECISION_DISCARD, None, "실패 기준 충족")
    return PromotionDecision(
        candidate.candidate_id, DECISION_OBSERVE, None, "증거가 아직 부족하다."
    )


def parse_learning_ledger(doc: Mapping[str, Any] | None) -> tuple[LearningLedgerEntry, ...]:
    if not isinstance(doc, Mapping):
        return ()
    raw_entries = doc.get("entries") or doc.get("records") or []
    entries: list[LearningLedgerEntry] = []
    if not isinstance(raw_entries, list):
        return ()
    for item in raw_entries:
        if not isinstance(item, Mapping):
            continue
        candidate_id = str(item.get("candidate_id") or "").strip()
        decision = str(item.get("decision") or "").strip()
        if not candidate_id or not decision:
            continue
        entries.append(
            LearningLedgerEntry(
                entry_id=str(item.get("entry_id") or _stable_id("ledger", candidate_id, decision)),
                candidate_id=candidate_id,
                decision=decision,
                reason_ko=str(item.get("reason_ko") or ""),
                evidence_package_id=_none_if_blank(item.get("evidence_package_id")),
                next_recheck_condition=_none_if_blank(item.get("next_recheck_condition")),
                created_at_utc=str(item.get("created_at_utc") or ""),
            )
        )
    return tuple(entries)


def parse_promotion_failure_signals(raw: str | None) -> tuple[PromotionFailureSignal, ...]:
    if not raw:
        return ()
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if not isinstance(doc, Mapping):
        return ()
    run_id = _none_if_blank(doc.get("run_id"))
    evidence_package_id = f"autonomous-promotion:{run_id}" if run_id else "autonomous-promotion"
    raw_assessments = doc.get("assessments")
    if not isinstance(raw_assessments, list):
        return ()
    signals: list[PromotionFailureSignal] = []
    seen: set[str] = set()
    for assessment in raw_assessments:
        if not isinstance(assessment, Mapping):
            continue
        if str(assessment.get("stage") or "").strip().upper() != "DISCARD":
            continue
        candidate = assessment.get("candidate")
        candidate_doc = candidate if isinstance(candidate, Mapping) else {}
        domain_key = str(candidate_doc.get("domain_key") or "").strip()
        if domain_key not in {"strategy_design", "portfolio_design"}:
            continue
        candidate_id = str(
            assessment.get("candidate_id") or candidate_doc.get("candidate_id") or ""
        ).strip()
        if not candidate_id or candidate_id in seen:
            continue
        reason = str(
            assessment.get("blocked_reason_ko")
            or assessment.get("allowed_next_action")
            or "promotion loop에서 DISCARD로 판정됐다."
        )
        title = str(candidate_doc.get("title_ko") or candidate_id)
        signals.append(
            PromotionFailureSignal(
                candidate_id=candidate_id,
                title_ko=mask_sensitive_values(title),
                reason_ko=mask_sensitive_values(reason),
                evidence_package_id=evidence_package_id,
            )
        )
        seen.add(candidate_id)
    return tuple(signals)


def apply_promotion_failure_signals(
    candidates: Sequence[BreakthroughCandidate],
    failures: Sequence[PromotionFailureSignal],
) -> tuple[BreakthroughCandidate, ...]:
    if not failures:
        return tuple(candidates)
    failure_by_id = {failure.candidate_id: failure for failure in failures}
    updated: list[BreakthroughCandidate] = []
    for candidate in candidates:
        failure = failure_by_id.get(candidate.candidate_id)
        if failure is None:
            updated.append(candidate)
            continue
        updated.append(
            replace(
                candidate,
                status=STATUS_REJECTED,
                next_action_ko=failure.reason_ko,
                recheck_condition=None,
            )
        )
    return tuple(_sort_candidates(updated))


def apply_learning_ledger(
    candidates: Sequence[BreakthroughCandidate],
    entries: Sequence[LearningLedgerEntry],
) -> tuple[BreakthroughCandidate, ...]:
    by_candidate: dict[str, LearningLedgerEntry] = {}
    for entry in entries:
        by_candidate[entry.candidate_id] = entry
    updated: list[BreakthroughCandidate] = []
    for candidate in candidates:
        entry = by_candidate.get(candidate.candidate_id)
        if entry and entry.decision == "rejected" and not entry.next_recheck_condition:
            updated.append(replace(candidate, status=STATUS_REJECTED))
        else:
            updated.append(candidate)
    return tuple(_sort_candidates(updated))


def update_learning_ledger(
    existing: Sequence[LearningLedgerEntry],
    candidates: Sequence[BreakthroughCandidate],
    timestamp_utc: str,
    *,
    promotion_failures: Sequence[PromotionFailureSignal] = (),
) -> tuple[LearningLedgerEntry, ...]:
    entries = list(existing)
    seen = {(entry.candidate_id, entry.decision) for entry in entries}
    failure_by_id = {failure.candidate_id: failure for failure in promotion_failures}
    for candidate in candidates:
        if candidate.status not in {
            STATUS_REJECTED,
            STATUS_OPERATOR_REVIEW,
            STATUS_EVIDENCE_DEPENDENT,
        }:
            continue
        decision = (
            "rejected"
            if candidate.status == STATUS_REJECTED
            else (
                "evidence_dependent"
                if candidate.status == STATUS_EVIDENCE_DEPENDENT
                else "operator_review"
            )
        )
        key = (candidate.candidate_id, decision)
        if key in seen:
            continue
        failure = failure_by_id.get(candidate.candidate_id) if decision == "rejected" else None
        reason_ko = failure.reason_ko if failure else candidate.next_action_ko
        evidence_package_id = failure.evidence_package_id if failure else None
        entries.append(
            LearningLedgerEntry(
                entry_id=_stable_id("ledger", candidate.candidate_id, decision),
                candidate_id=candidate.candidate_id,
                decision=decision,
                reason_ko=reason_ko,
                evidence_package_id=evidence_package_id,
                next_recheck_condition=candidate.recheck_condition,
                created_at_utc=timestamp_utc,
            )
        )
        seen.add(key)
    for failure in promotion_failures:
        key = (failure.candidate_id, "rejected")
        if key in seen:
            continue
        entries.append(
            LearningLedgerEntry(
                entry_id=_stable_id("ledger", failure.candidate_id, "rejected"),
                candidate_id=failure.candidate_id,
                decision="rejected",
                reason_ko=failure.reason_ko,
                evidence_package_id=failure.evidence_package_id,
                next_recheck_condition=None,
                created_at_utc=timestamp_utc,
            )
        )
        seen.add(key)
    return tuple(entries)


def ledger_document(entries: Sequence[LearningLedgerEntry]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "entries": [entry.to_dict() for entry in entries],
    }


def candidate_backlog_document(candidates: Sequence[BreakthroughCandidate]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidates": [candidate.to_dict() for candidate in candidates],
    }


def write_summary_artifacts(
    summary: EvolutionRunSummary,
    *,
    summary_out: Path | None = None,
    json_out: Path | None = None,
    ledger_out: Path | None = None,
    candidate_backlog_out: Path | None = None,
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
    if ledger_out is not None:
        ledger_out.parent.mkdir(parents=True, exist_ok=True)
        ledger_out.write_text(
            json.dumps(ledger_document(summary.learning_ledger), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
    if candidate_backlog_out is not None:
        candidate_backlog_out.parent.mkdir(parents=True, exist_ok=True)
        candidate_backlog_out.write_text(
            json.dumps(
                candidate_backlog_document(summary.candidates),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _surface_from_text(
    req: EvidenceRequirement,
    raw: str | None,
    now: datetime,
) -> EvidenceSurface:
    if not raw:
        return EvidenceSurface(
            key=req.key,
            kind=req.kind,
            source_ref=f"{req.branch}:{req.filename}",
            observed_at_utc=None,
            producer_commit=None,
            freshness_status="missing",
            summary_ko="증거 없음",
            machine_payload={"signals": []},
        )
    ts = parse_timestamp_utc(raw)
    freshness = _freshness(ts, now, req.max_age_hours)
    signals = _signals(req.key, raw)
    return EvidenceSurface(
        key=req.key,
        kind=req.kind,
        source_ref=f"{req.branch}:{req.filename}",
        observed_at_utc=ts,
        producer_commit=_producer_commit(raw),
        freshness_status=freshness,
        summary_ko=mask_sensitive_values(_summary_for(req.key, raw, freshness, signals)),
        machine_payload={"signals": sorted(signals)},
    )


def _generate_candidates(
    surfaces: Sequence[EvidenceSurface],
) -> tuple[BreakthroughCandidate, ...]:
    by_key = {surface.key: surface for surface in surfaces}
    stale = [s.key for s in surfaces if s.freshness_status in {"late", "stale", "missing"}]
    signals = {s.key: set(s.machine_payload.get("signals") or []) for s in surfaces}
    candidates = [
        _candidate(
            "data_collection",
            "공개 데이터 수집·교차 검증 확장",
            _problem_for_data_collection(by_key, stale),
            ("public-data",),
            "evidence_quality",
            "evidence_quality",
            62,
            75,
            35,
            _confidence_score(by_key.get("public-data")),
            90,
            68,
            78,
            EVIDENCE_SIDECAR_FRESHNESS if "public-data" in stale else EVIDENCE_NONE,
            "공개 데이터 sidecar 신선도와 교차 검증 범위를 먼저 확인한다.",
        ),
        _candidate(
            "data_quality",
            "오래된 증거와 성과 실패 분리",
            "누락·stale 증거를 전략 실패로 오해하지 않게 증거 출처와 생산 커밋을 먼저 분리한다.",
            tuple(stale) if stale else ("pipeline-liveness",),
            "reliability",
            "evidence_quality",
            58,
            82,
            45,
            70 if stale else 84,
            95,
            72,
            88,
            EVIDENCE_SIDECAR_FRESHNESS if stale else EVIDENCE_NONE,
            "stale evidence 목록을 후보와 별도 관측 이슈로 보고한다.",
        ),
        _analysis_candidate(by_key, stale, signals),
        _strategy_candidate(by_key, signals),
        _portfolio_candidate(by_key, signals),
        _execution_candidate(by_key, stale, signals),
        _live_readiness_candidate(by_key, signals),
        _candidate(
            "review",
            "학습 장부로 폐기·보류 후보 재발굴 차단",
            "반복 조사 비용을 줄이려면 채택·폐기·증거 의존 상태를 구조화해야 한다.",
            ("handoff", "pipeline-liveness"),
            "operator_time",
            "operator_leverage",
            50,
            92,
            55,
            82,
            95,
            90,
            95,
            EVIDENCE_NONE,
            "후보 상태를 learning_ledger.json에 기록하고 재검토 조건을 남긴다.",
        ),
        _agent_ops_candidate(by_key, stale),
    ]
    return tuple(_sort_candidates(candidates))


def _strategy_candidate(
    by_key: Mapping[str, EvidenceSurface],
    signals: Mapping[str, set[str]],
) -> BreakthroughCandidate:
    micro = signals.get("rebalance-micro-gtaa", set())
    money = signals.get("money-path", set())
    if "latest_intent_loss" in micro or "preview_only" in money:
        title = "micro GTAA 의도 손익 재검토와 대체 전략 연구"
        problem = (
            "현재 돈 경로가 PREVIEW_ONLY 또는 latest_intent_loss에 묶여 있으므로, "
            "실주문 재개가 아니라 전략 증거 재검토와 대체 후보 연구가 먼저다."
        )
        dependency = EVIDENCE_NEW_EXPERIMENT
        confidence = _confidence_score(by_key.get("rebalance-micro-gtaa"))
        growth = 92
    else:
        title = "전략 후보군 고레버리지 재평가"
        problem = "현재 후보 전략을 장기 수익력과 증거 신뢰도 기준으로 재정렬한다."
        dependency = EVIDENCE_NONE
        confidence = 72
        growth = 78
    return _candidate(
        "strategy_design",
        title,
        problem,
        ("money-path", "rebalance-micro-gtaa", "rebalance-paper-forward"),
        "profit",
        "profit_power",
        growth,
        86,
        88,
        confidence,
        92,
        88,
        86,
        dependency,
        "read-only 전략 증거 패키지를 만들고 새 전략은 backtest부터 시작한다.",
    )


def _analysis_candidate(
    by_key: Mapping[str, EvidenceSurface],
    stale: Sequence[str],
    signals: Mapping[str, set[str]],
) -> BreakthroughCandidate:
    evidence_refs = ("regime-stratify", "public-data", "promote-readiness")
    stale_or_missing = set(evidence_refs) & set(stale)
    performance_signals = signals.get("promote-readiness", set())
    setup_error = "setup_error" in performance_signals
    evidence_dependency = (
        EVIDENCE_SIDECAR_FRESHNESS if stale_or_missing or setup_error else EVIDENCE_NONE
    )
    valid_performance = evidence_dependency == EVIDENCE_NONE and bool(
        {"performance_ready", "performance_not_ready"} & performance_signals
    )
    evidence_confidence = min(_confidence_score(by_key.get(key)) for key in evidence_refs)
    if setup_error:
        evidence_confidence = min(evidence_confidence, 42)
    growth_leverage = 74 if valid_performance else 70
    learning_velocity = 88 if valid_performance else 82
    next_action = (
        "레짐·성과 sidecar를 후보 스코어 입력으로 쓰는 실험을 설계한다."
        if evidence_dependency == EVIDENCE_NONE
        else "레짐·성과 점수 입력 전에 promote-readiness와 분석 sidecar 신선도를 복구·재확인한다."
    )
    return _candidate(
        "analysis",
        "레짐·성과 분석을 후보 점수화 입력으로 승격",
        "분석 결과가 대화에 머물지 않고 후보 점수화의 증거 신뢰도와 "
        "성장 레버리지로 들어가야 한다.",
        evidence_refs,
        "profit",
        "learning_velocity",
        growth_leverage,
        80,
        58,
        evidence_confidence,
        92,
        learning_velocity,
        82,
        evidence_dependency,
        next_action,
    )


def _execution_candidate(
    by_key: Mapping[str, EvidenceSurface],
    stale: Sequence[str],
    signals: Mapping[str, set[str]],
) -> BreakthroughCandidate:
    quality = by_key.get("execution-quality")
    dependency = (
        EVIDENCE_SIDECAR_FRESHNESS
        if quality is None or "execution-quality" in stale
        else EVIDENCE_NONE
    )
    next_action = (
        "execution-quality sidecar 신선도를 회복한 뒤 거부 주문 기회손익과 "
        "브로커 오류율을 읽기 전용으로 증거 패키징한다."
        if dependency == EVIDENCE_SIDECAR_FRESHNESS
        else "execution-quality sidecar의 거부 주문 기회손익과 브로커 오류율을 "
        "읽기 전용으로 증거 패키징한다."
    )
    return _candidate(
        "execution_quality",
        "주문 거부·체결 품질 손익 관측",
        _problem_for_execution(signals),
        ("execution-quality", "rebalance-micro-gtaa", "kis-smoke"),
        "risk_reduction",
        "execution_quality",
        70,
        65,
        70,
        _confidence_score(quality),
        90,
        74,
        72,
        dependency,
        next_action,
    )


def _portfolio_candidate(
    by_key: Mapping[str, EvidenceSurface],
    signals: Mapping[str, set[str]],
) -> BreakthroughCandidate:
    reassign = signals.get("reassign", set())
    forward = signals.get("rebalance-paper-forward", set())
    dependency = (
        EVIDENCE_MARKET_OBSERVATION
        if "premature" in reassign or "insufficient_data" in forward
        else EVIDENCE_NONE
    )
    status = STATUS_EVIDENCE_DEPENDENT if dependency == EVIDENCE_MARKET_OBSERVATION else STATUS_NEW
    return _candidate(
        "portfolio_design",
        "비상관 포트폴리오 후보 비교력 강화",
        "비교 가능한 후보가 부족하면 재지정을 앞당기지 말고 후보 비교와 증거 누적 품질을 높인다.",
        ("reassign", "rebalance-paper-forward"),
        "profit",
        "profit_power",
        84,
        82,
        78,
        min(
            _confidence_score(by_key.get("reassign")),
            _confidence_score(by_key.get("rebalance-paper-forward")),
        ),
        90,
        74,
        80,
        dependency,
        "후보별 전진 관측·상관·낙폭을 같은 기준으로 묶는 실험을 설계한다.",
        status=status,
        recheck_condition="후보가 COMPARABLE 관측 수에 도달하면 재검토",
    )


def _live_readiness_candidate(
    by_key: Mapping[str, EvidenceSurface],
    signals: Mapping[str, set[str]],
) -> BreakthroughCandidate:
    money = signals.get("money-path", set())
    dependency = EVIDENCE_NEW_EXPERIMENT if "preview_only" in money else EVIDENCE_NONE
    return _candidate(
        "live_readiness",
        "돈 경로 준비도와 기존 게이트 정렬",
        "실제 돈 경로는 기존 money-path, 스펙 055 재지정, "
        "스펙 050 자본 사다리 밖에서 열면 안 된다.",
        ("money-path", "edge-autoarm", "reassign"),
        "risk_reduction",
        "capital_path",
        82,
        78,
        95,
        _confidence_score(by_key.get("money-path")),
        96,
        78,
        82,
        dependency,
        "돈 경로 상태를 단일 evidence package로 묶고 기존 게이트로만 승격한다.",
    )


def _agent_ops_candidate(
    by_key: Mapping[str, EvidenceSurface],
    stale: Sequence[str],
) -> BreakthroughCandidate:
    dependency = EVIDENCE_SIDECAR_FRESHNESS if "pipeline-liveness" in stale else EVIDENCE_NONE
    return _candidate(
        "agent_ops",
        "자율 루프 sidecar와 handoff 생존성",
        "자동 성장 루프가 멈추거나 handoff가 stale이면 다음 세션이 같은 판단을 반복한다.",
        ("pipeline-liveness", "handoff"),
        "operator_time",
        "operator_leverage",
        55,
        88,
        60,
        _confidence_score(by_key.get("pipeline-liveness")),
        95,
        92,
        92,
        dependency,
        "autonomous-evolution sidecar를 pipeline liveness에 등록하고 "
        "handoff에 단일 진입점을 남긴다.",
    )


def _candidate(
    domain_key: str,
    title_ko: str,
    problem_ko: str,
    evidence_refs: Sequence[str],
    expected_benefit: str,
    breakthrough_type: str,
    growth_leverage: int,
    capability_compounding: int,
    capital_path_alignment: int,
    evidence_confidence: int,
    safety_preservation: int,
    learning_velocity: int,
    repeatability: int,
    evidence_dependency: str,
    next_action_ko: str,
    *,
    status: str | None = None,
    recheck_condition: str | None = None,
) -> BreakthroughCandidate:
    safety_impact = classify_safety_surfaces(f"{title_ko}\n{problem_ko}\n{next_action_ko}")
    risk_grade = risk_grade_for_surfaces(safety_impact)
    if status is None:
        if safety_impact:
            status = STATUS_OPERATOR_REVIEW
        elif evidence_dependency in {EVIDENCE_MARKET_OBSERVATION, EVIDENCE_SIDECAR_FRESHNESS}:
            status = STATUS_EVIDENCE_DEPENDENT
        else:
            status = STATUS_NEW
    confidence = (
        "high" if evidence_confidence >= 80 else "medium" if evidence_confidence >= 55 else "low"
    )
    return BreakthroughCandidate(
        candidate_id=_stable_id("candidate", domain_key, title_ko, problem_ko),
        domain_key=domain_key,
        title_ko=title_ko,
        problem_ko=problem_ko,
        evidence_refs=tuple(evidence_refs),
        expected_benefit=expected_benefit,
        breakthrough_type=breakthrough_type,
        growth_leverage=growth_leverage,
        capability_compounding=capability_compounding,
        capital_path_alignment=capital_path_alignment,
        evidence_confidence=evidence_confidence,
        safety_preservation=safety_preservation,
        learning_velocity=learning_velocity,
        repeatability=repeatability,
        evidence_dependency=evidence_dependency,
        confidence=confidence,
        risk_grade=risk_grade,
        safety_impact=safety_impact,
        status=status,
        next_action_ko=next_action_ko,
        recheck_condition=recheck_condition,
    )


def _sort_candidates(
    candidates: Sequence[BreakthroughCandidate],
) -> list[BreakthroughCandidate]:
    return sorted(
        candidates,
        key=lambda c: (
            c.status == STATUS_OPERATOR_REVIEW,
            -c.composite_score,
            c.risk_grade,
            c.domain_key,
            c.candidate_id,
        ),
    )


def _summary_for(key: str, raw: str, freshness: str, signals: set[str]) -> str:
    if key == "execution-quality":
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            doc = None
        if isinstance(doc, Mapping):
            monitor = doc.get("opportunity_monitor")
            rejections = doc.get("broker_rejections")
            broker_errors = (
                rejections.get("parsed_broker_errors")
                if isinstance(rejections, Mapping)
                else "?"
            )
            return (
                f"execution-quality: {freshness}, "
                f"status={doc.get('overall_status', '?')}, "
                f"verdict={monitor.get('verdict', '?') if isinstance(monitor, Mapping) else '?'}, "
                f"broker_errors={broker_errors}"
            )
    if key == "kis-smoke":
        state = "success" if "smoke_state | success" in raw.lower() else "unknown"
        return f"kis-smoke: {freshness}, state={state}, {len(raw)} chars"
    signal_text = ", ".join(sorted(signals)) if signals else "특이 신호 없음"
    return f"{key}: {freshness}, {signal_text}, {len(raw)} chars"


def _signals(key: str, raw: str) -> set[str]:
    lowered = raw.lower()
    signals: set[str] = set()
    checks = {
        "preview_only": ("preview_only", "armed:false", "armed (무장 여부) | false"),
        "real_order_path_armed": ("real_order_path_armed", "armed:true"),
        "latest_intent_loss": ("latest_intent_loss", "intent_loss"),
        "rejected_order": ("rejected_by_broker", "rejected order", "주문 거부"),
        "insufficient_data": ("insufficient_data", "premature", "관측 부족"),
        "premature": ("premature", "관측 전", "최소 관측"),
        "degraded": ("degraded", "critical", "stale", "missing"),
        "edge_confirmed": ("edge_confirmed",),
        "hold": ("hold",),
    }
    for signal, needles in checks.items():
        if any(needle in lowered for needle in needles):
            signals.add(signal)
    if key == "pipeline-liveness" and "ok" in lowered and not {"degraded", "critical"} & signals:
        signals.add("liveness_ok")
    if key == "kis-smoke":
        if "smoke_state | success" in lowered or '"smoke_state": "success"' in lowered:
            signals.add("broker_smoke_success")
        if "smoke_exit | 0" not in lowered and "smoke_state" in lowered:
            signals.add("broker_smoke_attention")
    if key == "execution-quality":
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            doc = None
        if isinstance(doc, Mapping):
            status = str(doc.get("overall_status") or "").lower()
            if status == "strategy_review":
                signals.add("strategy_review")
            if status == "execution_review":
                signals.add("execution_review")
            monitor = doc.get("opportunity_monitor")
            if isinstance(monitor, Mapping):
                latest = str(monitor.get("latest_signal") or "").lower()
                if latest == "intent_loss":
                    signals.add("latest_intent_loss")
                if latest == "intent_gain":
                    signals.add("latest_intent_gain")
            rejections = doc.get("broker_rejections")
            if isinstance(rejections, Mapping):
                try:
                    if int(rejections.get("parsed_broker_errors") or 0) > 0:
                        signals.add("broker_rejection_error")
                        signals.add("rejected_order")
                except (TypeError, ValueError):
                    pass
            smoke = doc.get("broker_smoke")
            if isinstance(smoke, Mapping) and smoke.get("smoke_state") == "success":
                signals.add("broker_smoke_success")
    if key == "promote-readiness":
        if re.search(r"ready\s*\([^)]*\)\s*\|\s*true", lowered) or re.search(
            r"\bready\b[^|\n]*\|\s*true", lowered
        ):
            signals.add("performance_ready")
        if re.search(r"ready\s*\([^)]*\)\s*\|\s*false", lowered) or re.search(
            r"\bready\b[^|\n]*\|\s*false", lowered
        ):
            signals.add("performance_not_ready")
        exit_match = re.search(r"ssh_exit\s*\|\s*([0-9]+)", lowered)
        if exit_match and exit_match.group(1) not in {"0", "1"}:
            signals.add("setup_error")
    return signals


def _freshness(ts: str | None, now: datetime, max_age_hours: float) -> str:
    if ts is None:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    parsed = _ensure_utc(parsed)
    age = (now - parsed).total_seconds() / 3600.0
    if age <= max_age_hours:
        return "fresh"
    if age <= 2 * max_age_hours:
        return "late"
    return "stale"


def _producer_commit(raw: str) -> str | None:
    for line in raw.splitlines():
        if "commit" not in line.lower():
            continue
        match = re.search(r"\b[0-9a-f]{7,40}\b", line)
        if match:
            return match.group(0)
    return None


def _problem_for_data_collection(
    by_key: Mapping[str, EvidenceSurface], stale: Sequence[str]
) -> str:
    if "public-data" in stale:
        return "공개 데이터 수집 sidecar가 늦거나 누락되어 분석 입력의 현재성을 먼저 회복해야 한다."
    if "public-data" in by_key:
        return (
            "공개 데이터 채널은 존재하므로 교차 검증과 레짐 입력을 "
            "후보 점수화에 더 잘 연결할 수 있다."
        )
    return "공개 데이터 증거가 없어 수집 경로 존재 여부부터 확인해야 한다."


def _problem_for_execution(signals: Mapping[str, set[str]]) -> str:
    micro = signals.get("rebalance-micro-gtaa", set())
    quality = signals.get("execution-quality", set())
    if "rejected_order" in micro or quality & {
        "latest_intent_loss",
        "latest_intent_gain",
        "broker_rejection_error",
        "strategy_review",
        "execution_review",
    }:
        return "최근 주문 거부가 있으므로 체결 품질과 기회손익을 읽기 전용으로 분석해야 한다."
    return "실행 품질은 주문 거부, 브로커 오류, 체결 품질 증거를 계속 누적해야 한다."


def _confidence_score(surface: EvidenceSurface | None) -> int:
    if surface is None:
        return 35
    return {
        "fresh": 86,
        "late": 62,
        "stale": 42,
        "missing": 20,
        "unknown": 55,
    }.get(surface.freshness_status, 55)


def _stable_id(prefix: str, *parts: object) -> str:
    text = "\n".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}"


def _candidate_by_id(
    candidates: Sequence[BreakthroughCandidate],
    candidate_id: str,
) -> BreakthroughCandidate:
    for candidate in candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise KeyError(candidate_id)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _ensure_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _none_if_blank(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "DEFAULT_EVIDENCE_REQUIREMENTS",
    "SCHEMA_VERSION",
    "BreakthroughCandidate",
    "EvidencePackage",
    "EvidenceRequirement",
    "EvidenceSurface",
    "EvolutionDomain",
    "EvolutionRunSummary",
    "ExperimentPlan",
    "LearningLedgerEntry",
    "PromotionDecision",
    "PromotionFailureSignal",
    "apply_learning_ledger",
    "apply_promotion_failure_signals",
    "assert_no_secret_like_values",
    "build_evidence_surfaces",
    "candidate_backlog_document",
    "classify_safety_surfaces",
    "decide_promotion",
    "default_domains",
    "generate_experiment_plan",
    "ledger_document",
    "mask_sensitive_values",
    "parse_learning_ledger",
    "parse_promotion_failure_signals",
    "parse_timestamp_utc",
    "risk_grade_for_surfaces",
    "scan_evolution",
    "update_learning_ledger",
    "write_summary_artifacts",
]
