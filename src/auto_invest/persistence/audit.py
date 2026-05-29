"""Append-only audit log writer.

Per constitution principle IV every domain event MUST land in
`audit_log` exactly once and never be mutated. This module is the
single sanctioned writer.

Per-event payloads are pydantic models so the contract between event
producers and downstream consumers (daily report, reconciliation) stays
explicit. The `event_type` literal on each model is the discriminator
the writer uses to label the row; producers never set it manually.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "RULE_LOAD",
    "ORDER_INTENT",
    "ORDER_SUBMITTED",
    "ORDER_REJECTED_BY_GATE",
    "ORDER_REJECTED_BY_BROKER",
    "FILL",
    "CANCEL",
    "ERROR",
    "RECONCILIATION_OK",
    "RECONCILIATION_MISMATCH",
    "HALT_SET",
    "HALT_CLEARED",
    "STRATEGY_PAUSED",
    "STRATEGY_PROMOTED",
    "DATA_QUALITY_ISSUE",
    "SECRETS_LOADED",
    "WORKER_STARTED",
    "WORKER_STOPPED",
    "LLM_CALL",
    "PRICE_TABLE_LOADED",
    "DEPLOY_BLOCKED_KERNEL_TOUCH",
    "DEPLOY_STARTED",
    "DEPLOY_COMPLETED",
    "DEPLOY_FAILED",
    "DEPLOY_ROLLED_BACK",
    "DEPLOY_KERNEL_TOUCHED",
    "BACKTEST_STARTED",
    "BACKTEST_COMPLETED",
    "LLM_CALL_STUBBED",
    "CANARY_ENTERED",
    "CANARY_PASSED",
    "CANARY_FAILED",
    "CANARY_KERNEL_TOUCH_DETECTED",
    "PAPER_RUN_STARTED",
    "PAPER_RUN_STOPPED",
    "ORDER_PAPER_FILLED",
    "PAPER_RUN_REJECTED",
    "RULE_DESIGN_REQUESTED",
    "RULE_DESIGN_COMPLETED",
    "RULE_DESIGN_REJECTED",
    "RULE_DESIGN_DEPLOYED",
    "LIVE_PERFORMANCE_SNAPSHOT",
    "JUDGMENT_ADVISORY_APPLIED",
    "JUDGMENT_FALLBACK",
    "AUTO_TUNED_L1",
    "AUTO_TUNED_L2_CANARY_ENTERED",
    "AUTO_TUNED_L4_FORENSIC",
    "AUTO_TUNER_RUN",
    "AUTO_TUNED_CANARY_CANDIDATE",
    "AUTO_TUNED_CANARY_VALIDATED",
    "CIRCUIT_BREAKER_TRIPPED",
    "SIZING_DECISION",
]


class AuditPayload(BaseModel):
    """Base payload model. Subclasses pin a single `event_type` literal."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_type: EventType


class WorkerStartedPayload(AuditPayload):
    event_type: Literal["WORKER_STARTED"] = "WORKER_STARTED"
    pid: int
    config_path: str


class WorkerStoppedPayload(AuditPayload):
    event_type: Literal["WORKER_STOPPED"] = "WORKER_STOPPED"
    reason: str


class SecretsLoadedPayload(AuditPayload):
    event_type: Literal["SECRETS_LOADED"] = "SECRETS_LOADED"
    keys: list[str]


class RuleLoadPayload(AuditPayload):
    event_type: Literal["RULE_LOAD"] = "RULE_LOAD"
    rule_count: int
    rule_ids: list[str]


class OrderIntentPayload(AuditPayload):
    event_type: Literal["ORDER_INTENT"] = "ORDER_INTENT"
    rule_id: str
    symbol: str
    side: str
    order_type: str
    qty: int
    limit_price_usd: str | None = None


class OrderSubmittedPayload(AuditPayload):
    event_type: Literal["ORDER_SUBMITTED"] = "ORDER_SUBMITTED"
    kis_order_id: str
    submitted_at_utc: str


