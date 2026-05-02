"""Integration tests for the reconciliation runner (T048, T052)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.enums import Side
from auto_invest.persistence import audit, db
from auto_invest.persistence import positions as positions_mod
from auto_invest.reconciliation.runner import run_reconciliation
from auto_invest.worker.halt import is_halted

BASE = "https://api.example"
ACCOUNT = "1234567801"


@asynccontextmanager
async def _broker(tmp_path: Path) -> AsyncIterator[tuple]:
    halt_path = tmp_path / "halt.flag"
    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)
    async with httpx.AsyncClient(base_url=BASE) as inner:
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        try:
            yield client, conn, halt_path
        finally:
            conn.close()


def _seed_local_position(
    conn,
    *,
    symbol: str,
    qty: int,
    avg_cost: str = "100",
) -> None:
    positions_mod.update_from_fill(
        conn,
        symbol=symbol,
        side=Side.BUY,
        qty=qty,
        price_usd=Decimal(avg_cost),
        ts_utc="2026-05-02T13:31:00.000Z",
    )


def _balance_payload(
    *,
    positions: list[dict],
    cash_usd: str = "1000",
) -> dict:
    return {
        "output1": positions,
        "output2": {
            "frcr_dncl_amt_2": cash_usd,
            "tot_evlu_pfls_amt": "0",
        },
    }


# ----------------------------------------------------- match path


@pytest.mark.asyncio
async def test_reconciliation_ok_when_positions_match(tmp_path: Path):
    async with _broker(tmp_path) as (client, conn, halt_path):
        _seed_local_position(conn, symbol="AAPL", qty=10)

        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-balance").mock(
                return_value=httpx.Response(
                    200,
                    json=_balance_payload(
                        positions=[
                            {
                                "ovrs_pdno": "AAPL",
                                "ovrs_cblc_qty": "10",
                                "pchs_avg_pric": "100",
                            }
                        ]
                    ),
                )
            )

            outcome = await run_reconciliation(
                conn,
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
                halt_path=halt_path,
            )

        assert outcome.state == "OK"
        assert outcome.diff is None
        assert is_halted(halt_path) is False
        events = [r["event_type"] for r in audit.read_all(conn)]
        assert "RECONCILIATION_OK" in events
        run_row = conn.execute(
            "SELECT result FROM reconciliation_runs"
        ).fetchone()
        assert run_row["result"] == "OK"


# ----------------------------------------------------- mismatch path


@pytest.mark.asyncio
async def test_reconciliation_mismatch_qty_halts_worker(tmp_path: Path):
    async with _broker(tmp_path) as (client, conn, halt_path):
        # Local says 10 AAPL, broker says 7 AAPL.
        _seed_local_position(conn, symbol="AAPL", qty=10)

        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-balance").mock(
                return_value=httpx.Response(
                    200,
                    json=_balance_payload(
                        positions=[
                            {
                                "ovrs_pdno": "AAPL",
                                "ovrs_cblc_qty": "7",
                                "pchs_avg_pric": "100",
                            }
                        ]
                    ),
                )
            )

            outcome = await run_reconciliation(
                conn,
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
                halt_path=halt_path,
            )

        assert outcome.state == "MISMATCH"
        assert outcome.diff is not None
        position_diffs = outcome.diff["position_diffs"]
        assert position_diffs == [
            {"symbol": "AAPL", "local_qty": 10, "broker_qty": 7}
        ]
        assert is_halted(halt_path) is True
        events = [r["event_type"] for r in audit.read_all(conn)]
        assert "RECONCILIATION_MISMATCH" in events
        assert "HALT_SET" not in events  # halt is filesystem-only at this layer


@pytest.mark.asyncio
async def test_reconciliation_mismatch_when_local_has_unknown_symbol(tmp_path: Path):
    async with _broker(tmp_path) as (client, conn, halt_path):
        _seed_local_position(conn, symbol="AAPL", qty=5)
        # Broker reports zero positions.
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-balance").mock(
                return_value=httpx.Response(
                    200, json=_balance_payload(positions=[])
                )
            )
            outcome = await run_reconciliation(
                conn,
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
                halt_path=halt_path,
            )
        assert outcome.state == "MISMATCH"
        assert outcome.diff["position_diffs"][0]["symbol"] == "AAPL"


# ----------------------------------------------------- inconclusive path


@pytest.mark.asyncio
async def test_reconciliation_inconclusive_on_broker_error(tmp_path: Path):
    async with _broker(tmp_path) as (client, conn, halt_path):
        _seed_local_position(conn, symbol="AAPL", qty=10)
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-balance").mock(
                return_value=httpx.Response(503, json={"err": "x"})
            )
            outcome = await run_reconciliation(
                conn,
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
                halt_path=halt_path,
            )
        assert outcome.state == "INCONCLUSIVE"
        # INCONCLUSIVE does NOT halt — it's an environmental error.
        assert is_halted(halt_path) is False
        events = [r["event_type"] for r in audit.read_all(conn)]
        assert "ERROR" in events
        run_row = conn.execute(
            "SELECT result FROM reconciliation_runs"
        ).fetchone()
        assert run_row["result"] == "INCONCLUSIVE"
