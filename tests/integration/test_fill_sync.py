"""Integration tests for live fill ingestion orchestrator (spec 015, T007/T013)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.config.enums import Side
from auto_invest.execution import fill_sync as fill_sync_mod
from auto_invest.execution.fill_sync import (
    FillPlan,
    PlannedFill,
    PlannedTransition,
    apply_fill_plan,
    sync_fills,
)
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
    kis: str | None = "K1",
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


def _recovered_events(conn, corr: str) -> list[dict]:
    return [
        audit.parse_payload(r)
        for r in audit.read_by_correlation(conn, corr)
        if r["event_type"] == "ORDER_SUBMISSION_RECOVERED"
    ]


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


def _fill_audit_count(conn, corr: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM audit_log
        WHERE event_type='FILL' AND correlation_id=?
        """,
        (corr,),
    ).fetchone()
    return int(row["c"])


def _state(conn, corr: str) -> str:
    return conn.execute(
        "SELECT state FROM orders WHERE correlation_id=?", (corr,)
    ).fetchone()["state"]


def _planned_fill(
    *,
    corr: str = "ord-1",
    kis: str = "K1",
    symbol: str = "AAPL",
    side: str = "BUY",
    qty: int = 100,
    price: str = "150",
    fill_id: str = "K1:100",
) -> PlannedFill:
    return PlannedFill(
        correlation_id=corr,
        kis_order_id=kis,
        symbol=symbol,
        side=side,
        rule_id="r1",
        qty=qty,
        price_usd=Decimal(price),
        kis_fill_id=fill_id,
    )


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


def test_apply_plan_skips_duplicate_fill_without_cache_or_audit(tmp_path: Path) -> None:
    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)
    try:
        _seed_order(conn, qty=100)
        conn.execute(
            """
            INSERT INTO fills
                (order_correlation_id, kis_fill_id, qty, price_usd, executed_at_utc)
            VALUES ('ord-1', 'K1:100', 100, '150', '2026-05-26T15:00:00.000Z')
            """
        )
        positions_mod.update_from_fill(
            conn,
            symbol="AAPL",
            side=Side.BUY,
            qty=100,
            price_usd=Decimal("150"),
            ts_utc="2026-05-26T15:00:00.000Z",
        )

        fills_applied, qty_applied, transitions = apply_fill_plan(
            conn,
            FillPlan(fills=[_planned_fill()]),
            ts_iso="2026-05-26T15:00:01.000Z",
        )

        assert (fills_applied, qty_applied, transitions) == (0, 0, 0)
        assert _fills_total(conn, "ord-1") == 100
        assert _fill_audit_count(conn, "ord-1") == 0
        pos = positions_mod.get_position(conn, "AAPL")
        assert pos is not None and pos.qty == 100
    finally:
        conn.close()


