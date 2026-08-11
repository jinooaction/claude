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
STATUS_RELEASED = "RELEASED"
STATUS_SUPPRESSED = "SUPPRESSED"
STATUS_BLOCKED = "BLOCKED"

AUTONOMY_CODEX_START = "CODEX_AUTONOMOUS_START"
AUTONOMY_OPERATOR_APPROVAL = "OPERATOR_APPROVAL_REQUIRED"
AUTONOMY_RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
AUTONOMY_CLOSED_RELEASED = "CLOSED_RELEASED"
AUTONOMY_CLOSED_SUPPRESSED = "CLOSED_SUPPRESSED"
AUTONOMY_OBSERVATION_WAIT = "OBSERVATION_WAIT"

MACRO_GROWTH_DISCOVERY_CANDIDATE_ID = "candidate-macro-growth-discovery"
MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID = (
    "candidate-evolution-source-diversification"
)
MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID = (
    "candidate-autonomous-growth-objective-calibration"
)
FRONTIER_DISCOVERY_CANDIDATE_ID = "candidate-autonomous-frontier-discovery"
MACRO_CANDIDATE_MAP_REGENERATOR_ID = "candidate-macro-candidate-map-regenerator"
INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID = "candidate-investment-edge-frontier-map"
FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID = (
    "candidate-forward-regime-edge-experiment"
)
SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID = (
    "candidate-signal-diversification-edge-experiment"
)
COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID = (
    "candidate-cost-adjusted-edge-experiment"
)
DATA_EVIDENCE_FRONTIER_CANDIDATE_ID = "candidate-data-evidence-frontier-map"
PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID = (
    "candidate-public-data-input-quality-contract"
)
REGIME_TIMELINE_COVERAGE_CANDIDATE_ID = "candidate-regime-timeline-coverage-contract"
DATA_EVIDENCE_LIVENESS_CANDIDATE_ID = "candidate-data-evidence-liveness-contract"
EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID = "candidate-execution-quality-frontier-map"
BROKER_REJECTION_TAXONOMY_CANDIDATE_ID = (
    "candidate-broker-rejection-taxonomy-contract"
)
EXECUTION_COST_BASIS_CANDIDATE_ID = "candidate-execution-cost-basis-contract"
BROKER_DIAGNOSTIC_LIVENESS_CANDIDATE_ID = (
    "candidate-broker-diagnostic-liveness-contract"
)
AGENT_OPS_FRONTIER_CANDIDATE_ID = "candidate-agent-ops-frontier-map"
HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID = "candidate-handoff-truth-liveness-contract"
PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID = (
    "candidate-pr-merge-evidence-liveness-contract"
)
WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID = (
    "candidate-worktree-concurrency-liveness-contract"
)
AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID = (
    "candidate-agent-harness-regression-liveness-contract"
)
OPERATOR_REPORT_LIVENESS_CANDIDATE_ID = "candidate-operator-report-liveness-contract"
EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID = (
    "candidate-evidence-source-diversification-validation-failures"
)
BROAD_FRONTIER_EXPANSION_VALIDATION_FAILURES_CANDIDATE_PREFIX = (
    "candidate-broad-frontier-expansion-validation-failures"
)
BROAD_FRONTIER_EXPANSION_NO_EDGE_CANDIDATE_PREFIX = (
    "candidate-broad-frontier-expansion-no-edge"
)
BROAD_VALIDATION_FAILURE_COMMAND_REPLAY_CANDIDATE_ID = (
    "candidate-broad-validation-failure-command-replay-contract"
)
BROAD_VALIDATION_FAILURE_DATA_READINESS_CANDIDATE_ID = (
    "candidate-broad-validation-failure-data-readiness-contract"
)
BROAD_VALIDATION_FAILURE_PACKAGE_KIND_CANDIDATE_ID = (
    "candidate-broad-validation-failure-package-kind-expansion-contract"
)
BROAD_VALIDATION_FAILURE_PROMOTION_RECHECK_CANDIDATE_ID = (
    "candidate-broad-validation-failure-promotion-recheck-contract"
)
BROAD_NO_EDGE_ASSET_UNIVERSE_ROTATION_CANDIDATE_ID = (
    "candidate-broad-no-edge-asset-universe-rotation-experiment"
)
BROAD_NO_EDGE_MULTI_HORIZON_SIGNAL_CANDIDATE_ID = (
    "candidate-broad-no-edge-multi-horizon-signal-experiment"
)
BROAD_NO_EDGE_REGIME_COST_ROBUSTNESS_CANDIDATE_ID = (
    "candidate-broad-no-edge-regime-cost-robustness-experiment"
)
BROAD_NO_EDGE_DATA_GAP_AUDIT_CANDIDATE_ID = (
    "candidate-broad-no-edge-data-gap-audit"
)
WAIT_FOR_FRESH_EVIDENCE_CANDIDATE_ID = "wait-for-fresh-evidence"

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
_RELEASED_STATUSES = {"released", "release", "completed", "complete", "done", "shipped"}
_CLOSED_QUEUE_STATUSES = {STATUS_RELEASED, STATUS_SUPPRESSED}

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
    "rebalance-paper-forward": "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
    "edge-autoarm": "automation/edge-autoarm-last-run:LAST_RUN.md",
    "money-path": "automation/money-path-last-run:LAST_RUN.md",
    "execution-quality": "automation/execution-quality-last-run:LAST_RUN.md",
    "kis-smoke": "automation/kis-smoke-last-run:LAST_RUN.md",
    "rebalance-micro-gtaa": "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
    "public-data": "automation/public-data:LAST_RUN.md",
    "regime-stratify": "automation/regime-stratify-last-run:LAST_RUN.md",
    "released-work": "automation/released-work-last-run:released_work.json",
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

CODEX_COMPLETION_GATES: tuple[str, ...] = (
    "관련 focused pytest 통과",
    "uv run pytest 통과",
    "uv run ruff check src tests 통과",
    "uv run python scripts/check_handoff_facts.py 통과",
    "uv run python scripts/agent_harness_probe.py --strict 통과",
    "PR 품질 관문 통과",
    "필요한 HANDOFF 갱신",
)

OBJECTIVE_VERSION = "autonomous-growth-objective-v1"
MAX_RANKED_CANDIDATES = 10
MAX_PARALLEL_CANDIDATES = 1
MAX_VALIDATION_MINUTES = 90

_OBJECTIVE_WEIGHTS: dict[str, int] = {
    "growth_leverage": 30,
    "evidence_readiness": 20,
    "validation_cost_fit": 15,
    "safety_margin": 25,
    "learning_value": 10,
}

_OBJECTIVE_STOP_CONDITIONS: tuple[str, ...] = (
    "operator approval required for safety-impact or grade >=4 work",
    "missing or malformed required sidecar evidence blocks autonomous start",
    (
        "full pytest, ruff, handoff fact check, strict harness, "
        "or PR quality gate failure blocks merge"
    ),
    "WIP or DO NOT MERGE PR body blocks automatic merge",
)


@dataclass(frozen=True)
class MacroGrowthCandidateTemplate:
    """정적 후보 큐가 닫혔을 때 순차적으로 꺼내는 거시 성장 후보."""

    candidate_id: str
    title_ko: str
    priority_score: int
    reason_ko: str
    next_action_ko: str


@dataclass(frozen=True)
class MacroCandidateMapTemplate:
    """후보 고갈 뒤 재생성할 상위 탐색 영역."""

    domain_key: str
    work_domain_key: str
    label_ko: str
    recommended_candidate_id: str
    title_ko: str
    priority_score: int
    reason_ko: str
    next_action_ko: str
    source_domain_keys: tuple[str, ...]


@dataclass(frozen=True)
class InvestmentEdgeFrontierTemplate:
    """투자 엣지 영역 안에서 재생성할 no-live 실험 후보."""

    frontier_key: str
    label_ko: str
    recommended_candidate_id: str
    title_ko: str
    priority_score: int
    reason_ko: str
    next_action_ko: str


@dataclass(frozen=True)
class DataEvidenceFrontierTemplate:
    """데이터 증거 영역 안에서 재생성할 입력 품질 후보."""

    frontier_key: str
    label_ko: str
    recommended_candidate_id: str
    title_ko: str
    priority_score: int
    reason_ko: str
    next_action_ko: str


@dataclass(frozen=True)
class ExecutionQualityFrontierTemplate:
    """체결 품질 영역 안에서 재생성할 브로커·비용 진단 후보."""

    frontier_key: str
    label_ko: str
    recommended_candidate_id: str
    title_ko: str
    priority_score: int
    reason_ko: str
    next_action_ko: str


@dataclass(frozen=True)
class AgentOpsFrontierTemplate:
    """운영 체계 영역 안에서 재생성할 자율 루프 후보."""

    frontier_key: str
    label_ko: str
    recommended_candidate_id: str
    title_ko: str
    priority_score: int
    reason_ko: str
    next_action_ko: str


@dataclass(frozen=True)
class BroadNoEdgeFrontierTemplate:
    """NO_EDGE_YET 뒤 정적 후보 목록 밖에서 재생성할 no-live 실험 후보."""

    frontier_key: str
    label_ko: str
    work_domain_key: str
    recommended_candidate_id: str
    title_ko: str
    priority_score: int
    reason_ko: str
    next_action_ko: str
    review_axes: tuple[str, ...]


@dataclass(frozen=True)
class BroadValidationFailureFrontierTemplate:
    """검증 실패 parent 후보 뒤 재생성할 구체 no-live 검증 후보."""

    frontier_key: str
    label_ko: str
    work_domain_key: str
    recommended_candidate_id: str
    title_ko: str
    priority_score: int
    reason_ko: str
    next_action_ko: str
    failure_codes: tuple[str, ...]
    package_kinds: tuple[str, ...]
    review_axes: tuple[str, ...]


_MACRO_GROWTH_CANDIDATES: tuple[MacroGrowthCandidateTemplate, ...] = (
    MacroGrowthCandidateTemplate(
        candidate_id=MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
        title_ko="거시 자율 성장 후보 발굴기",
        priority_score=2800,
        reason_ko=(
            "정적 후보 템플릿과 기존 sidecar 후보가 모두 완료·억제로 닫혀 "
            "새 성장 축을 합성해야 한다."
        ),
        next_action_ko=(
            "closed-queue 신호를 SDD로 설계하고, released-work 뒤 다음 거시 후보로 "
            "이어지는 결정론적 후보 발굴 규칙을 구현한다."
        ),
    ),
    MacroGrowthCandidateTemplate(
        candidate_id=MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
        title_ko="정적 후보 템플릿 밖 증거 기반 후보 공간 확장",
        priority_score=2700,
        reason_ko=(
            "거시 후보 발굴 부트스트랩은 출시됐지만 upstream evolution 후보 생성은 "
            "여전히 고정 템플릿 중심이다."
        ),
        next_action_ko=(
            "정적 템플릿 밖 sidecar 나이, 반복 실패 유형, released-work 포화, "
            "관찰 병목을 후보 생성 입력으로 확장한다."
        ),
    ),
    MacroGrowthCandidateTemplate(
        candidate_id=MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
        title_ko="자율 성장 목적 함수와 탐색 예산 보정",
        priority_score=2600,
        reason_ko=(
            "후보 공간 확장 뒤에는 성장률, 검증 비용, 안전 경계를 함께 보는 "
            "탐색 목적 함수가 필요하다."
        ),
        next_action_ko=(
            "후보 발굴의 목적 함수, 탐색 예산, 중단 조건, 반복 학습 지표를 "
            "측정 가능한 계약으로 고정한다."
        ),
    ),
)

_INVESTMENT_EDGE_FRONTIER_TEMPLATES: tuple[InvestmentEdgeFrontierTemplate, ...] = (
    InvestmentEdgeFrontierTemplate(
        frontier_key="forward_regime_edge",
        label_ko="forward 레짐 엣지",
        recommended_candidate_id=FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID,
        title_ko="forward 레짐 엣지 no-live 실험 설계",
        priority_score=2350,
        reason_ko=(
            "forward verdict 관측과 레짐 성과 증거는 존재하지만, 레짐별 견고성을 "
            "다음 no-live 실험 후보로 분리한 계약은 아직 없다."
        ),
        next_action_ko=(
            "rebalance-paper-forward, money-path, released-work, learning ledger를 "
            "함께 읽어 레짐별 forward edge no-live 실험 계약과 검증 기준을 SDD로 만든다."
        ),
    ),
    InvestmentEdgeFrontierTemplate(
        frontier_key="signal_diversification_edge",
        label_ko="신호 다변화 엣지",
        recommended_candidate_id=SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID,
        title_ko="신호 다변화 no-live 엣지 실험 설계",
        priority_score=2250,
        reason_ko=(
            "기존 forward 후보가 특정 신호·전략군에 치우치면 세계 수준의 투자 엣지 "
            "탐색 폭이 좁아진다."
        ),
        next_action_ko=(
            "기존 forward verdict와 released-work를 읽어 상관이 낮은 신호 후보군을 "
            "no-live 실험 후보로 분리한다."
        ),
    ),
    InvestmentEdgeFrontierTemplate(
        frontier_key="cost_adjusted_edge",
        label_ko="비용 차감 엣지",
        recommended_candidate_id=COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID,
        title_ko="거래 비용 차감 no-live 엣지 실험 설계",
        priority_score=2150,
        reason_ko=(
            "paper 성과가 실제 돈으로 이어지려면 비용과 슬리피지에 둔감한 엣지를 "
            "분리해 검증해야 한다."
        ),
        next_action_ko=(
            "forward verdict, execution-quality, money-path 증거를 함께 읽어 비용 차감 "
            "no-live 실험 후보와 통과 기준을 만든다."
        ),
    ),
)

_DATA_EVIDENCE_FRONTIER_TEMPLATES: tuple[DataEvidenceFrontierTemplate, ...] = (
    DataEvidenceFrontierTemplate(
        frontier_key="public_data_input_quality",
        label_ko="공개 데이터 입력 품질",
        recommended_candidate_id=PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID,
        title_ko="공개 데이터 입력 품질 계약",
        priority_score=2250,
        reason_ko=(
            "public-data sidecar는 발행 항목과 교차 검증 요약을 갖고 있지만, "
            "그 범위·누락·검증 상태를 다음 투자 후보의 입력 품질 계약으로 고정하지 않았다."
        ),
        next_action_ko=(
            "public-data summary, regime.json, regime_timeline.csv, regime-stratify, "
            "pipeline-liveness를 함께 읽어 공개 데이터 입력 품질 검증 게이트를 만든다."
        ),
    ),
    DataEvidenceFrontierTemplate(
        frontier_key="regime_timeline_coverage",
        label_ko="레짐 타임라인 커버리지",
        recommended_candidate_id=REGIME_TIMELINE_COVERAGE_CANDIDATE_ID,
        title_ko="레짐 타임라인 커버리지 계약",
        priority_score=2150,
        reason_ko=(
            "레짐 층화는 public-data 타임라인에 의존하지만, 라벨 결측·관측 수·"
            "전망적 조인 품질을 별도 후보로 닫지 않았다."
        ),
        next_action_ko=(
            "regime_timeline.csv와 regime-stratify 결과를 읽어 라벨 커버리지, "
            "레짐별 관측 수, 전망적 조인 품질을 검증하는 후보를 만든다."
        ),
    ),
    DataEvidenceFrontierTemplate(
        frontier_key="data_evidence_liveness",
        label_ko="데이터 증거 생존성",
        recommended_candidate_id=DATA_EVIDENCE_LIVENESS_CANDIDATE_ID,
        title_ko="데이터 증거 생존성 계약",
        priority_score=2050,
        reason_ko=(
            "pipeline-liveness는 public-data와 regime-stratify 신선도를 보여주지만, "
            "데이터 품질 후보 관점의 대기·복구 기준은 분리돼 있지 않다."
        ),
        next_action_ko=(
            "pipeline-liveness의 collect-public-data와 regime-stratify 체크를 "
            "데이터 품질 후보의 PASS/WAIT/FAIL 기준으로 분리한다."
        ),
    ),
)