class OrderRejectedByGatePayload(AuditPayload):
    event_type: Literal["ORDER_REJECTED_BY_GATE"] = "ORDER_REJECTED_BY_GATE"
    gate: str
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderRejectedByBrokerPayload(AuditPayload):
    event_type: Literal["ORDER_REJECTED_BY_BROKER"] = "ORDER_REJECTED_BY_BROKER"
    broker_code: str
    broker_message: str


class FillPayload(AuditPayload):
    event_type: Literal["FILL"] = "FILL"
    kis_fill_id: str
    qty: int
    price_usd: str
    executed_at_utc: str
    commission_usd: str | None = None


class CancelPayload(AuditPayload):
    event_type: Literal["CANCEL"] = "CANCEL"
    reason: str


class ErrorPayload(AuditPayload):
    event_type: Literal["ERROR"] = "ERROR"
    where: str
    message: str
    exc_type: str | None = None


class ReconciliationOkPayload(AuditPayload):
    event_type: Literal["RECONCILIATION_OK"] = "RECONCILIATION_OK"
    started_at_utc: str
    finished_at_utc: str


class ReconciliationMismatchPayload(AuditPayload):
    event_type: Literal["RECONCILIATION_MISMATCH"] = "RECONCILIATION_MISMATCH"
    started_at_utc: str
    finished_at_utc: str
    diff: dict[str, Any]


class HaltSetPayload(AuditPayload):
    event_type: Literal["HALT_SET"] = "HALT_SET"
    reason: str


class HaltClearedPayload(AuditPayload):
    event_type: Literal["HALT_CLEARED"] = "HALT_CLEARED"
    cleared_by: str


class StrategyPausedPayload(AuditPayload):
    event_type: Literal["STRATEGY_PAUSED"] = "STRATEGY_PAUSED"
    reason: str
    metric_value: str


class StrategyPromotedPayload(AuditPayload):
    event_type: Literal["STRATEGY_PROMOTED"] = "STRATEGY_PROMOTED"
    from_stage: str
    to_stage: str


class DataQualityIssuePayload(AuditPayload):
    event_type: Literal["DATA_QUALITY_ISSUE"] = "DATA_QUALITY_ISSUE"
    issue: str
    detail: dict[str, Any] = Field(default_factory=dict)


class LlmCallPayload(AuditPayload):
    """Per FR-T03 / FR-T11: token counts and metadata only — no prompt text."""

    event_type: Literal["LLM_CALL"] = "LLM_CALL"
    model: str
    decision_class: str | None = None
    tokens_total: int
    cost_usd: str | None = None
    latency_ms: int
    error_class: str | None = None


class PriceTableLoadedPayload(AuditPayload):
    """Per spec 002 R-T3: pin the price-table version that priced each call."""

    event_type: Literal["PRICE_TABLE_LOADED"] = "PRICE_TABLE_LOADED"
    path: str
    sha256: str


class DeployBlockedKernelTouchPayload(AuditPayload):
    """Per constitution IX.B-1 / spec 006 FR-D13.

    Recorded when the deploy automation refuses to proceed because the
    proposed change set's diff intersects the Kernel manifest.
    """

    event_type: Literal["DEPLOY_BLOCKED_KERNEL_TOUCH"] = "DEPLOY_BLOCKED_KERNEL_TOUCH"
    sha_before: str
    sha_after: str
    touched_paths: list[str]
    touched_groups: list[str]
    triggered_by: str = "manual"  # "manual" | "auto-tuner"


DeployPhase = Literal[
    "precondition_lock",
    "precondition_dirty_tree",
    "precondition_secrets",
    "market_hours_guard",
    "pull",
    "kernel_check",
    "sync",
    "migrate",
    "dry_run",
    "stop_worker",
    "start_worker",
    "health_check",
    "canary_gate",
    "rollback",
]


class DeployStartedPayload(AuditPayload):
    """Per spec 006 FR-D03 — emitted before any side-effecting phase.

    The deploy's `correlation_id` lives in the row column, not in this
    payload — readers join via `WHERE correlation_id = ?`.
    """

    event_type: Literal["DEPLOY_STARTED"] = "DEPLOY_STARTED"
    sha_before: str
    sha_after: str
    branch: str
    triggered_by: Literal["manual", "auto-tuner"] = "manual"
    dry_run: bool = False
    allow_dirty: bool = False
    health_window_s: int = 90


