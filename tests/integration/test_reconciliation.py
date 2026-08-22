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
) -> dict:
    """KIS 해외주식 잔고조회(TTTS3012R) 응답 stub.

    output2는 P&L 위주 필드만 포함 — KIS는 이 endpoint에서 외화예수금(cash)
    필드를 반환하지 않으므로 cash는 별도 inquire-psamount endpoint에서
    조회한다. `_psamount_payload`를 참고.
    """
    return {
        "output1": positions,
        "output2": {
            "tot_evlu_pfls_amt": "0",
            "tot_pftrt": "0",
        },
    }


def _psamount_payload(cash_usd: str = "1000") -> dict:
    """KIS 해외주식 주문가능금액조회(TTTS3007R) 응답 stub.

    외화예수금(주문가능 외화금액)은 응답의 `output.ord_psbl_frcr_amt`에서
    추출된다 (broker/overseas.get_purchasable_cash_usd).
    """
    return {"output": {"ord_psbl_frcr_amt": cash_usd}}


def _mock_kis_endpoints(
    mock,
    *,
    positions: list[dict],
    cash_usd: str = "1000",
) -> None:
    """inquire-balance + inquire-psamount를 둘 다 mock."""
    mock.get("/uapi/overseas-stock/v1/trading/inquire-balance").mock(
        return_value=httpx.Response(200, json=_balance_payload(positions=positions))
    )
    mock.get("/uapi/overseas-stock/v1/trading/inquire-psamount").mock(
        return_value=httpx.Response(200, json=_psamount_payload(cash_usd=cash_usd))
    )


# ----------------------------------------------------- match path