_EXECUTION_QUALITY_FRONTIER_TEMPLATES: tuple[
    ExecutionQualityFrontierTemplate, ...
] = (
    ExecutionQualityFrontierTemplate(
        frontier_key="broker_rejection_taxonomy",
        label_ko="브로커 거부 분류",
        recommended_candidate_id=BROKER_REJECTION_TAXONOMY_CANDIDATE_ID,
        title_ko="브로커 거부 분류 계약",
        priority_score=2150,
        reason_ko=(
            "execution-quality sidecar는 거부 주문과 KIS 오류 코드를 관측하지만, "
            "거부 원인 분류와 재발 기준은 별도 후보로 닫혀 있지 않다."
        ),
        next_action_ko=(
            "execution-quality, rebalance-micro-gtaa, kis-smoke 증거를 함께 읽어 "
            "브로커 거부 코드·원인·재발 가능성을 분류하는 읽기 전용 계약을 만든다."
        ),
    ),
    ExecutionQualityFrontierTemplate(
        frontier_key="execution_cost_basis",
        label_ko="체결 비용 기준",
        recommended_candidate_id=EXECUTION_COST_BASIS_CANDIDATE_ID,
        title_ko="체결 비용 기준 계약",
        priority_score=2050,
        reason_ko=(
            "비용 차감 엣지 후보는 execution-quality를 읽지만, accepted fill 비용 "
            "기준의 충분성은 아직 독립 후보로 닫혀 있지 않다."
        ),
        next_action_ko=(
            "execution-quality와 money-path 증거를 읽어 실제 비용 기준이 충분한지와 "
            "관측 대기 상태를 분리하는 읽기 전용 계약을 만든다."
        ),
    ),
    ExecutionQualityFrontierTemplate(
        frontier_key="broker_diagnostic_liveness",
        label_ko="브로커 진단 생존성",
        recommended_candidate_id=BROKER_DIAGNOSTIC_LIVENESS_CANDIDATE_ID,
        title_ko="브로커 진단 생존성 계약",
        priority_score=1950,
        reason_ko=(
            "KIS smoke와 execution-quality는 신선도와 성공 상태를 보여주지만, "
            "체결 품질 후보 관점의 PASS/WAIT/FAIL 계약은 아직 분리돼 있지 않다."
        ),
        next_action_ko=(
            "kis-smoke, execution-quality, pipeline-liveness를 함께 읽어 브로커 "
            "진단 증거의 생존성 기준을 읽기 전용 계약으로 고정한다."
        ),
    ),
)

_AGENT_OPS_FRONTIER_TEMPLATES: tuple[AgentOpsFrontierTemplate, ...] = (
    AgentOpsFrontierTemplate(
        frontier_key="handoff_truth_liveness",
        label_ko="HANDOFF 사실성 생존성",
        recommended_candidate_id=HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID,
        title_ko="HANDOFF 사실성 생존성 계약",
        priority_score=2150,
        reason_ko=(
            "HANDOFF.md와 check_handoff_facts는 최신 main·코드 merge 상태를 "
            "다음 세션에 전달하지만, stale handoff와 정상 handoff-only 예외를 "
            "후보 관점에서 분리하는 계약은 아직 없다."
        ),
        next_action_ko=(
            "HANDOFF.md, check_handoff_facts.py, agent_harness_probe.py, "
            "released-work, autonomous-work 증거를 함께 읽어 stale handoff와 "
            "정상 handoff-only baseline을 분리하는 읽기 전용 계약을 만든다."
        ),
    ),
    AgentOpsFrontierTemplate(
        frontier_key="pr_merge_evidence_liveness",
        label_ko="PR/머지 증거 생존성",
        recommended_candidate_id=PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID,
        title_ko="PR/머지 증거 생존성 계약",
        priority_score=2050,
        reason_ko=(
            "PR 품질 관문, merge commit, released-work, deploy 관측은 각각 존재하지만 "
            "작업 완료 보고가 어느 증거까지 살아 있어야 하는지 후보 단위로 닫혀 있지 않다."
        ),
        next_action_ko=(
            "PR 본문 품질 관문, merge commit, released-work sidecar, deploy-status "
            "관측을 함께 읽어 머지 뒤 완료 증거의 PASS/WAIT/FAIL 계약을 만든다."
        ),
    ),
    AgentOpsFrontierTemplate(
        frontier_key="worktree_concurrency_liveness",
        label_ko="worktree 동시 작업 생존성",
        recommended_candidate_id=WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID,
        title_ko="worktree 동시 작업 생존성 계약",
        priority_score=1950,
        reason_ko=(
            "local_concurrency_guard와 session lease는 병렬 Codex 작업을 막지만, "
            "WARN/BLOCK·isolate·복구 스냅샷 흐름의 생존성은 후보로 닫혀 있지 않다."
        ),
        next_action_ko=(
            "local_concurrency_guard, .codex/state/concurrency 복구 스냅샷, "
            "pre-commit/pre-push 훅 경로를 읽어 동시 작업 방어의 PASS/WAIT/FAIL "
            "계약을 만든다."
        ),
    ),
    AgentOpsFrontierTemplate(
        frontier_key="agent_harness_regression_liveness",
        label_ko="agent harness 회귀 생존성",
        recommended_candidate_id=AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID,
        title_ko="agent harness 회귀 생존성 계약",
        priority_score=1850,
        reason_ko=(
            "evaluation, 첫 판단 품질, redteam 하네스 묶음은 존재하지만, "
            "strict harness가 무엇을 PASS/WAIT/FAIL로 보존해야 하는지 후보 단위로 "
            "아직 닫혀 있지 않다."
        ),
        next_action_ko=(
            ".codex/harness/evaluation_tasks.toml, quality_tasks.toml, "
            "redteam_tasks.toml, scripts/agent_harness_probe.py를 함께 읽어 "
            "하네스 회귀 증거의 PASS/WAIT/FAIL 계약을 만든다."
        ),
    ),
    AgentOpsFrontierTemplate(
        frontier_key="operator_report_liveness",
        label_ko="운영자 이해 가능 보고 생존성",
        recommended_candidate_id=OPERATOR_REPORT_LIVENESS_CANDIDATE_ID,
        title_ko="운영자 이해 가능 보고 생존성 계약",
        priority_score=1750,
        reason_ko=(
            "AGENTS.md, quality gate, PR 템플릿, 첫 판단 품질 과제는 완료 보고의 "
            "의미 전달을 요구하지만, 최종 보고가 실제 운영 상태 변화·검증·남은 위험을 "
            "후보 단위로 보존하는 계약은 아직 닫혀 있지 않다."
        ),
        next_action_ko=(
            "AGENTS.md 보고 기준, .codex/quality-gate.md, PR 템플릿, "
            "QUALITY-006, HANDOFF와 released-work 증거를 함께 읽어 운영자가 다시 "
            "묻지 않아도 되는 완료 보고의 PASS/WAIT/FAIL 계약을 만든다."
        ),
    ),
)

_BROAD_VALIDATION_FAILURE_FRONTIER_TEMPLATES: tuple[
    BroadValidationFailureFrontierTemplate, ...
] = (
    BroadValidationFailureFrontierTemplate(
        frontier_key="command_replay_contract",
        label_ko="검증 명령 재현 계약",
        work_domain_key="agent_ops",
        recommended_candidate_id=BROAD_VALIDATION_FAILURE_COMMAND_REPLAY_CANDIDATE_ID,
        title_ko="검증 실패 명령 재현 계약",
        priority_score=2480,
        reason_ko=(
            "현재 막힌 패키지는 모두 `execution_failed` 진단이며, 실패 명령·종료 "
            "코드·제한 출력이 다음 후보 발굴의 병목이다. 같은 패키지를 막연히 "
            "재시도하지 말고 재현 가능한 실패 지문 계약으로 먼저 닫아야 한다."
        ),
        next_action_ko=(
            "candidate-result-executor와 candidate-packages 증거를 읽어 실패 명령, "
            "허용된 읽기 전용 재현 범위, 종료 코드, stdout/stderr 요약, 다음 "
            "진단 action을 기계 판독 계약으로 만든다."
        ),
        failure_codes=("execution_failed",),
        package_kinds=("strategy_backtest", "portfolio_backtest"),
        review_axes=("validation_command", "exit_code", "safe_replay", "output_digest"),
    ),
    BroadValidationFailureFrontierTemplate(
        frontier_key="data_readiness_contract",
        label_ko="검증 데이터 준비도",
        work_domain_key="data_quality",
        recommended_candidate_id=BROAD_VALIDATION_FAILURE_DATA_READINESS_CANDIDATE_ID,
        title_ko="검증 실패 데이터 준비도 계약",
        priority_score=2380,
        reason_ko=(
            "두 패키지 모두 후보 history root와 포트폴리오 입력을 요구한다. 실행 "
            "실패가 전략 아이디어의 실패인지 데이터 준비 결함인지 분리하지 못하면 "
            "엣지 탐색 폭이 실제보다 좁아진다."
        ),
        next_action_ko=(
            "candidate history support, portfolio TOML, public-data, regime-stratify "
            "증거를 함께 읽어 history root, 관측 기간, 데이터 결측 원인을 "
            "검증 패키지별 PASS/WAIT/FAIL로 분리한다."
        ),
        failure_codes=("execution_failed",),
        package_kinds=("strategy_backtest", "portfolio_backtest"),
        review_axes=("history_root", "portfolio_toml", "market_history_coverage"),
    ),
    BroadValidationFailureFrontierTemplate(
        frontier_key="package_kind_expansion",
        label_ko="전략·포트폴리오 패키지 분리",
        work_domain_key="strategy_design",
        recommended_candidate_id=BROAD_VALIDATION_FAILURE_PACKAGE_KIND_CANDIDATE_ID,
        title_ko="검증 실패 패키지 종류별 frontier 확장",
        priority_score=2280,
        reason_ko=(
            "막힌 패키지는 전략 백테스트와 포트폴리오 백테스트가 섞여 있다. 둘을 "
            "같은 실패로 취급하면 전략군, 포트폴리오 구성, 보유 기간, 산출 증거를 "
            "넓히는 순서가 흐려진다."
        ),
        next_action_ko=(
            "strategy_backtest와 portfolio_backtest 실패를 나눠 전략군, 포트폴리오 "
            "구성, 보유 기간, 산출 증거별 no-live 후보 축을 재정렬한다."
        ),
        failure_codes=("execution_failed",),
        package_kinds=("strategy_backtest", "portfolio_backtest"),
        review_axes=("strategy_family", "portfolio_design", "holding_period"),
    ),
    BroadValidationFailureFrontierTemplate(
        frontier_key="promotion_recheck_contract",
        label_ko="승격 재검토 조건",
        work_domain_key="review",
        recommended_candidate_id=BROAD_VALIDATION_FAILURE_PROMOTION_RECHECK_CANDIDATE_ID,
        title_ko="검증 실패 승격 재검토 계약",
        priority_score=2180,
        reason_ko=(
            "learning ledger가 실패 후보를 억제한 뒤 재검토 조건이 없으면, 실패가 "
            "고쳐져도 후보가 닫힌 채 남을 수 있다. 억제 기억은 필요하지만 새 증거가 "
            "생겼을 때 되살리는 조건도 필요하다."
        ),
        next_action_ko=(
            "learning ledger, autonomous-promotion, candidate-result evidence를 "
            "함께 읽어 어떤 실패 지문 변화가 후보 재검토를 허용하는지 결정론적 "
            "계약으로 만든다."
        ),
        failure_codes=("execution_failed",),
        package_kinds=("strategy_backtest", "portfolio_backtest"),
        review_axes=("learning_ledger", "promotion_evidence", "recheck_condition"),
    ),
)

_BROAD_NO_EDGE_FRONTIER_TEMPLATES: tuple[BroadNoEdgeFrontierTemplate, ...] = (
    BroadNoEdgeFrontierTemplate(
        frontier_key="asset_universe_rotation",
        label_ko="자산군 확장과 방어 회전",
        work_domain_key="strategy_design",
        recommended_candidate_id=BROAD_NO_EDGE_ASSET_UNIVERSE_ROTATION_CANDIDATE_ID,
        title_ko="광역 자산군 방어 회전 no-live 실험 설계",
        priority_score=2490,
        reason_ko=(
            "기존 비교 트랙이 모두 NO_EDGE라면 같은 자산군 안에서 신호만 바꾸는 "
            "탐색은 충분히 넓지 않다."
        ),
        next_action_ko=(
            "public-data, rebalance-paper-forward, money-path를 함께 읽어 "
            "주식·현금성·채권성·방어 자산군 대체 후보의 no-live 후보군과 제외 기준을 "
            "SDD로 정의한다."
        ),
        review_axes=("strategy_family", "asset_universe"),
    ),
    BroadNoEdgeFrontierTemplate(
        frontier_key="multi_horizon_signal",
        label_ko="다중 보유 기간과 신호군",
        work_domain_key="strategy_design",
        recommended_candidate_id=BROAD_NO_EDGE_MULTI_HORIZON_SIGNAL_CANDIDATE_ID,
        title_ko="다중 보유 기간 신호군 no-live 실험 설계",
        priority_score=2390,
        reason_ko=(
            "단일 보유 기간이나 유사한 momentum 신호만 반복하면 엣지가 없는 구간을 "
            "계속 같은 방식으로 재측정할 수 있다."
        ),
        next_action_ko=(
            "rebalance-paper-forward와 learning ledger를 읽어 단기·중기·장기 "
            "보유 기간과 trend·carry·quality·volatility 신호군을 분리한 "
            "no-live 실험 후보를 만든다."
        ),
        review_axes=("signal_family", "holding_period"),
    ),
    BroadNoEdgeFrontierTemplate(
        frontier_key="regime_cost_robustness",
        label_ko="레짐과 비용 견고성",
        work_domain_key="strategy_design",
        recommended_candidate_id=BROAD_NO_EDGE_REGIME_COST_ROBUSTNESS_CANDIDATE_ID,
        title_ko="레짐·비용 견고성 no-live 실험 설계",
        priority_score=2290,
        reason_ko=(
            "paper 성과가 비용, 슬리피지, 레짐 전환에 약하면 실제 돈 경로로 "
            "올라갈 수 없다."
        ),
        next_action_ko=(
            "regime-stratify, execution-quality, money-path 증거를 함께 읽어 "
            "레짐 구간별 통과 기준과 비용 민감도 stress test를 no-live 계약으로 "
            "정의한다."
        ),
        review_axes=("regime_window", "cost_sensitivity"),
    ),
    BroadNoEdgeFrontierTemplate(
        frontier_key="data_gap_causal_audit",
        label_ko="데이터 결측 원인 감사",
        work_domain_key="data_quality",
        recommended_candidate_id=BROAD_NO_EDGE_DATA_GAP_AUDIT_CANDIDATE_ID,
        title_ko="NO_EDGE 데이터 결측 원인 감사",
        priority_score=2190,
        reason_ko=(
            "엣지가 없다는 결론이 진짜 전략 문제인지, 공개 데이터 범위·조인·레짐 "
            "라벨 결측 때문인지 분리해야 한다."
        ),
        next_action_ko=(
            "public-data summary, regime.json, regime_timeline.csv를 읽어 데이터 "
            "결측 원인이 no-edge 판정에 끼친 영향을 분리하는 읽기 전용 감사를 "
            "정의한다."
        ),
        review_axes=("data_missing_cause", "regime_window"),
    ),
)

