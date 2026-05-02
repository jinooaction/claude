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