class DeployCompletedPayload(AuditPayload):
    """Per spec 006 FR-D03 — emitted on success (exactly once per run)."""

    event_type: Literal["DEPLOY_COMPLETED"] = "DEPLOY_COMPLETED"
    sha_before: str
    sha_after: str
    phase: Literal["live", "dry_run"]
    duration_s: float


class DeployFailedPayload(AuditPayload):
    """Per spec 006 FR-D03 — emitted on any failure (exactly once per run)."""

    event_type: Literal["DEPLOY_FAILED"] = "DEPLOY_FAILED"
    sha_before: str
    sha_after: str | None = None
    phase: DeployPhase
    reason: str
    exit_code: int


class DeployRolledBackPayload(AuditPayload):
    """Per spec 006 FR-D08 — emitted after a successful rollback to sha_before."""

    event_type: Literal["DEPLOY_ROLLED_BACK"] = "DEPLOY_ROLLED_BACK"
    sha_before: str
    sha_after_failed: str
    rolled_back_phase: str


class DeployKernelTouchedPayload(AuditPayload):
    """Per spec 006 FR-D13 + constitution v3.0.0 IX.A — informational.

    Recorded when a deploy's diff intersects the Kernel manifest. Under
    v3.0.0 this is a forensic-attention signal, NOT a blocking gate;
    the deploy continues after this row lands. Replaces (in semantic,
    not in literal) the deprecated `DEPLOY_BLOCKED_KERNEL_TOUCH` event.
    """

    event_type: Literal["DEPLOY_KERNEL_TOUCHED"] = "DEPLOY_KERNEL_TOUCHED"
    sha_before: str
    sha_after: str
    touched_paths: list[str]
    touched_groups: list[str]
    triggered_by: Literal["manual", "auto-tuner"] = "manual"


class BacktestStartedPayload(AuditPayload):
    """Per spec 008 FR-B04 — run header recorded at backtest start."""

    event_type: Literal["BACKTEST_STARTED"] = "BACKTEST_STARTED"
    run_id: str
    invoker: Literal["cli", "canary"]
    ruleset_sha256: str
    dataset_version: str
    date_start: str
    date_end: str
    replay_seed: int
    fill_model: Literal["pessimistic_zero_slip"]
    judgment_mode: Literal["stub"]
    synthetic_shock: bool


class BacktestCompletedPayload(AuditPayload):
    """Per spec 008 FR-B05 — terminal row with summary metrics."""

    event_type: Literal["BACKTEST_COMPLETED"] = "BACKTEST_COMPLETED"
    run_id: str
    outcome: Literal["completed", "failed"]
    failure_reason: str | None = None
    aggregate_return_pct: str
    aggregate_max_drawdown_pct: str
    aggregate_sharpe: str
    total_orders: int
    total_fills: int
    total_gate_rejections: int


class LlmCallStubbedPayload(AuditPayload):
    """Per spec 008 FR-B08 — every judgment-point call during a backtest
    is short-circuited to a deterministic stub; this row records that.
    """

    event_type: Literal["LLM_CALL_STUBBED"] = "LLM_CALL_STUBBED"
    run_id: str
    decision_class: str
    input_sha256: str
    stubbed_branch: str


class CanaryEnteredPayload(AuditPayload):
    """Per spec 007 FR-C09 — run header at canary start.

    Carries the bands snapshot so a forensic reader can reconstruct
    which thresholds were in force without having to git-archaeology
    `config/canary_bands.toml` at the canary's `started_at`.
    """

    event_type: Literal["CANARY_ENTERED"] = "CANARY_ENTERED"
    canary_run_id: str
    candidate_rev: str
    baseline_rev: str
    tier: Literal["L2", "L3"]
    window_trading_days: int
    window_start_date: str
    window_end_date: str
    bands_snapshot: dict[str, Any]


