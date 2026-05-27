"""Integration tests for live fill ingestion orchestrator (spec 015, T007/T013)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.execution.fill_sync import sync_fills
from auto_invest.persistence import audit, db
from auto_invest.persistence import positions as positions_mod

BASE = "https://api.example"
ACCOUNT = "1234567801"
CCNL = "/uapi/overseas-stock/v1/trading/inquire-ccnl"


@asynccontextmanager
async def _broker(tmp_path: Path) -> AsyncIterator[tuple]:
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
            yield client, conn
        finally:
            conn.close()


def _seed_order(
    conn,
    *,
    corr: str = "ord-1",
    kis: str = "K1",
    symbol: str = "AAPL",
    side: str = "BUY",
    qty: int = 100,
    state: str = "SUBMITTED",
) -> None:
    conn.execute(
        """
        INSERT INTO orders
            (correlation_id, rule_id, symbol, side, order_type, qty, state, kis_order_id)
        VALUES (?, 'r1', ?, ?, 'LIMIT', ?, ?, ?)
        """,
        (corr, symbol, side, qty, state, kis),
    )
    # spec 011 라이브 FILL 조인을 위해 ORDER_INTENT 도 남긴다.
    from auto_invest.persistence.audit import OrderIntentPayload

    audit.append(
        conn,
        OrderIntentPayload(
            rule_id="r1", symbol=symbol, side=side, order_type="LIMIT", qty=qty
        ),
        rule_id="r1",
        symbol=symbol,
        correlation_id=corr,
    )


def _ccnl(rows: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"output": rows})


async def _sync(client, conn):
    return await sync_fills(
        conn,
        client,
        access_token="t",
        app_key="k",
        app_secret="s",
        account=ACCOUNT,
    )


def _fills_total(conn, corr: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(qty),0) AS t FROM fills WHERE order_correlation_id=?",
        (corr,),
    ).fetchone()
    return int(row["t"])


def _state(conn, corr: str) -> str:
    return conn.execute(
        "SELECT state FROM orders WHERE correlation_id=?", (corr,)
    ).fetchone()["state"]


@pytest.mark.asyncio
async def test_full_fill_recorded(tmp_path: Path) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, qty=100)
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(
                return_value=_ccnl(
                    [{"odno": "K1", "pdno": "AAPL", "ft_ccld_qty": "100",
                      "ft_ccld_unpr3": "150"}]
                )
            )
            res = await _sync(client, conn)
        assert res.fills_applied == 1
        assert _fills_total(conn, "ord-1") == 100
        assert _state(conn, "ord-1") == "FILLED"
        pos = positions_mod.get_position(conn, "AAPL")
        assert pos is not None and pos.qty == 100


@pytest.mark.asyncio
async def test_partial_then_complete(tmp_path: Path) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, qty=100)
        with respx.mock(base_url=BASE) as mock:
            route = mock.get(CCNL)
            route.mock(return_value=_ccnl(
                [{"odno": "K1", "pdno": "AAPL", "ft_ccld_qty": "40", "ft_ccld_unpr3": "150"}]
            ))
            await _sync(client, conn)
            assert _fills_total(conn, "ord-1") == 40
            assert _state(conn, "ord-1") == "PARTIALLY_FILLED"

            route.mock(return_value=_ccnl(
                [{"odno": "K1", "pdno": "AAPL", "ft_ccld_qty": "100", "ft_ccld_unpr3": "150"}]
            ))
            await _sync(client, conn)
            assert _fills_total(conn, "ord-1") == 100
            assert _state(conn, "ord-1") == "FILLED"
            # fills 두 줄(40 + 60).
            n = conn.execute(
                "SELECT COUNT(*) AS c FROM fills WHERE order_correlation_id='ord-1'"
            ).fetchone()["c"]
            assert n == 2


@pytest.mark.asyncio
async def test_idempotent_resync(tmp_path: Path) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, qty=100)
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=_ccnl(
                [{"odno": "K1", "pdno": "AAPL", "ft_ccld_qty": "100", "ft_ccld_unpr3": "150"}]
            ))
            await _sync(client, conn)
            res2 = await _sync(client, conn)
        # 두 번째 동기화는 새 FILL 0건, 여전히 합계 100.
        assert res2.fills_applied == 0
        assert _fills_total(conn, "ord-1") == 100
        assert positions_mod.get_position(conn, "AAPL").qty == 100


@pytest.mark.asyncio
async def test_no_open_orders_skips_broker(tmp_path: Path) -> None:
    async with _broker(tmp_path) as (client, conn):
        # 열린 주문 없음 → 브로커 호출 안 함.
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            route = mock.get(CCNL).mock(return_value=_ccnl([]))
            res = await _sync(client, conn)
        assert res.polled is False
        assert route.called is False


@pytest.mark.asyncio
async def test_broker_error_is_isolated(tmp_path: Path) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, qty=100)
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=httpx.Response(503, json={"err": "x"}))
            res = await _sync(client, conn)
        # 예외를 삼키고 ERROR 감사를 남기되 상태는 그대로(거래 무중단).
        assert res.error is not None
        assert _state(conn, "ord-1") == "SUBMITTED"
        errs = [
            r for r in audit.read_all(conn) if r["event_type"] == "ERROR"
        ]
        assert any("fill_sync" in (r["payload_json"] or "") for r in errs)


@pytest.mark.asyncio
async def test_terminal_partial_expires_with_cancel(tmp_path: Path) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, qty=100)
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=_ccnl(
                [{"odno": "K1", "pdno": "AAPL", "ft_ccld_qty": "40", "ft_ccld_unpr3": "150",
                  "nccs_qty": "60", "prcs_stat_name": "취소완료"}]
            ))
            await _sync(client, conn)
        assert _fills_total(conn, "ord-1") == 40
        assert _state(conn, "ord-1") == "EXPIRED"
        cancels = [r for r in audit.read_all(conn) if r["event_type"] == "CANCEL"]
        assert len(cancels) == 1
