"""End-of-session reconciliation (T049, FR-007).

Compares the worker's local view of positions against the broker's
report. Three possible outcomes:

  * OK            — perfectly aligned; logs RECONCILIATION_OK.
  * MISMATCH      — at least one position differs; logs
                    RECONCILIATION_MISMATCH with a structured diff and
                    sets the halt flag so no further orders fire until
                    the operator clears the halt.
  * INCONCLUSIVE  — the broker call failed; logs an ERROR audit row but
                    does NOT halt (the issue is environmental, not a
                    state-drift signal).

Per `data-model.md`, the reconciliation_runs row is inserted exactly
once per run, at completion. The "started" event is implicit in the
row's `started_at_utc` column.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from auto_invest.broker.client import ResilientClient
from auto_invest.broker.overseas import (
    US_ORDER_EXCHANGES,
    get_balance_resolving_market,
    get_positions_resolving_market,
)
from auto_invest.persistence import audit
from auto_invest.persistence import positions as positions_mod
from auto_invest.persistence.audit import (
    ErrorPayload,
    ReconciliationMismatchPayload,
    ReconciliationOkPayload,
)
from auto_invest.worker.halt import set_halt


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class ReconciliationOutcome:
    state: str  # "OK" | "MISMATCH" | "INCONCLUSIVE"
    started_at_utc: str
    finished_at_utc: str
    diff: dict[str, Any] | None = None
    error: str | None = None


def _record_run(
    conn: sqlite3.Connection,
    *,
    started_at_utc: str,
    finished_at_utc: str,
    result: str,
    diff: dict[str, Any] | None,
) -> None:
    conn.execute(
        """
        INSERT INTO reconciliation_runs
            (started_at_utc, finished_at_utc, result, mismatch_payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            started_at_utc,
            finished_at_utc,
            result,
            json.dumps(diff) if diff else None,
        ),
    )


def _compute_diff(
    local: list[positions_mod.Position],
    broker: list,
    *,
    broker_cash_usd: Decimal,
    cash_tolerance_usd: Decimal,
) -> dict[str, Any] | None:
    """Return a structured diff payload, or None when everything matches."""
    local_by_symbol = {p.symbol: p for p in local}
    broker_by_symbol = {p.symbol: p for p in broker}

    position_diffs: list[dict[str, Any]] = []
    for symbol in sorted(set(local_by_symbol) | set(broker_by_symbol)):
        local_qty = local_by_symbol[symbol].qty if symbol in local_by_symbol else 0
        broker_qty = broker_by_symbol[symbol].qty if symbol in broker_by_symbol else 0
        if local_qty != broker_qty:
            position_diffs.append(
                {
                    "symbol": symbol,
                    "local_qty": local_qty,
                    "broker_qty": broker_qty,
                }
            )

    # Cash diff vs broker — for v1 we do not maintain a local cash
    # tally, so the broker's value is reported informationally only.
    cash_diffs: list[dict[str, Any]] = []
    if broker_cash_usd < 0:
        cash_diffs.append(
            {"reason": "negative_cash_balance", "broker_cash_usd": str(broker_cash_usd)}
        )
    _ = cash_tolerance_usd  # placeholder; reserved for future local-cash tracking.

    if not position_diffs and not cash_diffs:
        return None
    return {"position_diffs": position_diffs, "cash_diffs": cash_diffs}


async def run_reconciliation(
    conn: sqlite3.Connection,
    broker: ResilientClient,
    *,
    access_token: str,
    app_key: str,
    app_secret: str,
    account: str,
    halt_path: Path,
    markets: Sequence[str] = US_ORDER_EXCHANGES,
    cash_tolerance_usd: Decimal = Decimal("1.00"),
) -> ReconciliationOutcome:
    # 브로커 보유·잔고는 모든 미국 거래소(NASD·NYSE·AMEX)를 훑어 합쳐 조회한다 — 멀티에셋
    # 유니버스(SPY·GLD=AMEX, IEF=NASD)에서 다른 거래소 종목이 단일 거래소 조회에서 빠지면
    # 장부엔 있는데 브로커엔 없는 것처럼 보여(ledger_only) 허위 drift/halt 가 난다. 종목별
    # 중복 제거로 KIS 동작과 무관하게 정확. 거래소별 조회 오류는 아래 except 가 INCONCLUSIVE 로.
    started_at = _utcnow_iso_ms()

    try:
        broker_positions = await get_positions_resolving_market(
            broker,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account,
            markets=markets,
        )
        broker_balance = await get_balance_resolving_market(
            broker,
            access_token=access_token,
            app_key=app_key,
            app_secret=app_secret,
            account=account,
            markets=markets,
        )
    except Exception as exc:  # noqa: BLE001
        finished_at = _utcnow_iso_ms()
        audit.append(
            conn,
            ErrorPayload(
                where="reconciliation",
                message=str(exc),
                exc_type=type(exc).__name__,
            ),
        )
        _record_run(
            conn,
            started_at_utc=started_at,
            finished_at_utc=finished_at,
            result="INCONCLUSIVE",
            diff=None,
        )
        return ReconciliationOutcome(
            state="INCONCLUSIVE",
            started_at_utc=started_at,
            finished_at_utc=finished_at,
            error=str(exc),
        )

    local = positions_mod.get_all_positions(conn)
    diff = _compute_diff(
        local,
        list(broker_positions),
        broker_cash_usd=broker_balance.cash_usd,
        cash_tolerance_usd=cash_tolerance_usd,
    )
    finished_at = _utcnow_iso_ms()

    if diff is None:
        audit.append(
            conn,
            ReconciliationOkPayload(
                started_at_utc=started_at,
                finished_at_utc=finished_at,
            ),
        )
        _record_run(
            conn,
            started_at_utc=started_at,
            finished_at_utc=finished_at,
            result="OK",
            diff=None,
        )
        return ReconciliationOutcome(
            state="OK",
            started_at_utc=started_at,
            finished_at_utc=finished_at,
        )

    audit.append(
        conn,
        ReconciliationMismatchPayload(
            started_at_utc=started_at,
            finished_at_utc=finished_at,
            diff=diff,
        ),
    )
    _record_run(
        conn,
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        result="MISMATCH",
        diff=diff,
    )
    set_halt(halt_path, f"reconciliation mismatch: {len(diff['position_diffs'])} position(s)")
    return ReconciliationOutcome(
        state="MISMATCH",
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        diff=diff,
    )