_MACRO_CANDIDATE_MAP_TEMPLATES: tuple[MacroCandidateMapTemplate, ...] = (
    MacroCandidateMapTemplate(
        domain_key="investment_edge",
        work_domain_key="strategy_design",
        label_ko="투자 엣지",
        recommended_candidate_id=INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID,
        title_ko="투자 엣지 frontier 지도와 실험 후보 재생성",
        priority_score=2400,
        reason_ko=(
            "최근 후보는 운영 체계 개선에 치우쳤고, 장기 목표는 측정 가능한 투자 성과 "
            "성장이다."
        ),
        next_action_ko=(
            "forward verdict, money-path, released-work, learning ledger를 함께 읽어 "
            "투자 엣지 후보 공간을 영역별로 지도화하고 첫 no-live 실험 후보를 생성한다."
        ),
        source_domain_keys=("analysis", "strategy_design", "portfolio_design"),
    ),
    MacroCandidateMapTemplate(
        domain_key="data_evidence",
        work_domain_key="data_quality",
        label_ko="데이터 증거",
        recommended_candidate_id=DATA_EVIDENCE_FRONTIER_CANDIDATE_ID,
        title_ko="데이터 증거 frontier 지도와 입력 품질 후보 재생성",
        priority_score=2300,
        reason_ko=(
            "새 투자 후보는 데이터 깊이와 교차 검증 표면이 충분해야 재현 가능하다."
        ),
        next_action_ko=(
            "공개 데이터, regime, pipeline-liveness, public-data sidecar의 빈 영역을 "
            "지도화해 다음 데이터 품질 후보를 생성한다."
        ),
        source_domain_keys=("data_quality", "data_collection"),
    ),
    MacroCandidateMapTemplate(
        domain_key="execution_quality",
        work_domain_key="execution_quality",
        label_ko="체결 품질",
        recommended_candidate_id=EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID,
        title_ko="체결 품질 frontier 지도와 거래 비용 후보 재생성",
        priority_score=2200,
        reason_ko=(
            "투자 엣지가 실제 돈으로 이어지려면 주문 거부, 슬리피지, 지연, 비용 "
            "관측이 계속 닫혀야 한다."
        ),
        next_action_ko=(
            "execution-quality와 broker 진단 증거를 지도화해 다음 읽기 전용 체결 품질 "
            "후보를 생성한다."
        ),
        source_domain_keys=("execution_quality", "live_readiness"),
    ),
    MacroCandidateMapTemplate(
        domain_key="agent_ops",
        work_domain_key="agent_ops",
        label_ko="운영 체계",
        recommended_candidate_id=AGENT_OPS_FRONTIER_CANDIDATE_ID,
        title_ko="운영 체계 frontier 지도와 자율 루프 후보 재생성",
        priority_score=2100,
        reason_ko=(
            "후보 생성·검증·인계 루프 자체가 멈추면 다음 세션이 다시 수동 발굴을 "
            "반복한다."
        ),
        next_action_ko=(
            "autonomous-work, released-work, handoff, harness 증거를 지도화해 다음 "
            "운영 체계 후보를 생성한다."
        ),
        source_domain_keys=("agent_ops", "review"),
    ),
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
class BlockedPackageRef:
    """검증 실패가 막힌 후보 패키지를 재현하는 최소 참조."""

    candidate_id: str
    package_id: str
    package_kind: str
    status: str
    retryable: bool
    diagnostic_codes: tuple[str, ...]
    next_action_codes: tuple[str, ...]
    safe_to_auto_run: bool
    source_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "package_id": self.package_id,
            "package_kind": self.package_kind,
            "status": self.status,
            "retryable": self.retryable,
            "diagnostic_codes": list(self.diagnostic_codes),
            "next_action_codes": list(self.next_action_codes),
            "safe_to_auto_run": self.safe_to_auto_run,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True)
class ValidationFailureGroup:
    """동일 진단 코드로 묶인 막힌 검증 패키지 집계."""

    reason_code: str
    summary_ko: str
    package_count: int
    retryable_count: int
    safe_action_codes: tuple[str, ...]
    package_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "summary_ko": self.summary_ko,
            "package_count": self.package_count,
            "retryable_count": self.retryable_count,
            "safe_action_codes": list(self.safe_action_codes),
            "package_refs": list(self.package_refs),
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
    autonomy_level: str
    reason_ko: str
    next_action_ko: str
    start_guidance_ko: str
    completion_gates: tuple[str, ...]
    required_inputs: tuple[str, ...]
    safety_boundary: tuple[str, ...]
    source_refs: tuple[str, ...]
    blocked_package_refs: tuple[BlockedPackageRef, ...] = ()
    validation_failure_groups: tuple[ValidationFailureGroup, ...] = ()

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
            "autonomy_level": self.autonomy_level,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "start_guidance_ko": self.start_guidance_ko,
            "completion_gates": list(self.completion_gates),
            "required_inputs": list(self.required_inputs),
            "safety_boundary": list(self.safety_boundary),
            "source_refs": list(self.source_refs),
            "blocked_package_refs": [
                package.to_dict() for package in self.blocked_package_refs
            ],
            "validation_failure_groups": [
                group.to_dict() for group in self.validation_failure_groups
            ],
        }


@dataclass(frozen=True)
class ObjectiveExplorationBudget:
    """자율 성장 후보 탐색의 Codex 작업 범위 예산."""

    max_ranked_candidates: int
    max_parallel_candidates: int
    max_validation_minutes: int
    requires_handoff_refresh: bool
    requires_pr_quality_gate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_ranked_candidates": self.max_ranked_candidates,
            "max_parallel_candidates": self.max_parallel_candidates,
            "max_validation_minutes": self.max_validation_minutes,
            "requires_handoff_refresh": self.requires_handoff_refresh,
            "requires_pr_quality_gate": self.requires_pr_quality_gate,
        }


@dataclass(frozen=True)
class ObjectiveLearningMetrics:
    """반복 학습에 필요한 후보 큐 집계."""

    ranked_count: int
    suppressed_count: int
    operator_approval_count: int
    released_count: int
    blocked_count: int
    safety_impact_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "ranked_count": self.ranked_count,
            "suppressed_count": self.suppressed_count,
            "operator_approval_count": self.operator_approval_count,
            "released_count": self.released_count,
            "blocked_count": self.blocked_count,
            "safety_impact_count": self.safety_impact_count,
        }


@dataclass(frozen=True)
class ObjectiveCandidateScore:
    """후보 하나를 목적 함수 구성요소로 설명한 점수."""

    candidate_id: str
    status: str
    risk_grade: int
    priority_score: int
    growth_leverage: int
    evidence_readiness: int
    validation_cost_fit: int
    safety_margin: int
    learning_value: int
    total_score: int
    explanation_ko: str

    def component_scores(self) -> dict[str, int]:
        return {
            "growth_leverage": self.growth_leverage,
            "evidence_readiness": self.evidence_readiness,
            "validation_cost_fit": self.validation_cost_fit,
            "safety_margin": self.safety_margin,
            "learning_value": self.learning_value,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status,
            "risk_grade": self.risk_grade,
            "priority_score": self.priority_score,
            "component_scores": self.component_scores(),
            "total_score": self.total_score,
            "explanation_ko": self.explanation_ko,
        }


@dataclass(frozen=True)
class MacroCandidateMapEntry:
    """후보 고갈 뒤 다음 탐색 영역을 설명하는 지도 행."""

    domain_key: str
    work_domain_key: str
    label_ko: str
    coverage_status: str
    ready_count: int
    operator_or_blocked_count: int
    closed_count: int
    released_count: int
    suppressed_count: int
    priority_score: int
    recommended_candidate_id: str
    title_ko: str
    reason_ko: str
    next_action_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_key": self.domain_key,
            "work_domain_key": self.work_domain_key,
            "label_ko": self.label_ko,
            "coverage_status": self.coverage_status,
            "ready_count": self.ready_count,
            "operator_or_blocked_count": self.operator_or_blocked_count,
            "closed_count": self.closed_count,
            "released_count": self.released_count,
            "suppressed_count": self.suppressed_count,
            "priority_score": self.priority_score,
            "recommended_candidate_id": self.recommended_candidate_id,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
        }


