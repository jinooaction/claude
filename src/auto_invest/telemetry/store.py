"""token_usage append-only writer + integrity check (FR-T02, FR-T04, FR-T12).

The single sanctioned writer for the `token_usage` table. Mutating
prior rows is forbidden by SQLite triggers in migration 0002.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class TokenUsage:
    """One metered LLM call.

    Per FR-T11, this struct carries no prompt or response content —
    only counts, model, decision class, and error class.
    """

    model: str
    decision_class: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: str | None
    latency_ms: int
    error_class: str | None
    correlation_id: str
    ts_utc: str

    @property
    def tokens_total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


def append_token_usage(conn: sqlite3.Connection, usage: TokenUsage) -> int:
    """Append a single token_usage row. Returns the assigned `seq`."""
    cursor = conn.execute(
        """
        INSERT INTO token_usage
            (ts_utc, model, decision_class,
             input_tokens, output_tokens,
             cache_read_tokens, cache_write_tokens,
             cost_usd, latency_ms, error_class, correlation_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            usage.ts_utc,
            usage.model,
            usage.decision_class,
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_tokens,
            usage.cache_write_tokens,
            usage.cost_usd,
            usage.latency_ms,
            usage.error_class,
            usage.correlation_id,
        ),
    )
    return int(cursor.lastrowid)


@dataclass(frozen=True)
class IntegrityMismatch:
    correlation_id: str
    kind: str  # "orphan_token_usage" | "orphan_llm_call"


def integrity_check(conn: sqlite3.Connection) -> list[IntegrityMismatch]:
    """Find correlation_ids present in one table but not the other (FR-T12).

    Both directions are checked:
      * a `token_usage` row whose correlation_id has no matching
        `LLM_CALL` audit row -> kind="orphan_token_usage".
      * an `LLM_CALL` audit row whose correlation_id has no matching
        `token_usage` row -> kind="orphan_llm_call".
    """
    out: list[IntegrityMismatch] = []
    rows_a = conn.execute(
        """
        SELECT DISTINCT t.correlation_id
        FROM token_usage t
        LEFT JOIN audit_log a
          ON a.correlation_id = t.correlation_id
         AND a.event_type = 'LLM_CALL'
        WHERE a.correlation_id IS NULL
        """
    ).fetchall()
    out.extend(
        IntegrityMismatch(correlation_id=row["correlation_id"], kind="orphan_token_usage")
        for row in rows_a
    )
    rows_b = conn.execute(
        """
        SELECT DISTINCT a.correlation_id
        FROM audit_log a
        LEFT JOIN token_usage t
          ON t.correlation_id = a.correlation_id
        WHERE a.event_type = 'LLM_CALL'
          AND t.correlation_id IS NULL
        """
    ).fetchall()
    out.extend(
        IntegrityMismatch(correlation_id=row["correlation_id"], kind="orphan_llm_call")
        for row in rows_b
    )
    return out


__all__ = [
    "IntegrityMismatch",
    "TokenUsage",
    "_utcnow_iso_ms",
    "append_token_usage",
    "integrity_check",
]