def test_apply_plan_rolls_back_fill_and_audit_on_position_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)
    try:
        _seed_order(conn, qty=100)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("position cache failed")

        monkeypatch.setattr(fill_sync_mod.positions_mod, "update_from_fill", _boom)
        plan = FillPlan(
            fills=[_planned_fill()],
            transitions=[
                PlannedTransition(
                    correlation_id="ord-1",
                    from_state="SUBMITTED",
                    to_state="FILLED",
                    reason="filled 100/100",
                )
            ],
        )

        with pytest.raises(RuntimeError, match="position cache failed"):
            apply_fill_plan(conn, plan, ts_iso="2026-05-26T15:00:00.000Z")

        assert _fills_total(conn, "ord-1") == 0
        assert _fill_audit_count(conn, "ord-1") == 0
        assert positions_mod.get_position(conn, "AAPL") is None
        assert _state(conn, "ord-1") == "SUBMITTED"
        history = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM order_state_history
            WHERE order_correlation_id='ord-1' AND to_state='FILLED'
            """
        ).fetchone()
        assert int(history["c"]) == 0
    finally:
        conn.close()


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
async def test_submission_unknown_unique_full_fill_recovers_and_applies_fill(
    tmp_path: Path,
) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, corr="ord-unknown", kis=None, qty=100, state="SUBMISSION_UNKNOWN")
        with respx.mock(base_url=BASE) as mock:
            route = mock.get(CCNL).mock(
                return_value=_ccnl(
                    [
                        {
                            "odno": "K-REC",
                            "pdno": "AAPL",
                            "sll_buy_dvsn_cd": "02",
                            "ft_ccld_qty": "100",
                            "ft_ccld_unpr3": "150",
                        }
                    ]
                )
            )
            res = await _sync(client, conn)

        assert route.called
        assert res.submission_unknown_recovered == 1
        assert res.fills_applied == 1
        assert _state(conn, "ord-unknown") == "FILLED"
        assert _fills_total(conn, "ord-unknown") == 100
        row = conn.execute(
            "SELECT kis_order_id FROM orders WHERE correlation_id='ord-unknown'"
        ).fetchone()
        assert row["kis_order_id"] == "K-REC"
        events = _recovered_events(conn, "ord-unknown")
        assert len(events) == 1
        assert events[0]["kis_order_id"] == "K-REC"


@pytest.mark.asyncio
async def test_submission_unknown_unique_unfilled_order_recovers_to_submitted(
    tmp_path: Path,
) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, corr="ord-unfilled", kis=None, qty=100, state="SUBMISSION_UNKNOWN")
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(
                return_value=_ccnl(
                    [
                        {
                            "odno": "K-OPEN",
                            "pdno": "AAPL",
                            "sll_buy_dvsn_cd": "02",
                            "ft_ccld_qty": "0",
                            "nccs_qty": "100",
                        }
                    ]
                )
            )
            res = await _sync(client, conn)

        assert res.submission_unknown_recovered == 1
        assert res.fills_applied == 0
        assert _state(conn, "ord-unfilled") == "SUBMITTED"
        row = conn.execute(
            "SELECT kis_order_id FROM orders WHERE correlation_id='ord-unfilled'"
        ).fetchone()
        assert row["kis_order_id"] == "K-OPEN"


@pytest.mark.asyncio
async def test_submission_unknown_ambiguous_matches_stay_unresolved(
    tmp_path: Path,
) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, corr="ord-ambiguous", kis=None, qty=100, state="SUBMISSION_UNKNOWN")
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(
                return_value=_ccnl(
                    [
                        {
                            "odno": "K-A",
                            "pdno": "AAPL",
                            "sll_buy_dvsn_cd": "02",
                            "ft_ccld_qty": "0",
                            "nccs_qty": "100",
                        },
                        {
                            "odno": "K-B",
                            "pdno": "AAPL",
                            "sll_buy_dvsn_cd": "02",
                            "ft_ccld_qty": "100",
                            "ft_ccld_unpr3": "150",
                        },
                    ]
                )
            )
            res = await _sync(client, conn)

        assert res.submission_unknown_recovered == 0
        assert _state(conn, "ord-ambiguous") == "SUBMISSION_UNKNOWN"
        row = conn.execute(
            "SELECT kis_order_id FROM orders WHERE correlation_id='ord-ambiguous'"
        ).fetchone()
        assert row["kis_order_id"] is None
        assert _recovered_events(conn, "ord-ambiguous") == []


@pytest.mark.asyncio
async def test_submission_unknown_lookup_failure_does_not_mutate_order(
    tmp_path: Path,
) -> None:
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, corr="ord-failed", kis=None, qty=100, state="SUBMISSION_UNKNOWN")
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=httpx.Response(503, json={"err": "x"}))
            res = await _sync(client, conn)

        assert res.error is not None
        assert _state(conn, "ord-failed") == "SUBMISSION_UNKNOWN"
        row = conn.execute(
            "SELECT kis_order_id FROM orders WHERE correlation_id='ord-failed'"
        ).fetchone()
        assert row["kis_order_id"] is None
        assert _recovered_events(conn, "ord-failed") == []


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
async def test_multi_exchange_fills_all_synced(tmp_path: Path) -> None:
    """검증된 멀티에셋 유니버스: SPY(AMEX)·IEF(NASD) 주문 체결이 거래소 스윕으로 모두 동기화.

    단일 거래소(기본 NASD)만 조회하던 옛 동작이면 SPY(AMEX) 체결이 누락돼 SUBMITTED 에
    갇히고 로컬 보유가 0 으로 남는다(→ 리밸런서 과매수, 손실 서킷 브레이커가 노출 못 봄).
    스윕이 두 거래소 체결을 모두 가져와 동기화함을 확인한다."""
    async with _broker(tmp_path) as (client, conn):
        _seed_order(conn, corr="ord-spy", kis="K-SPY", symbol="SPY", qty=1)
        _seed_order(conn, corr="ord-ief", kis="K-IEF", symbol="IEF", qty=5)

        def _se(request) -> httpx.Response:
            excd = request.url.params.get("OVRS_EXCG_CD", "")
            rows = {
                "AMEX": [{"odno": "K-SPY", "pdno": "SPY",
                          "ft_ccld_qty": "1", "ft_ccld_unpr3": "540"}],
                "NASD": [{"odno": "K-IEF", "pdno": "IEF",
                          "ft_ccld_qty": "5", "ft_ccld_unpr3": "95"}],
            }.get(excd, [])
            return httpx.Response(200, json={"output": rows})

        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(side_effect=_se)
            res = await _sync(client, conn)
        assert res.fills_applied == 2
        assert _state(conn, "ord-spy") == "FILLED"
        assert _state(conn, "ord-ief") == "FILLED"
        spy = positions_mod.get_position(conn, "SPY")
        ief = positions_mod.get_position(conn, "IEF")
        assert spy is not None and spy.qty == 1
        assert ief is not None and ief.qty == 5


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
