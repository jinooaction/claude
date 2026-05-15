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