class CanaryKernelTouchDetectedPayload(AuditPayload):
    """Per spec 007 FR-C08 (v3.0.0 semantics).

    Emitted when the candidate diff intersects `kernel.toml` paths. Under
    constitution v3.0.0 the Kernel is a forensic-attention list, NOT a
    barrier — this row records the forensic attention but does NOT halt
    the canary. The metric battery still runs and decides pass/fail.
    """

    event_type: Literal["CANARY_KERNEL_TOUCH_DETECTED"] = "CANARY_KERNEL_TOUCH_DETECTED"
    canary_run_id: str
    candidate_rev: str
    touched_groups: list[str]
    touched_files: list[str]


class CanaryPassedPayload(AuditPayload):
    """Per spec 007 FR-C09 — terminal row on successful canary."""

    event_type: Literal["CANARY_PASSED"] = "CANARY_PASSED"
    canary_run_id: str
    candidate_rev: str
    baseline_rev: str
    tier: Literal["L2", "L3"]
    finished_at: str
    artefact_path: str


class CanaryFailedPayload(AuditPayload):
    """Per spec 007 FR-C09 — terminal row on canary failure.

    `failing_metrics` is the subset of metric ids whose `inside_band`
    came back False; empty in pass would be a contradiction (which is
    why pass has its own event type).
    """

    event_type: Literal["CANARY_FAILED"] = "CANARY_FAILED"
    canary_run_id: str
    candidate_rev: str
    baseline_rev: str
    tier: Literal["L2", "L3"]
    finished_at: str
    failing_metrics: list[str]
    artefact_path: str


class PaperRunStartedPayload(AuditPayload):
    """Spec 009 FR-013 — paper-run 데몬 시작 단일 row.

    `WorkerStartedPayload`를 대체. live worker와 분리된 event_type을 가져
    paper-report가 paper 모드 이벤트만 집계할 수 있게 한다.
    """

    event_type: Literal["PAPER_RUN_STARTED"] = "PAPER_RUN_STARTED"
    pid: int
    config_path: str
    ruleset_sha256: str = Field(min_length=64, max_length=64)
    started_at_utc: str
    host: str


class PaperRunStoppedPayload(AuditPayload):
    """Spec 009 — paper-run 데몬 종료. `WorkerStoppedPayload` 대체."""

    event_type: Literal["PAPER_RUN_STOPPED"] = "PAPER_RUN_STOPPED"
    reason: Literal["normal_shutdown", "signal_received", "mutex_conflict", "crash"]
    stopped_at_utc: str
    session_started_event_id: int


class OrderPaperFilledPayload(AuditPayload):
    """Spec 009 FR-006 — 단일 차단 지점에서 시뮬 체결된 주문 1건.

    live의 `OrderSubmittedPayload` + `FillPayload` 쌍을 대체. paper 모드
    에서만 기록되며 KIS 주문 API 호출 없이 audit_log에만 남는다.
    """

    event_type: Literal["ORDER_PAPER_FILLED"] = "ORDER_PAPER_FILLED"
    rule_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    qty: int = Field(gt=0)
    simulated_fill_price_usd: str
    quote_source: Literal["ask", "bid", "last"]
    correlation_id: str
    paper_session_id: int
    # Spec 011 P4 (T015, FR-009) — 결정 시점 기준 시세(last). 슬리피지 측정의
    # 기준가로 쓰인다(체결가는 spread 를 가로지른 ask/bid, 기준가는 last). 추가-
    # 전용·옵션이라 과거 row 는 None 으로 읽혀 "측정 불가"로 분리된다(후방 호환).
    reference_price_usd: str | None = None


class RuleDesignRequestedPayload(AuditPayload):
    """Spec 010 FR-008 — 자동 룰 설계 호출 시작.

    `auto-invest design --intent "..."` 명령이 mutex check + KIS 잔고 조회
    이후, Claude 호출 직전에 1회 기록. 운영자의 원본 자연어 의도가 그대로
    저장되어 사후 추적 가능 (SC-004).
    """

    event_type: Literal["RULE_DESIGN_REQUESTED"] = "RULE_DESIGN_REQUESTED"
    intent: str
    requested_at_utc: str
    kis_balance_usd: str
    kis_holdings: list[dict[str, Any]]
    host: str