@pytest.mark.asyncio
async def test_reconciliation_ok_when_positions_match(tmp_path: Path):
    async with _broker(tmp_path) as (client, conn, halt_path):
        _seed_local_position(conn, symbol="AAPL", qty=10)

        with respx.mock(base_url=BASE) as mock:
            _mock_kis_endpoints(
                mock,
                positions=[
                    {
                        "ovrs_pdno": "AAPL",
                        "ovrs_cblc_qty": "10",
                        "pchs_avg_pric": "100",
                    }
                ],
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
        run_row = conn.execute("SELECT result FROM reconciliation_runs").fetchone()
        assert run_row["result"] == "OK"


# ----------------------------------------------------- mismatch path


@pytest.mark.asyncio
async def test_reconciliation_mismatch_qty_halts_worker(tmp_path: Path):
    async with _broker(tmp_path) as (client, conn, halt_path):
        # Local says 10 AAPL, broker says 7 AAPL.
        _seed_local_position(conn, symbol="AAPL", qty=10)

        with respx.mock(base_url=BASE) as mock:
            _mock_kis_endpoints(
                mock,
                positions=[
                    {
                        "ovrs_pdno": "AAPL",
                        "ovrs_cblc_qty": "7",
                        "pchs_avg_pric": "100",
                    }
                ],
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
            {"symbol": "AAPL", "local_qty": 10, "external_qty": 0, "broker_qty": 7}
        ]
        assert is_halted(halt_path) is True
        events = [r["event_type"] for r in audit.read_all(conn)]
        assert "RECONCILIATION_MISMATCH" in events
        assert "HALT_SET" not in events  # halt is filesystem-only at this layer


@pytest.mark.asyncio
async def test_reconciliation_mismatch_does_not_overwrite_manual_halt(tmp_path: Path):
    from auto_invest.worker.halt import read_halt, set_halt

    async with _broker(tmp_path) as (client, conn, halt_path):
        manual = set_halt(halt_path, "operator maintenance")
        _seed_local_position(conn, symbol="AAPL", qty=10)
        with respx.mock(base_url=BASE) as mock:
            _mock_kis_endpoints(mock, positions=[])
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
        assert read_halt(halt_path) == manual


@pytest.mark.asyncio
async def test_reconciliation_mismatch_when_local_has_unknown_symbol(tmp_path: Path):
    async with _broker(tmp_path) as (client, conn, halt_path):
        _seed_local_position(conn, symbol="AAPL", qty=5)
        # Broker reports zero positions.
        with respx.mock(base_url=BASE) as mock:
            _mock_kis_endpoints(mock, positions=[])
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


# ------------------------------------------- external holdings baseline
# 시스템 비관리 외부 보유(운영자가 시스템 밖에서 취득 — 원장에 영원히 없음)를
# deploy/external-holdings.toml 기준선으로 선언하면 (원장+기준선)==브로커 로
# 대조한다. 실측 사례: BHP·MRK·ORANY·RELX 4종목이 매 장 마감 허위 halt 를
# 반복(2026-06-04 / 06-11). 기준선과 다르면 여전히 MISMATCH (안전망 유지).


@pytest.mark.asyncio
async def test_external_baseline_covers_operator_holdings(tmp_path: Path):
    """원장에 없는 브로커 보유가 기준선과 정확히 일치하면 OK — halt 안 섬."""
    async with _broker(tmp_path) as (client, conn, halt_path):
        # 원장은 비어 있고(시스템 체결 0건), 계좌엔 운영자 보유 2종목.
        with respx.mock(base_url=BASE) as mock:
            _mock_kis_endpoints(
                mock,
                positions=[
                    {"ovrs_pdno": "BHP", "ovrs_cblc_qty": "1", "pchs_avg_pric": "47.97"},
                    {"ovrs_pdno": "MRK", "ovrs_cblc_qty": "3", "pchs_avg_pric": "79.09"},
                ],
            )
            outcome = await run_reconciliation(
                conn,
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
                halt_path=halt_path,
                external_holdings={"BHP": 1, "MRK": 3},
            )
        assert outcome.state == "OK"
        assert is_halted(halt_path) is False
        events = [r["event_type"] for r in audit.read_all(conn)]
        assert "RECONCILIATION_OK" in events


@pytest.mark.asyncio
async def test_external_baseline_combines_with_ledger(tmp_path: Path):
    """시스템 체결분 + 외부 기준선이 합산되어 브로커 총량과 대조된다."""
    async with _broker(tmp_path) as (client, conn, halt_path):
        _seed_local_position(conn, symbol="SPY", qty=3)
        with respx.mock(base_url=BASE) as mock:
            _mock_kis_endpoints(
                mock,
                positions=[
                    {"ovrs_pdno": "SPY", "ovrs_cblc_qty": "3", "pchs_avg_pric": "500"},
                    {"ovrs_pdno": "BHP", "ovrs_cblc_qty": "1", "pchs_avg_pric": "47.97"},
                ],
            )
            outcome = await run_reconciliation(
                conn,
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
                halt_path=halt_path,
                external_holdings={"BHP": 1},
            )
        assert outcome.state == "OK"
        assert is_halted(halt_path) is False


@pytest.mark.asyncio
async def test_external_baseline_drift_still_halts(tmp_path: Path):
    """기준선 수량과 다르면(운영자 매도 등) 여전히 MISMATCH → halt.

    기준선은 허위 halt 만 없애고 안전망은 약화하지 않는다 — 시스템 모델 밖의
    계좌 활동은 멈추고 드러낸다(fail-safe).
    """
    async with _broker(tmp_path) as (client, conn, halt_path):
        with respx.mock(base_url=BASE) as mock:
            # 기준선은 ORANY 28주를 기대하는데 계좌엔 20주뿐 (+RELX 전량 매도).
            _mock_kis_endpoints(
                mock,
                positions=[
                    {"ovrs_pdno": "ORANY", "ovrs_cblc_qty": "20", "pchs_avg_pric": "11.2"},
                ],
            )
            outcome = await run_reconciliation(
                conn,
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
                halt_path=halt_path,
                external_holdings={"ORANY": 28, "RELX": 6},
            )
        assert outcome.state == "MISMATCH"
        assert outcome.diff["position_diffs"] == [
            {"symbol": "ORANY", "local_qty": 0, "external_qty": 28, "broker_qty": 20},
            {"symbol": "RELX", "local_qty": 0, "external_qty": 6, "broker_qty": 0},
        ]
        assert is_halted(halt_path) is True


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
        run_row = conn.execute("SELECT result FROM reconciliation_runs").fetchone()
        assert run_row["result"] == "INCONCLUSIVE"