@dataclass(frozen=True)
class InvestmentEdgeFrontierMapEntry:
    """투자 엣지 영역 안쪽의 no-live 실험 후보 지도 행."""

    frontier_key: str
    label_ko: str
    coverage_status: str
    priority_score: int
    recommended_candidate_id: str
    title_ko: str
    reason_ko: str
    next_action_ko: str
    required_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontier_key": self.frontier_key,
            "label_ko": self.label_ko,
            "coverage_status": self.coverage_status,
            "priority_score": self.priority_score,
            "recommended_candidate_id": self.recommended_candidate_id,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class DataEvidenceFrontierMapEntry:
    """데이터 증거 영역 안쪽의 입력 품질 후보 지도 행."""

    frontier_key: str
    label_ko: str
    coverage_status: str
    priority_score: int
    recommended_candidate_id: str
    title_ko: str
    reason_ko: str
    next_action_ko: str
    required_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontier_key": self.frontier_key,
            "label_ko": self.label_ko,
            "coverage_status": self.coverage_status,
            "priority_score": self.priority_score,
            "recommended_candidate_id": self.recommended_candidate_id,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class ExecutionQualityFrontierMapEntry:
    """체결 품질 영역 안쪽의 브로커·비용 진단 후보 지도 행."""

    frontier_key: str
    label_ko: str
    coverage_status: str
    priority_score: int
    recommended_candidate_id: str
    title_ko: str
    reason_ko: str
    next_action_ko: str
    required_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontier_key": self.frontier_key,
            "label_ko": self.label_ko,
            "coverage_status": self.coverage_status,
            "priority_score": self.priority_score,
            "recommended_candidate_id": self.recommended_candidate_id,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class AgentOpsFrontierMapEntry:
    """운영 체계 영역 안쪽의 자율 루프 후보 지도 행."""

    frontier_key: str
    label_ko: str
    coverage_status: str
    priority_score: int
    recommended_candidate_id: str
    title_ko: str
    reason_ko: str
    next_action_ko: str
    required_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontier_key": self.frontier_key,
            "label_ko": self.label_ko,
            "coverage_status": self.coverage_status,
            "priority_score": self.priority_score,
            "recommended_candidate_id": self.recommended_candidate_id,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class BroadNoEdgeFrontierMapEntry:
    """NO_EDGE_YET 뒤 광역 no-live 실험 후보 지도 행."""

    frontier_key: str
    label_ko: str
    work_domain_key: str
    coverage_status: str
    priority_score: int
    recommended_candidate_id: str
    title_ko: str
    reason_ko: str
    next_action_ko: str
    review_axes: tuple[str, ...]
    required_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontier_key": self.frontier_key,
            "label_ko": self.label_ko,
            "work_domain_key": self.work_domain_key,
            "coverage_status": self.coverage_status,
            "priority_score": self.priority_score,
            "recommended_candidate_id": self.recommended_candidate_id,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "review_axes": list(self.review_axes),
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class BroadValidationFailureFrontierMapEntry:
    """검증 실패 parent 뒤 광역 no-live 검증 후보 지도 행."""

    frontier_key: str
    label_ko: str
    work_domain_key: str
    coverage_status: str
    priority_score: int
    recommended_candidate_id: str
    title_ko: str
    reason_ko: str
    next_action_ko: str
    failure_codes: tuple[str, ...]
    package_kinds: tuple[str, ...]
    review_axes: tuple[str, ...]
    package_count: int
    retryable_count: int
    required_inputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontier_key": self.frontier_key,
            "label_ko": self.label_ko,
            "work_domain_key": self.work_domain_key,
            "coverage_status": self.coverage_status,
            "priority_score": self.priority_score,
            "recommended_candidate_id": self.recommended_candidate_id,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "failure_codes": list(self.failure_codes),
            "package_kinds": list(self.package_kinds),
            "review_axes": list(self.review_axes),
            "package_count": self.package_count,
            "retryable_count": self.retryable_count,
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class ObjectiveCalibration:
    """자율 성장 목적 함수, 예산, 중단 조건, 학습 지표 계약."""

    objective_version: str
    selected_candidate_id: str | None
    exploration_budget: ObjectiveExplorationBudget
    stop_conditions: tuple[str, ...]
    learning_metrics: ObjectiveLearningMetrics
    candidate_scores: tuple[ObjectiveCandidateScore, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_version": self.objective_version,
            "selected_candidate_id": self.selected_candidate_id,
            "exploration_budget": self.exploration_budget.to_dict(),
            "stop_conditions": list(self.stop_conditions),
            "learning_metrics": self.learning_metrics.to_dict(),
            "candidate_scores": [score.to_dict() for score in self.candidate_scores],
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
    macro_candidate_map: tuple[MacroCandidateMapEntry, ...]
    investment_edge_frontier_map: tuple[InvestmentEdgeFrontierMapEntry, ...]
    data_evidence_frontier_map: tuple[DataEvidenceFrontierMapEntry, ...]
    execution_quality_frontier_map: tuple[ExecutionQualityFrontierMapEntry, ...]
    agent_ops_frontier_map: tuple[AgentOpsFrontierMapEntry, ...]
    broad_validation_failure_frontier_map: tuple[
        BroadValidationFailureFrontierMapEntry, ...
    ]
    broad_no_edge_frontier_map: tuple[BroadNoEdgeFrontierMapEntry, ...]
    evidence_surfaces: tuple[EvidenceSurface, ...]
    safety_invariants: tuple[str, ...]
    objective_calibration: ObjectiveCalibration

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
            "macro_candidate_map": [
                entry.to_dict() for entry in self.macro_candidate_map
            ],
            "investment_edge_frontier_map": [
                entry.to_dict() for entry in self.investment_edge_frontier_map
            ],
            "data_evidence_frontier_map": [
                entry.to_dict() for entry in self.data_evidence_frontier_map
            ],
            "execution_quality_frontier_map": [
                entry.to_dict() for entry in self.execution_quality_frontier_map
            ],
            "agent_ops_frontier_map": [
                entry.to_dict() for entry in self.agent_ops_frontier_map
            ],
            "broad_validation_failure_frontier_map": [
                entry.to_dict() for entry in self.broad_validation_failure_frontier_map
            ],
            "broad_no_edge_frontier_map": [
                entry.to_dict() for entry in self.broad_no_edge_frontier_map
            ],
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "safety_invariants": list(self.safety_invariants),
            "objective_calibration": self.objective_calibration.to_dict(),
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
                f"| autonomy_level | {packet.autonomy_level} |",
                f"| risk_grade | {packet.risk_grade} |",
                f"| priority_score | {packet.priority_score} |",
                f"| next_action_ko | {_table(packet.next_action_ko)} |",
                f"| start_guidance_ko | {_table(packet.start_guidance_ko)} |",
            ]
            if packet.completion_gates:
                gates = "; ".join(packet.completion_gates)
                lines.append(f"| completion_gates | {_table(gates)} |")

            if packet.validation_failure_groups:
                lines += [
                    "",
                    "## 검증 실패 그룹",
                    "",
                    "| 진단 | 패키지 | 재시도 가능 | 안전 다음 행동 | 요약 |",
                    "|------|-------:|-----------:|----------------|------|",
                ]
                for group in packet.validation_failure_groups:
                    actions = ", ".join(group.safe_action_codes) or "-"
                    lines.append(
                        f"| {_table(group.reason_code)} | {group.package_count} | "
                        f"{group.retryable_count} | {_table(actions)} | "
                        f"{_table(group.summary_ko)} |"
                    )

            if packet.blocked_package_refs:
                lines += [
                    "",
                    "## 막힌 검증 패키지",
                    "",
                    "| 후보 | 패키지 | 종류 | 진단 | 안전 다음 행동 | 출처 |",
                    "|------|--------|------|------|----------------|------|",
                ]
                for package in packet.blocked_package_refs:
                    diagnostics = ", ".join(package.diagnostic_codes) or "-"
                    actions = ", ".join(package.next_action_codes) or "-"
                    lines.append(
                        f"| {_table(package.candidate_id)} | {_table(package.package_id)} | "
                        f"{_table(package.package_kind)} | {_table(diagnostics)} | "
                        f"{_table(actions)} | {_table(package.source_ref)} |"
                    )

        lines += ["", "## 실행 가능 후보", ""]
        if self.ranked_work:
            lines += [
                "| 후보 | 영역 | 상태 | 자율 수준 | 위험 | 점수 | 이유 |",
                "|------|------|------|----------|-----:|-----:|------|",
            ]
            for packet in self.ranked_work:
                lines.append(
                    f"| {_table(packet.candidate_id)} | {_table(packet.domain_key)} | "
                    f"{packet.status} | {packet.autonomy_level} | {packet.risk_grade} | "
                    f"{packet.priority_score} | {_table(packet.reason_ko)} |"
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

        calibration = self.objective_calibration
        lines += [
            "",
            "## 목적 함수 보정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| objective_version | {calibration.objective_version} |",
            f"| selected_candidate_id | {_table(calibration.selected_candidate_id or '(없음)')} |",
        ]
        budget = calibration.exploration_budget.to_dict()
        for key, value in budget.items():
            lines.append(f"| {key} | {value} |")

        lines += ["", "### 중단 조건", ""]
        for condition in calibration.stop_conditions:
            lines.append(f"- {condition}")

        metrics = calibration.learning_metrics.to_dict()
        lines += ["", "### 반복 학습 지표", "", "| 지표 | 값 |", "|------|-----:|"]
        for key, value in metrics.items():
            lines.append(f"| {key} | {value} |")

        lines += ["", "### 후보 점수", ""]
        if calibration.candidate_scores:
            lines += [
                "| 후보 | 상태 | 위험 | 총점 | 성장 | 증거 | 검증 | 안전 | 학습 | 설명 |",
                "|------|------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|------|",
            ]
            for score in calibration.candidate_scores:
                components = score.component_scores()
                lines.append(
                    f"| {_table(score.candidate_id)} | {score.status} | {score.risk_grade} | "
                    f"{score.total_score} | {components['growth_leverage']} | "
                    f"{components['evidence_readiness']} | "
                    f"{components['validation_cost_fit']} | "
                    f"{components['safety_margin']} | {components['learning_value']} | "
                    f"{_table(score.explanation_ko)} |"
                )
        else:
            lines.append("- 점수화할 후보가 없습니다.")

        lines += ["", "## 거시 후보 지도", ""]
        if self.macro_candidate_map:
            lines += [
                "| 영역 | 상태 | 실행 | 닫힘 | 완료 | 억제 | 점수 | 추천 후보 | 이유 |",
                "|------|------|-----:|-----:|-----:|-----:|-----:|-----------|------|",
            ]
            for entry in self.macro_candidate_map:
                lines.append(
                    f"| {_table(entry.label_ko)} | {entry.coverage_status} | "
                    f"{entry.ready_count} | {entry.closed_count} | "
                    f"{entry.released_count} | {entry.suppressed_count} | "
                    f"{entry.priority_score} | "
                    f"{_table(entry.recommended_candidate_id)} | "
                    f"{_table(entry.reason_ko)} |"
                )
        else:
            lines.append("- 거시 후보 지도 항목이 없습니다.")

        lines += ["", "## 투자 엣지 frontier 지도", ""]
        if self.investment_edge_frontier_map:
            lines += [
                "| 영역 | 상태 | 점수 | 추천 후보 | 이유 |",
                "|------|------|-----:|-----------|------|",
            ]
            for entry in self.investment_edge_frontier_map:
                lines.append(
                    f"| {_table(entry.label_ko)} | {entry.coverage_status} | "
                    f"{entry.priority_score} | "
                    f"{_table(entry.recommended_candidate_id)} | "
                    f"{_table(entry.reason_ko)} |"
                )
        else:
            lines.append("- 투자 엣지 frontier 지도 항목이 없습니다.")

        lines += ["", "## 데이터 증거 frontier 지도", ""]
        if self.data_evidence_frontier_map:
            lines += [
                "| 영역 | 상태 | 점수 | 추천 후보 | 이유 |",
                "|------|------|-----:|-----------|------|",
            ]
            for entry in self.data_evidence_frontier_map:
                lines.append(
                    f"| {_table(entry.label_ko)} | {entry.coverage_status} | "
                    f"{entry.priority_score} | "
                    f"{_table(entry.recommended_candidate_id)} | "
                    f"{_table(entry.reason_ko)} |"
                )
        else:
            lines.append("- 데이터 증거 frontier 지도 항목이 없습니다.")

        lines += ["", "## 체결 품질 frontier 지도", ""]
        if self.execution_quality_frontier_map:
            lines += [
                "| 영역 | 상태 | 점수 | 추천 후보 | 이유 |",
                "|------|------|-----:|-----------|------|",
            ]
            for entry in self.execution_quality_frontier_map:
                lines.append(
                    f"| {_table(entry.label_ko)} | {entry.coverage_status} | "
                    f"{entry.priority_score} | "
                    f"{_table(entry.recommended_candidate_id)} | "
                    f"{_table(entry.reason_ko)} |"
                )
        else:
            lines.append("- 체결 품질 frontier 지도 항목이 없습니다.")

        lines += ["", "## 운영 체계 frontier 지도", ""]
        if self.agent_ops_frontier_map:
            lines += [
                "| 영역 | 상태 | 점수 | 추천 후보 | 이유 |",
                "|------|------|-----:|-----------|------|",
            ]
            for entry in self.agent_ops_frontier_map:
                lines.append(
                    f"| {_table(entry.label_ko)} | {entry.coverage_status} | "
                    f"{entry.priority_score} | "
                    f"{_table(entry.recommended_candidate_id)} | "
                    f"{_table(entry.reason_ko)} |"
                )
        else:
            lines.append("- 운영 체계 frontier 지도 항목이 없습니다.")

        lines += ["", "## 검증 실패 frontier 지도", ""]
        if self.broad_validation_failure_frontier_map:
            lines += [
                "| 영역 | 상태 | 패키지 | 점수 | 추천 후보 | 검토 축 | 이유 |",
                "|------|------|-------:|-----:|-----------|---------|------|",
            ]
            for entry in self.broad_validation_failure_frontier_map:
                axes = ", ".join(entry.review_axes)
                lines.append(
                    f"| {_table(entry.label_ko)} | {entry.coverage_status} | "
                    f"{entry.package_count} | {entry.priority_score} | "
                    f"{_table(entry.recommended_candidate_id)} | "
                    f"{_table(axes)} | {_table(entry.reason_ko)} |"
                )
        else:
            lines.append("- 검증 실패 frontier 지도 항목이 없습니다.")

        lines += ["", "## 광역 no-edge frontier 지도", ""]
        if self.broad_no_edge_frontier_map:
            lines += [
                "| 영역 | 상태 | 점수 | 추천 후보 | 검토 축 | 이유 |",
                "|------|------|-----:|-----------|---------|------|",
            ]
            for entry in self.broad_no_edge_frontier_map:
                axes = ", ".join(entry.review_axes)
                lines.append(
                    f"| {_table(entry.label_ko)} | {entry.coverage_status} | "
                    f"{entry.priority_score} | "
                    f"{_table(entry.recommended_candidate_id)} | "
                    f"{_table(axes)} | {_table(entry.reason_ko)} |"
                )
        else:
            lines.append("- 광역 no-edge frontier 지도 항목이 없습니다.")

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


def _json_after_marker(text: str | None, marker: str) -> Any | None:
    if not text:
        return None
    marker_index = text.find(marker)
    if marker_index < 0:
        return None
    object_index = text.find("{", marker_index)
    if object_index < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(text[object_index:])
    except json.JSONDecodeError:
        return None
    return parsed


def _markdown_table_value(text: str, key: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "|" not in stripped[1:]:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2 or cells[0] != key:
            continue
        return cells[1]
    return None


def _kis_smoke_markdown(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
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
        if (value := _markdown_table_value(text, key)) is not None
    }
    if not parsed:
        return None
    return parsed


def _json_headers_for_key(key: str) -> tuple[str, ...]:
    if key == "public-data":
        return ("summary.json", "결정 JSON", "decision JSON")
    if key == "regime-stratify":
        return ("stratified json", "결정 JSON", "decision JSON")
    return ("결정 JSON", "decision JSON")


def _json_for_key(key: str, text: str | None) -> Any | None:
    if key == "kis-smoke":
        return _kis_smoke_markdown(text) or _json_any(
            text,
            *_json_headers_for_key(key),
        )
    if key == "regime-stratify":
        return _json_after_marker(text, "stratified json") or _json_any(
            text,
            *_json_headers_for_key(key),
        )
    return _json_any(text, *_json_headers_for_key(key))


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


def _truthy(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return raw != 0
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _mapping_sequence(raw: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(raw, Mapping):
        return (raw,)
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        return tuple(item for item in raw if isinstance(item, Mapping))
    return ()


def _unique_strings(values: Sequence[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    for value in values:
        cleaned = _clean(value)
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return tuple(deduped)


def _status_for_candidate(
    source_status: str,
    risk_grade: int,
    safety_impact: Sequence[str],
) -> str:
    lowered = source_status.strip().lower()
    if lowered in _REJECTED_STATUSES:
        return STATUS_SUPPRESSED
    if lowered in _RELEASED_STATUSES:
        return STATUS_RELEASED
    if lowered in _BLOCKED_STATUSES:
        return STATUS_BLOCKED
    if lowered in _OPERATOR_STATUSES or risk_grade >= 3 or safety_impact:
        return STATUS_OPERATOR_APPROVAL_REQUIRED
    return STATUS_EXECUTION_READY


def _execution_contract(
    status: str,
    risk_grade: int,
    safety_impact: Sequence[str],
) -> tuple[str, str, tuple[str, ...]]:
    if status == STATUS_EXECUTION_READY and risk_grade <= 2 and not safety_impact:
        return (
            AUTONOMY_CODEX_START,
            (
                "운영자 추가 질문 없이 새 worktree 또는 브랜치에서 SDD 두께를 판단하고 "
                "구현, 검증, PR, 자동 머지 절차로 진행할 수 있다."
            ),
            CODEX_COMPLETION_GATES,
        )
    if status == STATUS_OPERATOR_APPROVAL_REQUIRED:
        return (
            AUTONOMY_OPERATOR_APPROVAL,
            "운영자 명시 승인 전에는 구현·실행하지 말고 안전 경계와 승인 필요 사유만 보고한다.",
            (
                "운영자 승인 기록",
                "안전 경계 영향 재평가",
                "필요 시 별도 SDD와 PR 품질 관문",
            ),
        )
    if status == STATUS_BLOCKED:
        return (
            AUTONOMY_RECOVERY_REQUIRED,
            "후보 실행보다 입력 sidecar나 workflow 복구를 먼저 수행한다.",
            ("복구 focused pytest 통과", "생존 감시 재실행", "HANDOFF 필요 시 갱신"),
        )
    if status == STATUS_RELEASED:
        return (
            AUTONOMY_CLOSED_RELEASED,
            "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
            ("released-work 장부 유지",),
        )
    if status == STATUS_SUPPRESSED:
        return (
            AUTONOMY_CLOSED_SUPPRESSED,
            (
                "learning ledger가 억제한 후보이므로 새 증거 또는 재검토 조건 없이는 "
                "다시 착수하지 않는다."
            ),
            ("learning ledger 억제 사유 유지",),
        )
    if status == STATUS_OBSERVATION_WAIT:
        return (
            AUTONOMY_OBSERVATION_WAIT,
            "현재는 새 코드 작업을 시작하지 말고 다음 sidecar 갱신 증거를 기다린다.",
            ("새 sidecar 증거 수집", "released-work/autonomous-work 재실행"),
        )
    return (
        AUTONOMY_RECOVERY_REQUIRED,
        "상태를 해석할 수 없으므로 입력 증거를 먼저 복구한다.",
        ("입력 증거 파싱 복구",),
    )


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
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        status,
        risk_grade,
        safety_impact,
    )
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
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=next_action,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
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
    autonomy_level, start_guidance, completion_gates = _execution_contract(status, 2, ())
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
        autonomy_level=autonomy_level,
        reason_ko=reason_ko,
        next_action_ko=next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
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
    if "overall_ok" in parsed:
        return f"overall_ok={parsed.get('overall_ok')}, published={parsed.get('published')}"
    if parsed.get("total_return_days"):
        return f"total_return_days={parsed.get('total_return_days')}"
    if parsed.get("smoke_state"):
        return f"state={parsed.get('smoke_state')}, exit={parsed.get('smoke_exit')}"
    if parsed.get("latest_signal"):
        return f"signal={parsed.get('latest_signal')}"
    if parsed.get("readiness_state"):
        return (
            f"readiness={parsed.get('readiness_state')}, "
            f"live={parsed.get('live_money_status')}"
        )
    for key in (
        "candidates",
        "packages",
        "results",
        "actions",
        "assessments",
        "entries",
        "released_work",
    ):
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


def _blocked_package_candidate_id(item: Mapping[str, Any]) -> str:
    return _clean(
        item.get("candidate_id")
        or item.get("candidate")
        or item.get("candidate_key")
    )


def _blocked_package_id(item: Mapping[str, Any]) -> str:
    return _clean(
        item.get("package_id")
        or item.get("package")
        or item.get("id")
        or item.get("result_id")
    )


def _diagnostic_items(item: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return _mapping_sequence(item.get("diagnostics"))


def _next_action_items(item: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    actions: list[Mapping[str, Any]] = list(_mapping_sequence(item.get("next_actions")))
    for diagnostic in _diagnostic_items(item):
        actions.extend(_mapping_sequence(diagnostic.get("next_actions")))
    return tuple(actions)


def _diagnostic_codes(item: Mapping[str, Any]) -> tuple[str, ...]:
    return _unique_strings(
        [
            _clean(diagnostic.get("code"))
            for diagnostic in _diagnostic_items(item)
        ]
    )


def _next_action_codes(item: Mapping[str, Any]) -> tuple[str, ...]:
    return _unique_strings(
        [
            _clean(action.get("action_code") or action.get("code"))
            for action in _next_action_items(item)
        ]
    )


def _retryable_validation_failure(item: Mapping[str, Any]) -> bool:
    if _truthy(item.get("retryable")):
        return True
    return any(_truthy(diagnostic.get("retryable")) for diagnostic in _diagnostic_items(item))


def _safe_validation_next_action(item: Mapping[str, Any]) -> bool:
    actions = _next_action_items(item)
    return bool(actions) and all(_truthy(action.get("safe_to_auto_run")) for action in actions)


def _blocked_package_ref_from_item(
    item: Mapping[str, Any],
    *,
    source_key: str,
) -> BlockedPackageRef | None:
    source_status = _candidate_status(item)
    if source_status.lower() not in _BLOCKED_STATUSES:
        return None
    candidate_id = _blocked_package_candidate_id(item)
    package_id = _blocked_package_id(item)
    if not candidate_id or not package_id:
        return None
    retryable = _retryable_validation_failure(item)
    safe_to_auto_run = _safe_validation_next_action(item)
    if not retryable or not safe_to_auto_run:
        return None
    diagnostic_codes = _diagnostic_codes(item) or ("execution_failed",)
    next_action_codes = _next_action_codes(item)
    if not next_action_codes:
        return None
    return BlockedPackageRef(
        candidate_id=candidate_id,
        package_id=package_id,
        package_kind=_clean(item.get("package_kind") or item.get("kind") or "unknown"),
        status=source_status.lower(),
        retryable=retryable,
        diagnostic_codes=diagnostic_codes,
        next_action_codes=next_action_codes,
        safe_to_auto_run=safe_to_auto_run,
        source_ref=_clean(item.get("source_ref") or _SOURCE_REFS[source_key]),
    )


def _retryable_blocked_package_refs(parsed: Mapping[str, Any]) -> tuple[BlockedPackageRef, ...]:
    source_items = (
        (
            "candidate-result-executor",
            _items(parsed.get("candidate-result-executor"), ("results", "candidate_results")),
        ),
        ("candidate-packages", _items(parsed.get("candidate-packages"), ("packages",))),
        (
            "candidate-implementation-factory",
            _items(parsed.get("candidate-implementation-factory"), ("packages",)),
        ),
    )
    refs: list[BlockedPackageRef] = []
    seen: set[tuple[str, str]] = set()
    for source_key, items in source_items:
        for item in items:
            ref = _blocked_package_ref_from_item(item, source_key=source_key)
            if ref is None:
                continue
            key = (ref.candidate_id, ref.package_id)
            if key in seen:
                continue
            refs.append(ref)
            seen.add(key)
    return tuple(sorted(refs, key=lambda ref: (ref.candidate_id, ref.package_id)))


def _validation_failure_groups(
    refs: Sequence[BlockedPackageRef],
) -> tuple[ValidationFailureGroup, ...]:
    grouped: dict[str, list[BlockedPackageRef]] = {}
    for ref in refs:
        for code in ref.diagnostic_codes or ("blocked_validation_failure",):
            grouped.setdefault(code, []).append(ref)

    groups: list[ValidationFailureGroup] = []
    for code, packages in grouped.items():
        safe_actions = _unique_strings(
            sorted(
                {
                    action
                    for package in packages
                    for action in package.next_action_codes
                }
            )
        )
        package_refs = tuple(sorted(package.package_id for package in packages))
        retryable_count = sum(package.retryable for package in packages)
        groups.append(
            ValidationFailureGroup(
                reason_code=code,
                summary_ko=(
                    f"{code} 진단으로 막힌 검증 패키지 {len(packages)}개를 "
                    "같은 원인으로 묶었다."
                ),
                package_count=len(packages),
                retryable_count=retryable_count,
                safe_action_codes=safe_actions,
                package_refs=package_refs,
            )
        )
    return tuple(sorted(groups, key=lambda group: group.reason_code))


def _source_diversification_refs() -> tuple[str, ...]:
    return (
        _SOURCE_REFS["released-work"],
        _SOURCE_REFS["evolution-backlog"],
        _SOURCE_REFS["evolution-ledger"],
        _SOURCE_REFS["candidate-implementation-factory"],
        _SOURCE_REFS["candidate-packages"],
        _SOURCE_REFS["candidate-result-executor"],
        _SOURCE_REFS["money-path"],
        _SOURCE_REFS["edge-autoarm"],
        _SOURCE_REFS["pipeline-liveness"],
    )


def _broad_frontier_expansion_refs() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            [
                *_source_diversification_refs(),
                _SOURCE_REFS["rebalance-paper-forward"],
                _SOURCE_REFS["capital-path-readiness"],
                _SOURCE_REFS["public-data"],
                "automation/public-data:summary.json",
                "automation/public-data:regime.json",
                "automation/public-data:regime_timeline.csv",
                _SOURCE_REFS["regime-stratify"],
                _SOURCE_REFS["execution-quality"],
                _SOURCE_REFS["kis-smoke"],
                _SOURCE_REFS["rebalance-micro-gtaa"],
            ]
        )
    )


def _nested_clean(mapping: Any, *keys: str) -> str:
    current = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return ""
        current = current.get(key)
    return _clean(current)


def _verdict_from_text(*values: object) -> str:
    text = " ".join(_clean(value) for value in values)
    for token in ("NO_EDGE", "EDGE_CONFIRMED", "INTENT_LOSS", "INTENT_GAIN"):
        if token in text:
            return token
    return ""


def _money_and_edge_context(parsed: Mapping[str, Any]) -> tuple[str, str, str, str]:
    money = parsed.get("money-path")
    edge = parsed.get("edge-autoarm")
    live_status = "미확인"
    ladder_stage = "미확인"
    edge_status = "미확인"
    forward_verdict = "미확인"
    if isinstance(money, Mapping):
        live_status = (
            _nested_clean(money, "live_money_state", "status")
            or _clean(money.get("live_money_status"))
            or _clean(money.get("overall_status"))
            or live_status
        )
        ladder_stage = (
            _clean(money.get("stage"))
            or _clean(money.get("capital_ladder_stage"))
            or _clean(money.get("readiness_state"))
            or ladder_stage
        )
    if isinstance(edge, Mapping):
        edge_status = (
            _clean(edge.get("overall_status"))
            or _clean(edge.get("status"))
            or _clean(edge.get("action"))
            or edge_status
        )
        forward_verdict = (
            _clean(edge.get("current_signal"))
            or _clean(edge.get("forward_verdict"))
            or _clean(edge.get("verdict"))
            or _verdict_from_text(edge.get("reason"))
            or forward_verdict
        )
    return live_status, ladder_stage, edge_status, forward_verdict


def _evidence_source_diversification_packet(
    packets: Sequence[WorkPacket],
    parsed: Mapping[str, Any],
) -> WorkPacket | None:
    if any(packet.status == STATUS_EXECUTION_READY for packet in packets):
        return None
    if any(packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED for packet in packets):
        return None
    released = _released_candidates(parsed.get("released-work"))
    if EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID in released:
        return None

    blocked_refs = _retryable_blocked_package_refs(parsed)
    if not blocked_refs:
        return None

    source_refs = _source_diversification_refs()
    groups = _validation_failure_groups(blocked_refs)
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    closed_count = sum(packet.status in _CLOSED_QUEUE_STATUSES for packet in packets)
    blocked_count = sum(packet.status == STATUS_BLOCKED for packet in packets)
    live_status, ladder_stage, edge_status, forward_verdict = _money_and_edge_context(
        parsed
    )
    diagnostic_summary = ", ".join(group.reason_code for group in groups) or "blocked"
    title = "막힌 검증 패키지 기반 후보 소스 다변화"
    reason = (
        f"실행 가능한 일반 후보는 없고 닫힌 후보 {closed_count}개가 남아 있다. "
        f"일반 큐에서 해석된 막힘은 {blocked_count}개지만, 후보 결과 실행기 "
        f"증거에는 자동으로 원인을 좁혀볼 수 있는 막힌 검증 패키지 "
        f"{len(blocked_refs)}개가 있으며 주요 진단은 {diagnostic_summary}이다. "
        f"money-path는 {live_status}/{ladder_stage}, edge-autoarm은 "
        f"{edge_status}/{forward_verdict}이므로 "
        "이 후보는 PREVIEW_ONLY/NO_EDGE_YET 상태에서 실제 주문이나 live 재무장을 "
        "허용하지 않는 읽기 전용 작업이다."
    )
    next_action = (
        "candidate-result-executor의 종료 코드와 제한된 출력만 읽어 "
        "strategy_backtest·portfolio_backtest 검증 실패 원인을 좁히고, "
        "후보 공장 입력 또는 no-live 검증 계약을 보정하는 SDD 작업으로 연결한다."
    )
    safety_boundary = (
        *SAFETY_INVARIANTS,
        "실제 주문, live 재무장, 자본 배분을 승인하지 않음",
    )
    return WorkPacket(
        packet_id=_packet_id(
            EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID,
            title,
            source_refs,
        ),
        candidate_id=EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID,
        domain_key="agent_ops",
        title_ko=title,
        work_type=_DOMAIN_WORK_TYPES["agent_ops"],
        risk_grade=2,
        safety_impact=(),
        priority_score=2650,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=next_action,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=safety_boundary,
        source_refs=source_refs,
        blocked_package_refs=blocked_refs,
        validation_failure_groups=groups,
    )


def _broad_frontier_expansion_candidate_id(
    blocked_refs: Sequence[BlockedPackageRef],
    groups: Sequence[ValidationFailureGroup],
) -> str:
    digest_source = {
        "groups": [
            {
                "reason_code": group.reason_code,
                "package_refs": sorted(group.package_refs),
                "safe_action_codes": sorted(group.safe_action_codes),
            }
            for group in groups
        ],
        "packages": [
            {
                "candidate_id": package.candidate_id,
                "package_id": package.package_id,
                "package_kind": package.package_kind,
                "diagnostic_codes": sorted(package.diagnostic_codes),
                "next_action_codes": sorted(package.next_action_codes),
            }
            for package in blocked_refs
        ],
    }
    digest = hashlib.sha256(
        json.dumps(digest_source, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"{BROAD_FRONTIER_EXPANSION_VALIDATION_FAILURES_CANDIDATE_PREFIX}-{digest}"


def _no_edge_context(
    live_status: str,
    ladder_stage: str,
    edge_status: str,
    forward_verdict: str,
) -> bool:
    text = " ".join(
        value.upper()
        for value in (live_status, ladder_stage, edge_status, forward_verdict)
        if value
    )
    if "EDGE_CONFIRMED" in text:
        return False
    return any(
        token in text
        for token in (
            "NO_EDGE",
            "NO_EDGE_YET",
            "WAIT_EDGE",
            "ACCUMULATING_EDGE",
            "PREVIEW_ONLY",
        )
    )


def _is_broad_no_edge_parent_candidate(candidate_id: str) -> bool:
    return candidate_id.startswith(
        f"{BROAD_FRONTIER_EXPANSION_NO_EDGE_CANDIDATE_PREFIX}-"
    )


def _is_broad_validation_failure_parent_candidate(candidate_id: str) -> bool:
    return candidate_id.startswith(
        f"{BROAD_FRONTIER_EXPANSION_VALIDATION_FAILURES_CANDIDATE_PREFIX}-"
    )


def _is_broad_no_edge_release(candidate_id: str) -> bool:
    return _is_broad_no_edge_parent_candidate(candidate_id) or candidate_id.startswith(
        "candidate-broad-no-edge-"
    )


def _broad_no_edge_candidate_id(
    *,
    released: Mapping[str, str],
    live_status: str,
    ladder_stage: str,
    edge_status: str,
    forward_verdict: str,
) -> str:
    released_fingerprint_inputs = sorted(
        candidate_id
        for candidate_id in released
        if not _is_broad_no_edge_release(candidate_id)
    )
    digest_source = {
        "edge_context": {
            "live_status": live_status,
            "ladder_stage": ladder_stage,
            "edge_status": edge_status,
            "forward_verdict": forward_verdict,
        },
        "released_candidates": released_fingerprint_inputs,
    }
    digest = hashlib.sha256(
        json.dumps(digest_source, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"{BROAD_FRONTIER_EXPANSION_NO_EDGE_CANDIDATE_PREFIX}-{digest}"


def _broad_frontier_expansion_packet(
    packets: Sequence[WorkPacket],
    parsed: Mapping[str, Any],
    surfaces: Sequence[EvidenceSurface],
) -> WorkPacket | None:
    if any(packet.status == STATUS_EXECUTION_READY for packet in packets):
        return None
    if any(packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED for packet in packets):
        return None
    if any(packet.status == STATUS_BLOCKED for packet in packets):
        return None
    if all(surface.parse_status == PARSE_MISSING for surface in surfaces):
        return None

    released = _released_candidates(parsed.get("released-work"))
    if EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID not in released:
        return None

    blocked_refs = _retryable_blocked_package_refs(parsed)
    groups = _validation_failure_groups(blocked_refs) if blocked_refs else ()
    live_status, ladder_stage, edge_status, forward_verdict = _money_and_edge_context(
        parsed
    )
    if blocked_refs:
        candidate_id = _broad_frontier_expansion_candidate_id(blocked_refs, groups)
        title = "검증 실패 지문 기반 광역 frontier 확장"
        diagnostic_summary = ", ".join(group.reason_code for group in groups) or "blocked"
        reason_focus = (
            f"현재 증거에는 아직 안전하게 분석 가능한 막힌 검증 패키지 "
            f"{len(blocked_refs)}개가 있다. 주요 진단은 {diagnostic_summary}이다. "
            "이 패키지 지문을 기준으로 정적 템플릿 밖의 투자 엣지·데이터·체결 "
            "품질 frontier를 다시 넓힌다."
        )
        next_action_focus = (
            "candidate-result-executor의 막힌 패키지와 rebalance-paper-forward, "
            "public-data, regime-stratify, execution-quality 증거를 함께 읽어 "
            "기존 후보 템플릿 밖의 no-live 실험 축을 SDD로 정의한다."
        )
        priority_score = 2550
    else:
        if not _no_edge_context(
            live_status,
            ladder_stage,
            edge_status,
            forward_verdict,
        ):
            return None
        candidate_id = _broad_no_edge_candidate_id(
            released=released,
            live_status=live_status,
            ladder_stage=ladder_stage,
            edge_status=edge_status,
            forward_verdict=forward_verdict,
        )
        title = "NO_EDGE_YET 기반 광역 투자 frontier 확장"
        reason_focus = (
            "현재 retryable 검증 패키지는 남아 있지 않지만, 알려진 macro·frontier·"
            "중첩 후보가 모두 닫힌 뒤에도 돈 경로가 엣지 확정으로 올라가지 못했다. "
            "따라서 새 sidecar만 기다리지 말고 정적 후보 목록 밖에서 투자 엣지 "
            "탐색 축 자체를 다시 넓힌다."
        )
        next_action_focus = (
            "rebalance-paper-forward, money-path, edge-autoarm, public-data, "
            "regime-stratify, execution-quality 증거를 함께 읽어 기존 후보 "
            "템플릿 밖의 no-live 실험 후보군을 SDD로 정의한다."
        )
        priority_score = 2525

    if candidate_id in released:
        return None

    source_refs = _broad_frontier_expansion_refs()
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    released_count = sum(packet.status == STATUS_RELEASED for packet in packets)
    suppressed_count = sum(packet.status == STATUS_SUPPRESSED for packet in packets)
    reason = (
        "기존 후보 소스 다변화 후보는 released-work에서 완료됐다. "
        f"닫힌 후보는 완료 {released_count}개와 억제 {suppressed_count}개이고, "
        f"{reason_focus} 같은 좁은 후보 목록 안에서 "
        "새 증거만 기다리면 PREVIEW_ONLY/NO_EDGE_YET 상태가 반복되므로, "
        f"money-path는 {live_status}/{ladder_stage}, edge-autoarm은 "
        f"{edge_status}/{forward_verdict}이므로 실제 주문이나 live 재무장은 "
        "여전히 허용하지 않는다."
    )
    next_action = (
        f"{next_action_focus} "
        "검토 축은 전략군, 신호군, 보유 기간, 자산군, 레짐 구간, 비용 민감도, "
        "데이터 결측 원인을 모두 포함하되 브로커 호출·주문·자본 배분은 하지 않는다."
    )
    safety_boundary = (
        *SAFETY_INVARIANTS,
        "증거 지문 기반 후보 발행만 허용",
        "실제 주문, live 재무장, 자본 배분을 승인하지 않음",
    )
    return WorkPacket(
        packet_id=_packet_id(candidate_id, title, source_refs),
        candidate_id=candidate_id,
        domain_key="strategy_design",
        title_ko=title,
        work_type=_DOMAIN_WORK_TYPES["strategy_design"],
        risk_grade=2,
        safety_impact=(),
        priority_score=priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=next_action,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=safety_boundary,
        source_refs=source_refs,
        blocked_package_refs=blocked_refs,
        validation_failure_groups=groups,
    )


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
                autonomy_level=AUTONOMY_CLOSED_SUPPRESSED,
                start_guidance_ko=(
                    "learning ledger가 억제한 후보이므로 새 증거 또는 재검토 조건 없이는 "
                    "다시 착수하지 않는다."
                ),
                completion_gates=("learning ledger 억제 사유 유지",),
                reason_ko=(
                    "learning ledger가 이 후보를 억제했다: "
                    f"{reason}"
                ),
            )
        )
    return tuple(updated)


def _released_candidates(released_work: Any) -> dict[str, str]:
    released: dict[str, str] = {}
    for item in _items(released_work, ("released_work", "entries", "records")):
        candidate_id = _candidate_id(item, "released")
        status = _candidate_status(item).lower()
        if status not in _RELEASED_STATUSES:
            continue
        released[candidate_id] = _candidate_reason(
            item,
            "released-work 장부가 완료된 후보로 기록했다.",
        )
    return released


def _apply_released_work(
    packets: Sequence[WorkPacket],
    released_work: Any,
) -> tuple[WorkPacket, ...]:
    released = _released_candidates(released_work)
    if not released:
        return tuple(packets)
    updated: list[WorkPacket] = []
    for packet in packets:
        reason = released.get(packet.candidate_id)
        if reason is None:
            updated.append(packet)
            continue
        updated.append(
            replace(
                packet,
                status=STATUS_RELEASED,
                autonomy_level=AUTONOMY_CLOSED_RELEASED,
                start_guidance_ko="이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
                completion_gates=("released-work 장부 유지",),
                reason_ko=f"released-work 장부가 이 후보를 완료 처리했다: {reason}",
                next_action_ko="이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
                required_inputs=tuple(
                    dict.fromkeys(
                        [
                            *packet.required_inputs,
                            _SOURCE_REFS["released-work"],
                        ]
                    )
                ),
                source_refs=tuple(
                    dict.fromkeys(
                        [
                            *packet.source_refs,
                            _SOURCE_REFS["released-work"],
                        ]
                    )
                ),
            )
        )
    return tuple(updated)


def _macro_growth_source_refs() -> tuple[str, ...]:
    return (
        _SOURCE_REFS["evolution-backlog"],
        _SOURCE_REFS["released-work"],
        _SOURCE_REFS["pipeline-liveness"],
        _SOURCE_REFS["capital-path-readiness"],
    )


def _investment_edge_source_refs() -> tuple[str, ...]:
    return (
        _SOURCE_REFS["rebalance-paper-forward"],
        _SOURCE_REFS["money-path"],
        _SOURCE_REFS["released-work"],
        _SOURCE_REFS["evolution-ledger"],
        _SOURCE_REFS["pipeline-liveness"],
    )


def _data_evidence_source_refs() -> tuple[str, ...]:
    return (
        _SOURCE_REFS["public-data"],
        "automation/public-data:summary.json",
        "automation/public-data:regime.json",
        "automation/public-data:regime_timeline.csv",
        _SOURCE_REFS["regime-stratify"],
        _SOURCE_REFS["pipeline-liveness"],
        _SOURCE_REFS["released-work"],
        _SOURCE_REFS["capital-path-readiness"],
    )


def _execution_quality_source_refs() -> tuple[str, ...]:
    return (
        _SOURCE_REFS["execution-quality"],
        _SOURCE_REFS["kis-smoke"],
        _SOURCE_REFS["rebalance-micro-gtaa"],
        _SOURCE_REFS["money-path"],
        _SOURCE_REFS["pipeline-liveness"],
        _SOURCE_REFS["released-work"],
        _SOURCE_REFS["capital-path-readiness"],
    )


def _agent_ops_source_refs() -> tuple[str, ...]:
    return (
        "automation/autonomous-work-execution-last-run:LAST_RUN.md",
        _SOURCE_REFS["released-work"],
        _SOURCE_REFS["pipeline-liveness"],
        "AGENTS.md",
        "CLAUDE.md",
        "HANDOFF.md",
        ".codex/quality-gate.md",
        "scripts/local_concurrency_guard.py",
        ".codex/hooks.json",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".codex/state/concurrency",
        ".codex/harness/evaluation_tasks.toml",
        ".codex/harness/quality_tasks.toml",
        ".codex/harness/redteam_tasks.toml",
        "scripts/check_handoff_facts.py",
        "scripts/agent_harness_probe.py",
        ".github/pull_request_template.md",
        ".github/workflows/pr-quality-gate.yml",
    )


def _broad_no_edge_source_refs() -> tuple[str, ...]:
    return _broad_frontier_expansion_refs()


def _broad_validation_failure_source_refs() -> tuple[str, ...]:
    return _broad_frontier_expansion_refs()


def _regular_queue_is_closed(
    packets: Sequence[WorkPacket],
    surfaces: Sequence[EvidenceSurface],
) -> bool:
    if any(packet.status == STATUS_EXECUTION_READY for packet in packets):
        return False
    if any(
        packet.status in {STATUS_OPERATOR_APPROVAL_REQUIRED, STATUS_BLOCKED}
        for packet in packets
    ):
        return False
    if packets:
        return all(packet.status in _CLOSED_QUEUE_STATUSES for packet in packets)
    return not all(surface.parse_status == PARSE_MISSING for surface in surfaces)


def _macro_growth_packets(
    packets: Sequence[WorkPacket],
    *,
    released_work: Any,
    surfaces: Sequence[EvidenceSurface],
    macro_candidate_map: Sequence[MacroCandidateMapEntry],
    investment_edge_frontier_map: Sequence[InvestmentEdgeFrontierMapEntry],
    data_evidence_frontier_map: Sequence[DataEvidenceFrontierMapEntry],
    execution_quality_frontier_map: Sequence[ExecutionQualityFrontierMapEntry],
    agent_ops_frontier_map: Sequence[AgentOpsFrontierMapEntry],
) -> tuple[WorkPacket, ...]:
    if not _regular_queue_is_closed(packets, surfaces):
        return ()

    released = _released_candidates(released_work)
    existing_ids = {packet.candidate_id for packet in packets}
    closed_count = sum(packet.status in _CLOSED_QUEUE_STATUSES for packet in packets)
    released_count = sum(packet.status == STATUS_RELEASED for packet in packets)
    suppressed_count = sum(packet.status == STATUS_SUPPRESSED for packet in packets)

    for template in _MACRO_GROWTH_CANDIDATES:
        if template.candidate_id in released or template.candidate_id in existing_ids:
            continue
        return (
            _macro_growth_packet(
                template,
                closed_count=closed_count,
                released_count=released_count,
                suppressed_count=suppressed_count,
            ),
        )
    frontier = _frontier_discovery_packet(
        released_work=released_work,
        closed_count=closed_count,
        released_count=released_count,
        suppressed_count=suppressed_count,
    )
    if frontier.candidate_id in released or frontier.candidate_id in existing_ids:
        regenerator = _macro_candidate_map_regenerator_packet(
            closed_count=closed_count,
            released_count=released_count,
            suppressed_count=suppressed_count,
            macro_candidate_map=macro_candidate_map,
        )
        if (
            regenerator.candidate_id not in released
            and regenerator.candidate_id not in existing_ids
        ):
            return (regenerator,)
        return _regenerated_macro_candidate_packets(
            macro_candidate_map,
            investment_edge_frontier_map=investment_edge_frontier_map,
            data_evidence_frontier_map=data_evidence_frontier_map,
            execution_quality_frontier_map=execution_quality_frontier_map,
            agent_ops_frontier_map=agent_ops_frontier_map,
            released=released,
            existing_ids=existing_ids,
        )
    return (frontier,)


def _observation_wait_packet(
    packets: Sequence[WorkPacket],
    surfaces: Sequence[EvidenceSurface],
) -> WorkPacket | None:
    if any(
        packet.status
        in {
            STATUS_EXECUTION_READY,
            STATUS_OPERATOR_APPROVAL_REQUIRED,
            STATUS_BLOCKED,
        }
        for packet in packets
    ):
        return None
    if all(surface.parse_status == PARSE_MISSING for surface in surfaces):
        return None

    present_refs = tuple(
        surface.source_ref for surface in surfaces if surface.present and surface.source_ref
    )
    source_refs = present_refs or tuple(_SOURCE_REFS.values())
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_OBSERVATION_WAIT,
        0,
        (),
    )
    released_count = sum(packet.status == STATUS_RELEASED for packet in packets)
    suppressed_count = sum(packet.status == STATUS_SUPPRESSED for packet in packets)
    reason = (
        "실행 가능한 후보, 운영자 승인 필요 후보, 복구 우선 후보가 없습니다. "
        f"현재 보이는 후보는 완료 {released_count}개와 억제 {suppressed_count}개뿐이므로 "
        "완료 후보를 다시 선택하지 않고 새 sidecar 증거를 기다립니다."
    )
    next_action = (
        "다음 scheduled sidecar 갱신 뒤 released-work와 autonomous-work를 다시 읽어 "
        "새 EXECUTION_READY 후보가 생겼는지 확인합니다."
    )
    title = "새 증거 대기"
    return WorkPacket(
        packet_id=_packet_id(WAIT_FOR_FRESH_EVIDENCE_CANDIDATE_ID, title, source_refs),
        candidate_id=WAIT_FOR_FRESH_EVIDENCE_CANDIDATE_ID,
        domain_key="agent_ops",
        title_ko=title,
        work_type=_DOMAIN_WORK_TYPES["agent_ops"],
        risk_grade=0,
        safety_impact=(),
        priority_score=0,
        status=STATUS_OBSERVATION_WAIT,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=next_action,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _macro_growth_packet(
    template: MacroGrowthCandidateTemplate,
    *,
    closed_count: int,
    released_count: int,
    suppressed_count: int,
) -> WorkPacket:
    source_refs = _macro_growth_source_refs()
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    queue_summary = (
        f"현재 일반 후보 큐는 닫힌 후보 {closed_count}개"
        f"(완료 {released_count}개, 억제 {suppressed_count}개)로 구성된다."
    )
    return WorkPacket(
        packet_id=_packet_id(template.candidate_id, template.title_ko, source_refs),
        candidate_id=template.candidate_id,
        domain_key="agent_ops",
        title_ko=template.title_ko,
        work_type=_DOMAIN_WORK_TYPES["agent_ops"],
        risk_grade=2,
        safety_impact=(),
        priority_score=template.priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=f"{template.reason_ko} {queue_summary}",
        next_action_ko=template.next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _frontier_discovery_packet(
    *,
    released_work: Any,
    closed_count: int,
    released_count: int,
    suppressed_count: int,
) -> WorkPacket:
    source_refs = _macro_growth_source_refs()
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    released = _released_candidates(released_work)
    macro_released_count = sum(
        template.candidate_id in released for template in _MACRO_GROWTH_CANDIDATES
    )
    title = "자율 후보 고갈 후 frontier 발굴"
    reason = (
        "기존 일반 후보와 macro 후보가 모두 닫혀 새 탐색 frontier를 발굴해야 한다. "
        f"현재 후보 큐는 닫힌 후보 {closed_count}개"
        f"(완료 {released_count}개, 억제 {suppressed_count}개)이고, "
        f"기존 macro 후보 {macro_released_count}/{len(_MACRO_GROWTH_CANDIDATES)}개가 "
        "released-work 장부에 기록됐다."
    )
    next_action = (
        "frontier discovery 스펙으로 다음 후보 생성 축을 정의하고, "
        "released-work 포화 뒤에도 새 실행 후보가 나오도록 결정론적 발굴 규칙을 구현한다."
    )
    return WorkPacket(
        packet_id=_packet_id(FRONTIER_DISCOVERY_CANDIDATE_ID, title, source_refs),
        candidate_id=FRONTIER_DISCOVERY_CANDIDATE_ID,
        domain_key="agent_ops",
        title_ko=title,
        work_type=_DOMAIN_WORK_TYPES["agent_ops"],
        risk_grade=2,
        safety_impact=(),
        priority_score=2500,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=next_action,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _macro_candidate_map_regenerator_packet(
    *,
    closed_count: int,
    released_count: int,
    suppressed_count: int,
    macro_candidate_map: Sequence[MacroCandidateMapEntry],
) -> WorkPacket:
    source_refs = _macro_growth_source_refs()
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    top_entry = macro_candidate_map[0] if macro_candidate_map else None
    top_summary = (
        f" 최상위 미탐색 영역은 {top_entry.label_ko}이다."
        if top_entry is not None
        else ""
    )
    title = "거시 후보 지도와 후보 재생성 루프"
    reason = (
        "frontier discovery 후보까지 released-work로 닫혔으므로, 단일 후보가 아니라 "
        "영역별 후보 지도를 만들어 다음 후보를 재생성해야 한다. "
        f"현재 후보 큐는 닫힌 후보 {closed_count}개"
        f"(완료 {released_count}개, 억제 {suppressed_count}개)다."
        f"{top_summary}"
    )
    next_action = (
        "투자 엣지, 데이터 증거, 체결 품질, 운영 체계 영역을 점수화하는 "
        "macro candidate map을 만들고, released-work 포화 뒤 최고 우선순위 "
        "미완료 영역 후보를 실행 후보로 발행한다."
    )
    return WorkPacket(
        packet_id=_packet_id(MACRO_CANDIDATE_MAP_REGENERATOR_ID, title, source_refs),
        candidate_id=MACRO_CANDIDATE_MAP_REGENERATOR_ID,
        domain_key="agent_ops",
        title_ko=title,
        work_type=_DOMAIN_WORK_TYPES["agent_ops"],
        risk_grade=2,
        safety_impact=(),
        priority_score=2450,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=next_action,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _regenerated_macro_candidate_packets(
    macro_candidate_map: Sequence[MacroCandidateMapEntry],
    *,
    investment_edge_frontier_map: Sequence[InvestmentEdgeFrontierMapEntry],
    data_evidence_frontier_map: Sequence[DataEvidenceFrontierMapEntry],
    execution_quality_frontier_map: Sequence[ExecutionQualityFrontierMapEntry],
    agent_ops_frontier_map: Sequence[AgentOpsFrontierMapEntry],
    released: Mapping[str, str],
    existing_ids: set[str],
) -> tuple[WorkPacket, ...]:
    for entry in macro_candidate_map:
        if entry.recommended_candidate_id in released:
            if entry.recommended_candidate_id == INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID:
                nested = _regenerated_investment_edge_candidate_packets(
                    investment_edge_frontier_map,
                    released=released,
                    existing_ids=existing_ids,
                )
                if nested:
                    return nested
            if entry.recommended_candidate_id == DATA_EVIDENCE_FRONTIER_CANDIDATE_ID:
                nested = _regenerated_data_evidence_candidate_packets(
                    data_evidence_frontier_map,
                    released=released,
                    existing_ids=existing_ids,
                )
                if nested:
                    return nested
            if entry.recommended_candidate_id == EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID:
                nested = _regenerated_execution_quality_candidate_packets(
                    execution_quality_frontier_map,
                    released=released,
                    existing_ids=existing_ids,
                )
                if nested:
                    return nested
            if entry.recommended_candidate_id == AGENT_OPS_FRONTIER_CANDIDATE_ID:
                nested = _regenerated_agent_ops_candidate_packets(
                    agent_ops_frontier_map,
                    released=released,
                    existing_ids=existing_ids,
                )
                if nested:
                    return nested
            continue
        if entry.recommended_candidate_id in existing_ids:
            continue
        return (_packet_from_macro_map_entry(entry),)
    return ()


def _packet_from_macro_map_entry(entry: MacroCandidateMapEntry) -> WorkPacket:
    source_refs = _macro_growth_source_refs()
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    reason = (
        f"거시 후보 지도에서 {entry.label_ko} 영역이 {entry.coverage_status} 상태다. "
        f"실행 후보 {entry.ready_count}개, 닫힌 후보 {entry.closed_count}개"
        f"(완료 {entry.released_count}개, 억제 {entry.suppressed_count}개). "
        f"{entry.reason_ko}"
    )
    return WorkPacket(
        packet_id=_packet_id(entry.recommended_candidate_id, entry.title_ko, source_refs),
        candidate_id=entry.recommended_candidate_id,
        domain_key=entry.work_domain_key,
        title_ko=entry.title_ko,
        work_type=_DOMAIN_WORK_TYPES.get(
            entry.work_domain_key,
            "autonomous_improvement",
        ),
        risk_grade=2,
        safety_impact=(),
        priority_score=entry.priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=entry.next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _regenerated_investment_edge_candidate_packets(
    investment_edge_frontier_map: Sequence[InvestmentEdgeFrontierMapEntry],
    *,
    released: Mapping[str, str],
    existing_ids: set[str],
) -> tuple[WorkPacket, ...]:
    for entry in investment_edge_frontier_map:
        if entry.recommended_candidate_id in released:
            continue
        if entry.recommended_candidate_id in existing_ids:
            continue
        return (_packet_from_investment_edge_entry(entry),)
    return ()


def _packet_from_investment_edge_entry(
    entry: InvestmentEdgeFrontierMapEntry,
) -> WorkPacket:
    source_refs = entry.required_inputs
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    reason = (
        f"투자 엣지 frontier 지도에서 {entry.label_ko} 영역이 "
        f"{entry.coverage_status} 상태다. {entry.reason_ko}"
    )
    return WorkPacket(
        packet_id=_packet_id(entry.recommended_candidate_id, entry.title_ko, source_refs),
        candidate_id=entry.recommended_candidate_id,
        domain_key="strategy_design",
        title_ko=entry.title_ko,
        work_type=_DOMAIN_WORK_TYPES["strategy_design"],
        risk_grade=2,
        safety_impact=(),
        priority_score=entry.priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=entry.next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _regenerated_data_evidence_candidate_packets(
    data_evidence_frontier_map: Sequence[DataEvidenceFrontierMapEntry],
    *,
    released: Mapping[str, str],
    existing_ids: set[str],
) -> tuple[WorkPacket, ...]:
    for entry in data_evidence_frontier_map:
        if entry.recommended_candidate_id in released:
            continue
        if entry.recommended_candidate_id in existing_ids:
            continue
        return (_packet_from_data_evidence_entry(entry),)
    return ()


def _packet_from_data_evidence_entry(
    entry: DataEvidenceFrontierMapEntry,
) -> WorkPacket:
    source_refs = entry.required_inputs
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    reason = (
        f"데이터 증거 frontier 지도에서 {entry.label_ko} 영역이 "
        f"{entry.coverage_status} 상태다. {entry.reason_ko}"
    )
    return WorkPacket(
        packet_id=_packet_id(entry.recommended_candidate_id, entry.title_ko, source_refs),
        candidate_id=entry.recommended_candidate_id,
        domain_key="data_quality",
        title_ko=entry.title_ko,
        work_type=_DOMAIN_WORK_TYPES["data_quality"],
        risk_grade=2,
        safety_impact=(),
        priority_score=entry.priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=entry.next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _regenerated_execution_quality_candidate_packets(
    execution_quality_frontier_map: Sequence[ExecutionQualityFrontierMapEntry],
    *,
    released: Mapping[str, str],
    existing_ids: set[str],
) -> tuple[WorkPacket, ...]:
    for entry in execution_quality_frontier_map:
        if entry.recommended_candidate_id in released:
            continue
        if entry.recommended_candidate_id in existing_ids:
            continue
        return (_packet_from_execution_quality_entry(entry),)
    return ()


def _packet_from_execution_quality_entry(
    entry: ExecutionQualityFrontierMapEntry,
) -> WorkPacket:
    source_refs = entry.required_inputs
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    reason = (
        f"체결 품질 frontier 지도에서 {entry.label_ko} 영역이 "
        f"{entry.coverage_status} 상태다. {entry.reason_ko}"
    )
    return WorkPacket(
        packet_id=_packet_id(entry.recommended_candidate_id, entry.title_ko, source_refs),
        candidate_id=entry.recommended_candidate_id,
        domain_key="execution_quality",
        title_ko=entry.title_ko,
        work_type=_DOMAIN_WORK_TYPES["execution_quality"],
        risk_grade=2,
        safety_impact=(),
        priority_score=entry.priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=entry.next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _regenerated_agent_ops_candidate_packets(
    agent_ops_frontier_map: Sequence[AgentOpsFrontierMapEntry],
    *,
    released: Mapping[str, str],
    existing_ids: set[str],
) -> tuple[WorkPacket, ...]:
    for entry in agent_ops_frontier_map:
        if entry.recommended_candidate_id in released:
            continue
        if entry.recommended_candidate_id in existing_ids:
            continue
        return (_packet_from_agent_ops_entry(entry),)
    return ()


def _packet_from_agent_ops_entry(entry: AgentOpsFrontierMapEntry) -> WorkPacket:
    source_refs = entry.required_inputs
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    reason = (
        f"운영 체계 frontier 지도에서 {entry.label_ko} 영역이 "
        f"{entry.coverage_status} 상태다. {entry.reason_ko}"
    )
    return WorkPacket(
        packet_id=_packet_id(entry.recommended_candidate_id, entry.title_ko, source_refs),
        candidate_id=entry.recommended_candidate_id,
        domain_key="agent_ops",
        title_ko=entry.title_ko,
        work_type=_DOMAIN_WORK_TYPES["agent_ops"],
        risk_grade=2,
        safety_impact=(),
        priority_score=entry.priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=entry.next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=SAFETY_INVARIANTS,
        source_refs=source_refs,
    )


def _broad_validation_failure_frontier_packets(
    packets: Sequence[WorkPacket],
    parsed: Mapping[str, Any],
    surfaces: Sequence[EvidenceSurface],
    broad_validation_failure_frontier_map: Sequence[
        BroadValidationFailureFrontierMapEntry
    ],
) -> tuple[WorkPacket, ...]:
    if any(packet.status == STATUS_EXECUTION_READY for packet in packets):
        return ()
    if any(packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED for packet in packets):
        return ()
    if any(packet.status == STATUS_BLOCKED for packet in packets):
        return ()
    if all(surface.parse_status == PARSE_MISSING for surface in surfaces):
        return ()

    released = _released_candidates(parsed.get("released-work"))
    if not any(
        _is_broad_validation_failure_parent_candidate(candidate_id)
        for candidate_id in released
    ):
        return ()

    blocked_refs = _retryable_blocked_package_refs(parsed)
    if not blocked_refs:
        return ()
    groups = _validation_failure_groups(blocked_refs)
    existing_ids = {packet.candidate_id for packet in packets}

    for entry in broad_validation_failure_frontier_map:
        if entry.recommended_candidate_id in released:
            continue
        if entry.recommended_candidate_id in existing_ids:
            continue
        if entry.package_count <= 0:
            continue
        return (
            _packet_from_broad_validation_failure_entry(
                entry,
                blocked_refs=blocked_refs,
                groups=groups,
                parsed=parsed,
            ),
        )
    return ()


def _packet_from_broad_validation_failure_entry(
    entry: BroadValidationFailureFrontierMapEntry,
    *,
    blocked_refs: Sequence[BlockedPackageRef],
    groups: Sequence[ValidationFailureGroup],
    parsed: Mapping[str, Any],
) -> WorkPacket:
    source_refs = entry.required_inputs
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    live_status, ladder_stage, edge_status, forward_verdict = _money_and_edge_context(
        parsed
    )
    axes = ", ".join(entry.review_axes)
    diagnostic_summary = ", ".join(group.reason_code for group in groups) or "blocked"
    reason = (
        f"검증 실패 frontier 지도에서 {entry.label_ko} 영역이 "
        f"{entry.coverage_status} 상태다. 현재 retryable 검증 실패 패키지 "
        f"{entry.package_count}개가 {diagnostic_summary} 지문으로 남아 있고, "
        f"검토 축은 {axes}이다. {entry.reason_ko} "
        f"money-path는 {live_status}/{ladder_stage}, edge-autoarm은 "
        f"{edge_status}/{forward_verdict}이므로 실제 주문이나 live 재무장은 "
        "여전히 허용하지 않는다."
    )
    safety_boundary = (
        *SAFETY_INVARIANTS,
        "검증 실패 지문 분석과 no-live 후보 설계만 허용",
        "브로커 API 호출 금지",
        "실제 주문 금지",
        "live 재무장 금지",
        "자본 배분 금지",
    )
    return WorkPacket(
        packet_id=_packet_id(entry.recommended_candidate_id, entry.title_ko, source_refs),
        candidate_id=entry.recommended_candidate_id,
        domain_key=entry.work_domain_key,
        title_ko=entry.title_ko,
        work_type=_DOMAIN_WORK_TYPES.get(
            entry.work_domain_key,
            "autonomous_improvement",
        ),
        risk_grade=2,
        safety_impact=(),
        priority_score=entry.priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=entry.next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=safety_boundary,
        source_refs=source_refs,
        blocked_package_refs=tuple(blocked_refs),
        validation_failure_groups=tuple(groups),
    )


def _broad_no_edge_frontier_packets(
    packets: Sequence[WorkPacket],
    parsed: Mapping[str, Any],
    surfaces: Sequence[EvidenceSurface],
    broad_no_edge_frontier_map: Sequence[BroadNoEdgeFrontierMapEntry],
) -> tuple[WorkPacket, ...]:
    if any(packet.status == STATUS_EXECUTION_READY for packet in packets):
        return ()
    if any(packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED for packet in packets):
        return ()
    if any(packet.status == STATUS_BLOCKED for packet in packets):
        return ()
    if all(surface.parse_status == PARSE_MISSING for surface in surfaces):
        return ()

    released = _released_candidates(parsed.get("released-work"))
    if not any(_is_broad_no_edge_parent_candidate(candidate_id) for candidate_id in released):
        return ()

    live_status, ladder_stage, edge_status, forward_verdict = _money_and_edge_context(
        parsed
    )
    if not _no_edge_context(
        live_status,
        ladder_stage,
        edge_status,
        forward_verdict,
    ):
        return ()

    existing_ids = {packet.candidate_id for packet in packets}
    for entry in broad_no_edge_frontier_map:
        if entry.recommended_candidate_id in released:
            continue
        if entry.recommended_candidate_id in existing_ids:
            continue
        return (
            _packet_from_broad_no_edge_entry(
                entry,
                live_status=live_status,
                ladder_stage=ladder_stage,
                edge_status=edge_status,
                forward_verdict=forward_verdict,
            ),
        )
    return ()


def _packet_from_broad_no_edge_entry(
    entry: BroadNoEdgeFrontierMapEntry,
    *,
    live_status: str,
    ladder_stage: str,
    edge_status: str,
    forward_verdict: str,
) -> WorkPacket:
    source_refs = entry.required_inputs
    autonomy_level, start_guidance, completion_gates = _execution_contract(
        STATUS_EXECUTION_READY,
        2,
        (),
    )
    axes = ", ".join(entry.review_axes)
    reason = (
        f"광역 no-edge frontier 지도에서 {entry.label_ko} 영역이 "
        f"{entry.coverage_status} 상태다. 검토 축은 {axes}이다. {entry.reason_ko} "
        f"money-path는 {live_status}/{ladder_stage}, edge-autoarm은 "
        f"{edge_status}/{forward_verdict}이므로 실제 주문이나 live 재무장은 "
        "여전히 허용하지 않는다."
    )
    safety_boundary = (
        *SAFETY_INVARIANTS,
        "no-live 실험 후보 설계만 허용",
        "브로커 API 호출 금지",
        "실제 주문 금지",
        "live 재무장 금지",
        "자본 배분 금지",
    )
    return WorkPacket(
        packet_id=_packet_id(entry.recommended_candidate_id, entry.title_ko, source_refs),
        candidate_id=entry.recommended_candidate_id,
        domain_key=entry.work_domain_key,
        title_ko=entry.title_ko,
        work_type=_DOMAIN_WORK_TYPES.get(
            entry.work_domain_key,
            "autonomous_improvement",
        ),
        risk_grade=2,
        safety_impact=(),
        priority_score=entry.priority_score,
        status=STATUS_EXECUTION_READY,
        autonomy_level=autonomy_level,
        reason_ko=reason,
        next_action_ko=entry.next_action_ko,
        start_guidance_ko=start_guidance,
        completion_gates=completion_gates,
        required_inputs=source_refs,
        safety_boundary=safety_boundary,
        source_refs=source_refs,
    )


def _macro_candidate_map(
    packets: Sequence[WorkPacket],
) -> tuple[MacroCandidateMapEntry, ...]:
    entries: list[MacroCandidateMapEntry] = []
    for template in _MACRO_CANDIDATE_MAP_TEMPLATES:
        matching = [
            packet
            for packet in packets
            if packet.domain_key in template.source_domain_keys
        ]
        ready_count = sum(
            packet.status == STATUS_EXECUTION_READY for packet in matching
        )
        operator_or_blocked_count = sum(
            packet.status in {STATUS_OPERATOR_APPROVAL_REQUIRED, STATUS_BLOCKED}
            for packet in matching
        )
        released_count = sum(packet.status == STATUS_RELEASED for packet in matching)
        suppressed_count = sum(packet.status == STATUS_SUPPRESSED for packet in matching)
        closed_count = released_count + suppressed_count
        if ready_count:
            coverage_status = "active"
        elif operator_or_blocked_count:
            coverage_status = "operator_or_blocked"
        elif closed_count:
            coverage_status = "exhausted"
        else:
            coverage_status = "underexplored"
        entries.append(
            MacroCandidateMapEntry(
                domain_key=template.domain_key,
                work_domain_key=template.work_domain_key,
                label_ko=template.label_ko,
                coverage_status=coverage_status,
                ready_count=ready_count,
                operator_or_blocked_count=operator_or_blocked_count,
                closed_count=closed_count,
                released_count=released_count,
                suppressed_count=suppressed_count,
                priority_score=template.priority_score,
                recommended_candidate_id=template.recommended_candidate_id,
                title_ko=template.title_ko,
                reason_ko=template.reason_ko,
                next_action_ko=template.next_action_ko,
            )
        )
    return tuple(sorted(entries, key=lambda entry: (-entry.priority_score, entry.domain_key)))


def _investment_edge_frontier_map(
    released_work: Any,
) -> tuple[InvestmentEdgeFrontierMapEntry, ...]:
    released = _released_candidates(released_work)
    required_inputs = _investment_edge_source_refs()
    entries = [
        InvestmentEdgeFrontierMapEntry(
            frontier_key=template.frontier_key,
            label_ko=template.label_ko,
            coverage_status=(
                "released"
                if template.recommended_candidate_id in released
                else "open"
            ),
            priority_score=template.priority_score,
            recommended_candidate_id=template.recommended_candidate_id,
            title_ko=template.title_ko,
            reason_ko=template.reason_ko,
            next_action_ko=template.next_action_ko,
            required_inputs=required_inputs,
        )
        for template in _INVESTMENT_EDGE_FRONTIER_TEMPLATES
    ]
    return tuple(sorted(entries, key=lambda entry: (-entry.priority_score, entry.frontier_key)))


def _data_evidence_frontier_map(
    released_work: Any,
) -> tuple[DataEvidenceFrontierMapEntry, ...]:
    released = _released_candidates(released_work)
    required_inputs = _data_evidence_source_refs()
    entries = [
        DataEvidenceFrontierMapEntry(
            frontier_key=template.frontier_key,
            label_ko=template.label_ko,
            coverage_status=(
                "released"
                if template.recommended_candidate_id in released
                else "open"
            ),
            priority_score=template.priority_score,
            recommended_candidate_id=template.recommended_candidate_id,
            title_ko=template.title_ko,
            reason_ko=template.reason_ko,
            next_action_ko=template.next_action_ko,
            required_inputs=required_inputs,
        )
        for template in _DATA_EVIDENCE_FRONTIER_TEMPLATES
    ]
    return tuple(sorted(entries, key=lambda entry: (-entry.priority_score, entry.frontier_key)))


def _execution_quality_frontier_map(
    released_work: Any,
) -> tuple[ExecutionQualityFrontierMapEntry, ...]:
    released = _released_candidates(released_work)
    required_inputs = _execution_quality_source_refs()
    entries = [
        ExecutionQualityFrontierMapEntry(
            frontier_key=template.frontier_key,
            label_ko=template.label_ko,
            coverage_status=(
                "released"
                if template.recommended_candidate_id in released
                else "open"
            ),
            priority_score=template.priority_score,
            recommended_candidate_id=template.recommended_candidate_id,
            title_ko=template.title_ko,
            reason_ko=template.reason_ko,
            next_action_ko=template.next_action_ko,
            required_inputs=required_inputs,
        )
        for template in _EXECUTION_QUALITY_FRONTIER_TEMPLATES
    ]
    return tuple(sorted(entries, key=lambda entry: (-entry.priority_score, entry.frontier_key)))


def _agent_ops_frontier_map(
    released_work: Any,
) -> tuple[AgentOpsFrontierMapEntry, ...]:
    released = _released_candidates(released_work)
    required_inputs = _agent_ops_source_refs()
    entries = [
        AgentOpsFrontierMapEntry(
            frontier_key=template.frontier_key,
            label_ko=template.label_ko,
            coverage_status=(
                "released"
                if template.recommended_candidate_id in released
                else "open"
            ),
            priority_score=template.priority_score,
            recommended_candidate_id=template.recommended_candidate_id,
            title_ko=template.title_ko,
            reason_ko=template.reason_ko,
            next_action_ko=template.next_action_ko,
            required_inputs=required_inputs,
        )
        for template in _AGENT_OPS_FRONTIER_TEMPLATES
    ]
    return tuple(sorted(entries, key=lambda entry: (-entry.priority_score, entry.frontier_key)))


def _broad_no_edge_frontier_map(
    released_work: Any,
) -> tuple[BroadNoEdgeFrontierMapEntry, ...]:
    released = _released_candidates(released_work)
    required_inputs = _broad_no_edge_source_refs()
    entries = [
        BroadNoEdgeFrontierMapEntry(
            frontier_key=template.frontier_key,
            label_ko=template.label_ko,
            work_domain_key=template.work_domain_key,
            coverage_status=(
                "released"
                if template.recommended_candidate_id in released
                else "open"
            ),
            priority_score=template.priority_score,
            recommended_candidate_id=template.recommended_candidate_id,
            title_ko=template.title_ko,
            reason_ko=template.reason_ko,
            next_action_ko=template.next_action_ko,
            review_axes=template.review_axes,
            required_inputs=required_inputs,
        )
        for template in _BROAD_NO_EDGE_FRONTIER_TEMPLATES
    ]
    return tuple(sorted(entries, key=lambda entry: (-entry.priority_score, entry.frontier_key)))


def _broad_validation_failure_frontier_map(
    released_work: Any,
    blocked_refs: Sequence[BlockedPackageRef],
) -> tuple[BroadValidationFailureFrontierMapEntry, ...]:
    released = _released_candidates(released_work)
    required_inputs = _broad_validation_failure_source_refs()
    entries: list[BroadValidationFailureFrontierMapEntry] = []
    for template in _BROAD_VALIDATION_FAILURE_FRONTIER_TEMPLATES:
        matching = _matching_validation_failure_refs(template, blocked_refs)
        entries.append(
            BroadValidationFailureFrontierMapEntry(
                frontier_key=template.frontier_key,
                label_ko=template.label_ko,
                work_domain_key=template.work_domain_key,
                coverage_status=(
                    "released"
                    if template.recommended_candidate_id in released
                    else "open"
                ),
                priority_score=template.priority_score,
                recommended_candidate_id=template.recommended_candidate_id,
                title_ko=template.title_ko,
                reason_ko=template.reason_ko,
                next_action_ko=template.next_action_ko,
                failure_codes=template.failure_codes,
                package_kinds=template.package_kinds,
                review_axes=template.review_axes,
                package_count=len(matching),
                retryable_count=sum(ref.retryable for ref in matching),
                required_inputs=required_inputs,
            )
        )
    return tuple(sorted(entries, key=lambda entry: (-entry.priority_score, entry.frontier_key)))


def _matching_validation_failure_refs(
    template: BroadValidationFailureFrontierTemplate,
    blocked_refs: Sequence[BlockedPackageRef],
) -> tuple[BlockedPackageRef, ...]:
    failure_codes = set(template.failure_codes)
    package_kinds = set(template.package_kinds)
    return tuple(
        ref
        for ref in blocked_refs
        if ref.package_kind in package_kinds
        and any(code in failure_codes for code in ref.diagnostic_codes)
    )


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
        STATUS_OBSERVATION_WAIT: 3,
        STATUS_RELEASED: 4,
        STATUS_SUPPRESSED: 5,
    }.get(packet.status, 5)
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


def _clamp_score(value: int) -> int:
    return min(100, max(0, value))


def _surface_score(surface: EvidenceSurface | None) -> int:
    if surface is None:
        return 0
    if surface.parse_status in {PARSE_OK, PARSE_PRESENT}:
        return 100
    if surface.parse_status == PARSE_MALFORMED:
        return 25
    return 0


def _evidence_readiness_score(
    packet: WorkPacket,
    surfaces_by_ref: Mapping[str, EvidenceSurface],
) -> int:
    if not packet.required_inputs:
        return 100
    scores = [_surface_score(surfaces_by_ref.get(ref)) for ref in packet.required_inputs]
    return round(sum(scores) / len(scores))


def _growth_leverage_score(packet: WorkPacket) -> int:
    score = round(packet.priority_score / 30)
    if packet.work_type == _DOMAIN_WORK_TYPES["agent_ops"]:
        score += 10
    if packet.candidate_id in {
        MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
        MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
        MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
    }:
        score += 5
    if packet.status != STATUS_EXECUTION_READY:
        score -= 10
    return _clamp_score(score)


def _validation_cost_fit_score(packet: WorkPacket) -> int:
    score = 100 - (max(packet.risk_grade, 1) - 1) * 10
    score -= min(20, max(0, len(packet.required_inputs) - 1) * 5)
    if packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED:
        score -= 20
    if packet.status == STATUS_BLOCKED:
        score -= 30
    return _clamp_score(score)


def _safety_margin_score(packet: WorkPacket) -> int:
    score = 100
    score -= max(0, packet.risk_grade - 2) * 20
    score -= len(packet.safety_impact) * 30
    if packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED:
        score -= 10
    return _clamp_score(score)


def _learning_value_score(packet: WorkPacket) -> int:
    score = 50
    if packet.work_type == _DOMAIN_WORK_TYPES["agent_ops"]:
        score += 25
    if packet.candidate_id in {
        MACRO_GROWTH_DISCOVERY_CANDIDATE_ID,
        MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID,
        MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID,
    }:
        score += 15
    learning_text = f"{packet.reason_ko} {packet.next_action_ko}"
    if any(token in learning_text for token in ("반복", "다시", "완료", "학습", "후보")):
        score += 10
    if packet.status in {STATUS_RELEASED, STATUS_SUPPRESSED}:
        score -= 15
    if packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED:
        score -= 10
    return _clamp_score(score)


def _total_objective_score(component_scores: Mapping[str, int]) -> int:
    weighted = sum(
        component_scores[key] * weight for key, weight in _OBJECTIVE_WEIGHTS.items()
    )
    total_weight = sum(_OBJECTIVE_WEIGHTS.values())
    return (weighted + total_weight // 2) // total_weight


def _objective_explanation(packet: WorkPacket, component_scores: Mapping[str, int]) -> str:
    if packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED:
        return "안전 표면이 있어 운영자 명시 승인 전에는 자동 착수하지 않는 후보입니다."
    if component_scores["evidence_readiness"] < 100:
        return "필수 증거가 일부 부족해 착수 전 sidecar 상태 확인이 필요한 후보입니다."
    if packet.work_type == _DOMAIN_WORK_TYPES["agent_ops"]:
        return "안전 경계 안에서 자율 성장 루프의 반복 판단 비용을 줄이는 후보입니다."
    return "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다."


def _objective_candidate_score(
    packet: WorkPacket,
    surfaces_by_ref: Mapping[str, EvidenceSurface],
) -> ObjectiveCandidateScore:
    component_scores = {
        "growth_leverage": _growth_leverage_score(packet),
        "evidence_readiness": _evidence_readiness_score(packet, surfaces_by_ref),
        "validation_cost_fit": _validation_cost_fit_score(packet),
        "safety_margin": _safety_margin_score(packet),
        "learning_value": _learning_value_score(packet),
    }
    return ObjectiveCandidateScore(
        candidate_id=packet.candidate_id,
        status=packet.status,
        risk_grade=packet.risk_grade,
        priority_score=packet.priority_score,
        growth_leverage=component_scores["growth_leverage"],
        evidence_readiness=component_scores["evidence_readiness"],
        validation_cost_fit=component_scores["validation_cost_fit"],
        safety_margin=component_scores["safety_margin"],
        learning_value=component_scores["learning_value"],
        total_score=_total_objective_score(component_scores),
        explanation_ko=_objective_explanation(packet, component_scores),
    )


def _objective_learning_metrics(
    ranked: Sequence[WorkPacket],
    suppressed: Sequence[WorkPacket],
) -> ObjectiveLearningMetrics:
    packets = [*ranked, *suppressed]
    return ObjectiveLearningMetrics(
        ranked_count=len(ranked),
        suppressed_count=len(suppressed),
        operator_approval_count=sum(
            packet.status == STATUS_OPERATOR_APPROVAL_REQUIRED for packet in packets
        ),
        released_count=sum(packet.status == STATUS_RELEASED for packet in packets),
        blocked_count=sum(packet.status == STATUS_BLOCKED for packet in packets),
        safety_impact_count=sum(bool(packet.safety_impact) for packet in packets),
    )


def _objective_calibration(
    selected: WorkPacket | None,
    ranked: Sequence[WorkPacket],
    suppressed: Sequence[WorkPacket],
    surfaces: Sequence[EvidenceSurface],
) -> ObjectiveCalibration:
    surfaces_by_ref = {surface.source_ref: surface for surface in surfaces}
    scored_packets = [*ranked, *suppressed]
    return ObjectiveCalibration(
        objective_version=OBJECTIVE_VERSION,
        selected_candidate_id=selected.candidate_id if selected is not None else None,
        exploration_budget=ObjectiveExplorationBudget(
            max_ranked_candidates=MAX_RANKED_CANDIDATES,
            max_parallel_candidates=MAX_PARALLEL_CANDIDATES,
            max_validation_minutes=MAX_VALIDATION_MINUTES,
            requires_handoff_refresh=True,
            requires_pr_quality_gate=True,
        ),
        stop_conditions=_OBJECTIVE_STOP_CONDITIONS,
        learning_metrics=_objective_learning_metrics(ranked, suppressed),
        candidate_scores=tuple(
            _objective_candidate_score(packet, surfaces_by_ref) for packet in scored_packets
        ),
    )


def build_autonomous_work_execution(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> AutonomousWorkExecutionReport:
    """수집된 sidecar 원문으로 다음 자율 작업 패킷을 만든다."""

    now = _as_utc(now)
    parsed: dict[str, Any] = {key: _json_for_key(key, raw) for key, raw in evidence_texts.items()}
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
    packets = list(_apply_released_work(packets, parsed.get("released-work")))
    source_diversification_packet = _evidence_source_diversification_packet(
        packets,
        parsed,
    )
    if source_diversification_packet is not None:
        packets.append(source_diversification_packet)

    ordered = _dedupe_packets(packets)
    macro_candidate_map = _macro_candidate_map(ordered)
    investment_edge_frontier_map = _investment_edge_frontier_map(
        parsed.get("released-work")
    )
    data_evidence_frontier_map = _data_evidence_frontier_map(parsed.get("released-work"))
    execution_quality_frontier_map = _execution_quality_frontier_map(
        parsed.get("released-work")
    )
    agent_ops_frontier_map = _agent_ops_frontier_map(parsed.get("released-work"))
    retryable_blocked_refs = _retryable_blocked_package_refs(parsed)
    broad_validation_failure_frontier_map = _broad_validation_failure_frontier_map(
        parsed.get("released-work"),
        retryable_blocked_refs,
    )
    broad_no_edge_frontier_map = _broad_no_edge_frontier_map(
        parsed.get("released-work")
    )
    ordered = _dedupe_packets(
        [
            *ordered,
            *_macro_growth_packets(
                ordered,
                released_work=parsed.get("released-work"),
                surfaces=surfaces,
                macro_candidate_map=macro_candidate_map,
                investment_edge_frontier_map=investment_edge_frontier_map,
                data_evidence_frontier_map=data_evidence_frontier_map,
                execution_quality_frontier_map=execution_quality_frontier_map,
                agent_ops_frontier_map=agent_ops_frontier_map,
            ),
        ]
    )
    broad_frontier_packet = _broad_frontier_expansion_packet(
        ordered,
        parsed,
        surfaces,
    )
    if broad_frontier_packet is not None:
        ordered = _dedupe_packets([*ordered, broad_frontier_packet])
    ordered = _dedupe_packets(
        [
            *ordered,
            *_broad_validation_failure_frontier_packets(
                ordered,
                parsed,
                surfaces,
                broad_validation_failure_frontier_map,
            ),
        ]
    )
    ordered = _dedupe_packets(
        [
            *ordered,
            *_broad_no_edge_frontier_packets(
                ordered,
                parsed,
                surfaces,
                broad_no_edge_frontier_map,
            ),
        ]
    )
    wait_packet = _observation_wait_packet(ordered, surfaces)
    if wait_packet is not None:
        ordered = _dedupe_packets([*ordered, wait_packet])
    ranked = tuple(
        packet for packet in ordered if packet.status == STATUS_EXECUTION_READY
    )[:MAX_RANKED_CANDIDATES]
    suppressed = tuple(
        packet for packet in ordered if packet.status != STATUS_EXECUTION_READY
    )[:MAX_RANKED_CANDIDATES]
    selected = ranked[0] if ranked else (suppressed[0] if suppressed else None)
    overall = _overall_status(selected, ranked, suppressed, surfaces)
    objective_calibration = _objective_calibration(selected, ranked, suppressed, surfaces)

    return AutonomousWorkExecutionReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        overall_status=overall,
        selected_work=selected,
        ranked_work=ranked,
        suppressed_work=suppressed,
        macro_candidate_map=macro_candidate_map,
        investment_edge_frontier_map=investment_edge_frontier_map,
        data_evidence_frontier_map=data_evidence_frontier_map,
        execution_quality_frontier_map=execution_quality_frontier_map,
        agent_ops_frontier_map=agent_ops_frontier_map,
        broad_validation_failure_frontier_map=broad_validation_failure_frontier_map,
        broad_no_edge_frontier_map=broad_no_edge_frontier_map,
        evidence_surfaces=surfaces,
        safety_invariants=SAFETY_INVARIANTS,
        objective_calibration=objective_calibration,
    )


__all__ = [
    "AGENT_HARNESS_REGRESSION_LIVENESS_CANDIDATE_ID",
    "AgentOpsFrontierMapEntry",
    "AGENT_OPS_FRONTIER_CANDIDATE_ID",
    "AutonomousWorkExecutionReport",
    "AUTONOMY_CLOSED_RELEASED",
    "AUTONOMY_CLOSED_SUPPRESSED",
    "AUTONOMY_CODEX_START",
    "AUTONOMY_OBSERVATION_WAIT",
    "AUTONOMY_OPERATOR_APPROVAL",
    "AUTONOMY_RECOVERY_REQUIRED",
    "BlockedPackageRef",
    "BROAD_NO_EDGE_ASSET_UNIVERSE_ROTATION_CANDIDATE_ID",
    "BROAD_NO_EDGE_DATA_GAP_AUDIT_CANDIDATE_ID",
    "BROAD_NO_EDGE_MULTI_HORIZON_SIGNAL_CANDIDATE_ID",
    "BROAD_NO_EDGE_REGIME_COST_ROBUSTNESS_CANDIDATE_ID",
    "BROAD_VALIDATION_FAILURE_COMMAND_REPLAY_CANDIDATE_ID",
    "BROAD_VALIDATION_FAILURE_DATA_READINESS_CANDIDATE_ID",
    "BROAD_VALIDATION_FAILURE_PACKAGE_KIND_CANDIDATE_ID",
    "BROAD_VALIDATION_FAILURE_PROMOTION_RECHECK_CANDIDATE_ID",
    "BroadValidationFailureFrontierMapEntry",
    "BroadNoEdgeFrontierMapEntry",
    "BROKER_DIAGNOSTIC_LIVENESS_CANDIDATE_ID",
    "BROKER_REJECTION_TAXONOMY_CANDIDATE_ID",
    "BROAD_FRONTIER_EXPANSION_NO_EDGE_CANDIDATE_PREFIX",
    "BROAD_FRONTIER_EXPANSION_VALIDATION_FAILURES_CANDIDATE_PREFIX",
    "CODEX_COMPLETION_GATES",
    "COST_ADJUSTED_EDGE_EXPERIMENT_CANDIDATE_ID",
    "DATA_EVIDENCE_LIVENESS_CANDIDATE_ID",
    "DataEvidenceFrontierMapEntry",
    "EvidenceSurface",
    "EVIDENCE_SOURCE_DIVERSIFICATION_VALIDATION_FAILURES_CANDIDATE_ID",
    "EXECUTION_COST_BASIS_CANDIDATE_ID",
    "ExecutionQualityFrontierMapEntry",
    "FORWARD_REGIME_EDGE_EXPERIMENT_CANDIDATE_ID",
    "FRONTIER_DISCOVERY_CANDIDATE_ID",
    "HANDOFF_TRUTH_LIVENESS_CANDIDATE_ID",
    "DATA_EVIDENCE_FRONTIER_CANDIDATE_ID",
    "EXECUTION_QUALITY_FRONTIER_CANDIDATE_ID",
    "INVESTMENT_EDGE_FRONTIER_CANDIDATE_ID",
    "InvestmentEdgeFrontierMapEntry",
    "MacroCandidateMapEntry",
    "MACRO_GROWTH_DISCOVERY_CANDIDATE_ID",
    "MACRO_CANDIDATE_MAP_REGENERATOR_ID",
    "MACRO_GROWTH_OBJECTIVE_CALIBRATION_CANDIDATE_ID",
    "MACRO_GROWTH_SOURCE_DIVERSIFICATION_CANDIDATE_ID",
    "ObjectiveCalibration",
    "ObjectiveCandidateScore",
    "ObjectiveExplorationBudget",
    "ObjectiveLearningMetrics",
    "PR_MERGE_EVIDENCE_LIVENESS_CANDIDATE_ID",
    "PUBLIC_DATA_INPUT_QUALITY_CANDIDATE_ID",
    "REGIME_TIMELINE_COVERAGE_CANDIDATE_ID",
    "SAFETY_INVARIANTS",
    "SCHEMA_VERSION",
    "SIGNAL_DIVERSIFICATION_EDGE_EXPERIMENT_CANDIDATE_ID",
    "STATUS_BLOCKED",
    "STATUS_EXECUTION_READY",
    "STATUS_OBSERVATION_WAIT",
    "STATUS_OPERATOR_APPROVAL_REQUIRED",
    "STATUS_RELEASED",
    "STATUS_SUPPRESSED",
    "ValidationFailureGroup",
    "WAIT_FOR_FRESH_EVIDENCE_CANDIDATE_ID",
    "WORKTREE_CONCURRENCY_LIVENESS_CANDIDATE_ID",
    "WorkPacket",
    "build_autonomous_work_execution",
]