class RuleDesignCompletedPayload(AuditPayload):
    """Spec 010 — Claude 호출 + 정적 검증 + paper-run 1일분 통과 시 1회.

    Claude가 사용한 정량 매개변수(`interpretation`)와 생성된 룰 TOML 전체
    텍스트를 모두 보관 — 운영자가 사후 100% 재현 가능 (SC-004).
    """

    event_type: Literal["RULE_DESIGN_COMPLETED"] = "RULE_DESIGN_COMPLETED"
    intent: str
    interpretation: dict[str, Any]
    generated_rules_toml: str
    model_id: str
    tokens_input: int = Field(ge=0)
    tokens_output: int = Field(ge=0)
    cost_usd: str
    retry_index: int = Field(ge=1, le=3)
    paper_run_session_id: int | None = None


class RuleDesignRejectedPayload(AuditPayload):
    """Spec 010 — 자동 룰 설계의 모든 거부 사유.

    재시도 3회 카운트의 각 실패도 별도 row로 기록되어, 운영자가 "왜 룰 설계가
    실패했나"를 audit_log grep으로 즉시 확인 가능.
    """

    event_type: Literal["RULE_DESIGN_REJECTED"] = "RULE_DESIGN_REJECTED"
    reason: Literal[
        "parse_error",
        "whitelist_violation",
        "cap_violation",
        "backtest_fail",
        "paper_run_fail",
        "operator_declined",
        "max_retries",
        "mutex_conflict",
        "insufficient_balance",
        "kis_token_failed",
        "claude_api_error",
    ]
    detail: str
    retry_index: int | None = None
    conflicting_event_id: int | None = None


class RuleDesignDeployedPayload(AuditPayload):
    """Spec 010 — 운영자 OK 후 새 라이브 worker 시작 시 1회.

    `design_session_id`(대응 REQUESTED row seq)와 `live_session_id`(새 워커의
    WORKER_STARTED row seq)를 짝맞춰 두어, design → live 흐름을 audit_log에서
    즉시 추적 가능.
    """

    event_type: Literal["RULE_DESIGN_DEPLOYED"] = "RULE_DESIGN_DEPLOYED"
    design_session_id: int
    live_session_id: int
    deployed_at_utc: str
    total_capital_usd: str


class PaperRunRejectedPayload(AuditPayload):
    """Spec 009 FR-015 — paper-run 시작 또는 시뮬 체결이 거부된 경우.

    mutex 충돌, quote 결측 등 paper-run이 정상 진행 못 한 사건을 추적.
    forensic grep으로 운영자가 "어제 paper-run 왜 안 떴지?"를 즉시 확인.
    """

    event_type: Literal["PAPER_RUN_REJECTED"] = "PAPER_RUN_REJECTED"
    attempted_mode: Literal["paper", "live"]
    reason: Literal["mutex_conflict", "no_quote_field", "other"]
    conflicting_event_id: int | None = None
    conflicting_session_started_at: str | None = None
    detail: str


class LivePerformanceSnapshotPayload(AuditPayload):
    """Spec 011 FR-014 (T014) — 성과 평가 한 번의 결과를 남기는 추가-전용 스냅샷.

    `auto-invest performance --snapshot` 으로만 기록되며 기본 동작은 순수 계산
    (스냅샷 미기록)이다. 기존 이벤트 타입·row 를 전혀 건드리지 않는 K4 추가
    변경이라 append-only 불변량(constitution IV)을 깨지 않는다. 미래 자율 튜너
    (spec 005)가 시계열로 소비할 기계 판독 신호 면 — 손익·수익률·위험조정 지표를
    `PerformanceReport` 와 같은 정의(문자열 Decimal)로 담는다. 거래 0건이면 위험
    조정 필드는 null."""

    event_type: Literal["LIVE_PERFORMANCE_SNAPSHOT"] = "LIVE_PERFORMANCE_SNAPSHOT"
    mode: Literal["paper", "live"]
    schema_version: str
    since_utc: str
    until_utc: str
    fills_count: int
    gross_invested_usd: str
    realized_pnl_usd: str
    unrealized_pnl_usd: str
    total_pnl_usd: str
    return_pct: str | None = None
    closed_trades: int = 0
    win_rate: str | None = None
    sharpe_ratio: str | None = None
    max_drawdown_pct: str | None = None
    total_return_pct: str | None = None
    computed_at_utc: str


class JudgmentAdvisoryAppliedPayload(AuditPayload):
    """Spec 004: 판단 지점 자문이 결정론적으로 게이트에 적용된 기록.

    `advisory` 는 자문 요약(action/stance + confidence)이며 프롬프트/응답 본문이
    아니다(헌법 V). `applied_decision` 은 게이트에 실제 적용된 결정 표식
    (`skip`/`size_down:0.5`/`block_buy`/`no_effect`). LLM_CALL 과 같은
    correlation_id 로 짝지어진다(append 의 correlation_id 인자).
    """

    event_type: Literal["JUDGMENT_ADVISORY_APPLIED"] = "JUDGMENT_ADVISORY_APPLIED"
    decision_class: str
    advisory: str
    applied_decision: str
    canary_cohort: bool = False


class JudgmentFallbackPayload(AuditPayload):
    """Spec 004: 판단 지점이 결정론적 폴백으로 전환된 기록.

    LLM 호출 실패/타임아웃/서킷오픈/예산초과/스키마위반/공급원부재 시 거래는
    막히지 않고 v1 동작으로 진행하며 그 사실을 추가-전용으로 남긴다(SC-001).
    """

    event_type: Literal["JUDGMENT_FALLBACK"] = "JUDGMENT_FALLBACK"
    decision_class: str
    reason: Literal[
        "failure",
        "timeout",
        "circuit_open",
        "budget_exceeded",
        "schema_invalid",
        "no_source",
    ]


class AutoTunedL1Payload(AuditPayload):
    """Spec 005: 자율 튜너가 저위험(L1) 설정 변경을 자동 적용한 기록.

    v1 적용 노브는 KPI 임계값 조이기(`config/llm_kpi_thresholds.toml`의
    `tier_b`)뿐이다. `old_value`/`new_value`(문자열 Decimal)로 가역성을
    보장한다(FR-A13). `session_date`는 멱등 dedup 키(R-8). 기존 이벤트·row
    를 건드리지 않는 K4 추가-전용 변경이라 append-only 불변량(헌법 IV)을
    깨지 않는다.
    """

    event_type: Literal["AUTO_TUNED_L1"] = "AUTO_TUNED_L1"
    session_date: str
    detection_rule: str
    kpi_name: str
    config_key: str
    old_value: str
    new_value: str
    tier_before: str
    tier_after: str
    window: str


class AutoTunedL2CanaryEnteredPayload(AuditPayload):
    """Spec 005: L2/L3 후보를 캐너리 진입 후보로 기록(튜너는 동기 통과 안 함).

    실제 캐너리 승격/실패(CANARY_PASSED/CANARY_FAILED)는 스펙 007 엔진이
    별도로 수행한다. 이 이벤트는 "튜너가 이 변경을 캐너리 대상으로 식별했다"
    는 포렌식 기록일 뿐 주문 경로에 닿지 않는다.
    """

    event_type: Literal["AUTO_TUNED_L2_CANARY_ENTERED"] = "AUTO_TUNED_L2_CANARY_ENTERED"
    session_date: str
    candidate_id: str
    authority_tier: Literal["L2", "L3"]
    detection_rule: str
    proposed_change: str
    target_paths: list[str]


class AutoTunedL4ForensicPayload(AuditPayload):
    """Spec 005: Kernel 터치 후보의 포렌식 콜아웃(인간 머지 대기).

    튜너는 Kernel 파일을 절대 자동 적용하지 않는다(FR-A06). 대상 파일이
    kernel.toml 매니페스트에 닿으면 분류와 무관하게 L4로 강등하고 이 이벤트로
    forensic 기록만 남긴다. Kernel 변경은 운영자 지시 세션의 명시적 작업.
    """

    event_type: Literal["AUTO_TUNED_L4_FORENSIC"] = "AUTO_TUNED_L4_FORENSIC"
    session_date: str
    candidate_id: str
    detection_rule: str
    kernel_groups: list[str]
    target_paths: list[str]
    reason: str


class AutoTunerRunPayload(AuditPayload):
    """Spec 005: 튜너 한 번 실행의 요약(apply 모드에서만 기록).

    dry-run은 어떤 감사도 쓰지 않는다(read-only 보장, SC-A03).
    """

    event_type: Literal["AUTO_TUNER_RUN"] = "AUTO_TUNER_RUN"
    session_date: str
    mode: Literal["dry_run", "apply"]
    candidates_count: int
    applied_count: int
    canary_count: int
    l4_count: int
    skipped_count: int


class AutoTunedCanaryCandidatePayload(AuditPayload):
    """Spec 012: L2/L3 후보를 캐너리가 평가 가능하게 구체화한 기록.

    기존 `AUTO_TUNED_L2_CANARY_ENTERED`(투입 식별 마커)와 달리, 이 이벤트는
    캐너리에 실제 투입 가능한 구체 변경(old→new + 권장 tier/window)을 담는다.
    K4 추가-전용 — 기존 이벤트·row 미수정(헌법 IV).
    """

    event_type: Literal["AUTO_TUNED_CANARY_CANDIDATE"] = "AUTO_TUNED_CANARY_CANDIDATE"
    session_date: str
    candidate_id: str
    detection_rule: str
    authority_tier: Literal["L2", "L3"]
    target_path: str
    config_key: str
    old_value: str
    new_value: str
    recommended_tier: str
    recommended_window_days: int


class AutoTunedCanaryValidatedPayload(AuditPayload):
    """Spec 012: 후보를 하드닝 캐너리로 검증한 결과.

    안전 불변: `promoted` 는 항상 False — 캐너리 합격은 검증일 뿐 자동 승격이
    아니다(헌법 IX.B-2). 라이브 승격은 운영자/스펙 006 게이트 전용. 이 이벤트는
    "검증됨, 승격 대기"의 포렌식 기록일 뿐 주문/배포 경로에 닿지 않는다.
    K4 추가-전용.
    """

    event_type: Literal["AUTO_TUNED_CANARY_VALIDATED"] = "AUTO_TUNED_CANARY_VALIDATED"
    session_date: str
    candidate_id: str
    outcome: Literal["passed", "failed", "skipped", "internal_error"]
    canary_run_id: str | None = None
    candidate_rev: str | None = None
    baseline_rev: str | None = None
    failing_metrics: list[str] = Field(default_factory=list)
    skip_reason: str | None = None
    promoted: bool = False


class CircuitBreakerTrippedPayload(AuditPayload):
    """Spec 014: 손실 서킷 브레이커가 트립해 워커가 자동 halt 한 기록.

    추가-전용 K4 이벤트 — 기존 이벤트/row 를 전혀 건드리지 않는다(헌법 IV). 트립의
    유일한 부수효과는 halt 플래그 세팅 + 이 row append 다(주문/청산 0건). 손익은
    스펙 011 성과 엔진 정의로 계산된 값(문자열 Decimal). `breached` 는 걸린 한도
    id 목록({"daily_loss", "total_drawdown"} 부분집합).
    """

    event_type: Literal["CIRCUIT_BREAKER_TRIPPED"] = "CIRCUIT_BREAKER_TRIPPED"
    mode: Literal["paper", "live"]
    tripped_at_utc: str
    starting_capital_usd: str
    realized_pnl_today_usd: str
    current_equity_usd: str
    breached: list[str]
    daily_loss_limit_pct: str
    max_total_drawdown_pct: str
    reason: str


class SizingDecisionPayload(AuditPayload):
    """Spec 018: 사이징 결정 포렌식 기록 (K4 추가-전용).

    사이징 모드가 fixed 가 아닌 모든 주문에서 order_router 가 append 한다.
    실현 변동성·역변동성 그룹 가중치·상관 헤어컷·최종 수량을 한 row 에 담아
    사이징 파이프라인 전체를 사후 재현할 수 있게 한다(헌법 X.2 단일 잣대).
    final_qty=0 도 기록해 사이징으로 스킵된 주문의 원인을 추적할 수 있다.
    """

    event_type: Literal["SIZING_DECISION"] = "SIZING_DECISION"
    sizing_mode: str
    base_qty: int
    final_qty: int
    realized_vol_pct: str | None = None
    vol_scale: str | None = None
    group_scale: str


AnyPayload = (
    WorkerStartedPayload
    | WorkerStoppedPayload
    | SecretsLoadedPayload
    | RuleLoadPayload
    | OrderIntentPayload
    | OrderSubmittedPayload
    | OrderRejectedByGatePayload
    | OrderRejectedByBrokerPayload
    | FillPayload
    | CancelPayload
    | ErrorPayload
    | ReconciliationOkPayload
    | ReconciliationMismatchPayload
    | HaltSetPayload
    | HaltClearedPayload
    | StrategyPausedPayload
    | StrategyPromotedPayload
    | DataQualityIssuePayload
    | LlmCallPayload
    | PriceTableLoadedPayload
    | DeployBlockedKernelTouchPayload
    | DeployStartedPayload
    | DeployCompletedPayload
    | DeployFailedPayload
    | DeployRolledBackPayload
    | DeployKernelTouchedPayload
    | BacktestStartedPayload
    | BacktestCompletedPayload
    | LlmCallStubbedPayload
    | CanaryEnteredPayload
    | CanaryKernelTouchDetectedPayload
    | CanaryPassedPayload
    | CanaryFailedPayload
    | PaperRunStartedPayload
    | PaperRunStoppedPayload
    | OrderPaperFilledPayload
    | PaperRunRejectedPayload
    | RuleDesignRequestedPayload
    | RuleDesignCompletedPayload
    | RuleDesignRejectedPayload
    | RuleDesignDeployedPayload
    | LivePerformanceSnapshotPayload
    | JudgmentAdvisoryAppliedPayload
    | JudgmentFallbackPayload
    | AutoTunedL1Payload
    | AutoTunedL2CanaryEnteredPayload
    | AutoTunedL4ForensicPayload
    | AutoTunerRunPayload
    | AutoTunedCanaryCandidatePayload
    | AutoTunedCanaryValidatedPayload
    | CircuitBreakerTrippedPayload
    | SizingDecisionPayload
)


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def append(
    conn: sqlite3.Connection,
    payload: AuditPayload,
    *,
    rule_id: str | None = None,
    symbol: str | None = None,
    correlation_id: str | None = None,
    ts_utc: str | None = None,
) -> int:
    """Append a single audit row. Returns the assigned `seq`.

    `ts_utc` is filled with the current UTC time at millisecond
    precision when omitted. The `payload` model's `event_type` literal
    becomes the row's discriminator column.
    """
    payload_json = payload.model_dump_json()
    ts = ts_utc or _utcnow_iso_ms()
    cursor = conn.execute(
        """
        INSERT INTO audit_log
            (ts_utc, event_type, rule_id, symbol, payload_json, correlation_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ts, payload.event_type, rule_id, symbol, payload_json, correlation_id),
    )
    return int(cursor.lastrowid)


def read_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return every audit row in seq order. Test/forensics use only."""
    return list(conn.execute("SELECT * FROM audit_log ORDER BY seq"))


def read_by_correlation(
    conn: sqlite3.Connection,
    correlation_id: str,
) -> list[sqlite3.Row]:
    """Return audit rows linked by correlation_id, in seq order."""
    return list(
        conn.execute(
            "SELECT * FROM audit_log WHERE correlation_id = ? ORDER BY seq",
            (correlation_id,),
        )
    )


def parse_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Parse a row's `payload_json` back into a dict."""
    return json.loads(row["payload_json"])
