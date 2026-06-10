"""거래소 자동 해석 — 되돌림 읽기 경로(체결·보유·잔고) 멀티 거래소 스윕 회귀 테스트.

배경(2026-06-10): 같은 날 시세(PR #229)·주문(PR #231) 거래소 자동 해석을 고쳤다. 이 파일은
그 *되돌림(읽기)* 대칭이다. 검증된 멀티에셋 유니버스는 거래소가 섞인다 — SPY·GLD=AMEX,
IEF=NASD. KIS 체결조회(inquire-ccnl)·잔고조회(inquire-balance)는 ``OVRS_EXCG_CD`` 로 거래소
범위를 받으므로, 단일 거래소(기본 NASD)로만 조회하면 다른 거래소 종목(SPY·GLD)의 체결·보유가
통째로 빠진다. 그러면 그 주문이 SUBMITTED 에 갇히고(체결 동기화 누락) 로컬 보유가 0 으로 남아
리밸런서가 과매수하며, 잔고 정합성은 'ledger_only' 로 오인해 허위 halt 를 낸다.

수정: 되돌림 조회는 ``US_ORDER_EXCHANGES``(NASD·NYSE·AMEX) 를 전부 훑어 합치되 종목/주문번호로
중복 제거한다. 그래서 KIS 가 거래소별로 엄격히 필터하든(각 거래소 자기 것만) 단일값에 전 거래소를
반환하든 *양쪽에서* 정확하다 — 중복 제거가 멱등성·이중계상 방지를 보장한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

import httpx
import pytest
import respx

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.overseas import (
    US_ORDER_EXCHANGES,
    get_balance_resolving_market,
    get_order_executions_resolving_market,
    get_positions_resolving_market,
)

BASE = "https://api.example"
ACCOUNT = "1234567801"
CCNL = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
BALANCE = "/uapi/overseas-stock/v1/trading/inquire-balance"
PSAMOUNT = "/uapi/overseas-stock/v1/trading/inquire-psamount"


@asynccontextmanager
async def _client() -> AsyncIterator[ResilientClient]:
    async with httpx.AsyncClient(base_url=BASE) as inner:
        yield ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )


def _per_exchange(rows_by_market: dict[str, list[dict]], *, key: str):
    """요청의 OVRS_EXCG_CD 에 해당하는 거래소 row 만 돌려주는 respx side_effect.

    실제 KIS(거래소별 엄격 필터)를 모사한다 — 각 거래소는 자기 종목만 반환."""

    def _se(request: httpx.Request) -> httpx.Response:
        excd = request.url.params.get("OVRS_EXCG_CD", "")
        return httpx.Response(200, json={key: rows_by_market.get(excd, [])})

    return _se


def test_us_order_exchanges_constant() -> None:
    """되돌림 스윕 집합 = 주문 거래소 3종(NASD·NYSE·AMEX), 순서 보존·중복 없음."""
    assert US_ORDER_EXCHANGES == ("NASD", "NYSE", "AMEX")


# ----------------------------------------------------------- 체결 조회(inquire-ccnl)


@pytest.mark.asyncio
async def test_executions_swept_across_exchanges() -> None:
    """SPY(AMEX)·IEF(NASD) 체결이 거래소 스윕으로 모두 합쳐진다(단일 거래소면 한쪽 누락)."""
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(
                side_effect=_per_exchange(
                    {
                        "NASD": [
                            {"odno": "K-IEF", "pdno": "IEF",
                             "ft_ccld_qty": "5", "ft_ccld_unpr3": "95"}
                        ],
                        "AMEX": [
                            {"odno": "K-SPY", "pdno": "SPY",
                             "ft_ccld_qty": "1", "ft_ccld_unpr3": "540"}
                        ],
                    },
                    key="output",
                )
            )
            execs = await get_order_executions_resolving_market(
                client,
                access_token="t",
                app_key="k",
                app_secret="s",
                account=ACCOUNT,
                order_date_yyyymmdd="20260610",
            )
    by_order = {e.kis_order_id: e.filled_qty for e in execs}
    assert by_order == {"K-IEF": 5, "K-SPY": 1}


@pytest.mark.asyncio
async def test_executions_deduped_if_kis_returns_all_on_any_market() -> None:
    """방어: KIS 가 단일값에 전 거래소 체결을 반환해도 주문번호 중복 제거로 1회만 계상."""
    same = [{"odno": "K1", "pdno": "SPY", "ft_ccld_qty": "2", "ft_ccld_unpr3": "540"}]
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get(CCNL).mock(return_value=httpx.Response(200, json={"output": same}))
            execs = await get_order_executions_resolving_market(
                client,
                access_token="t",
                app_key="k",
                app_secret="s",
                account=ACCOUNT,
                order_date_yyyymmdd="20260610",
            )
    assert len(execs) == 1
    assert execs[0].kis_order_id == "K1"
    assert execs[0].filled_qty == 2


# ----------------------------------------------------------- 보유 조회(inquire-balance)


@pytest.mark.asyncio
async def test_positions_swept_across_exchanges() -> None:
    """SPY·GLD(AMEX) + IEF(NASD) 보유가 거래소 스윕으로 모두 합쳐진다."""
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get(BALANCE).mock(
                side_effect=_per_exchange(
                    {
                        "AMEX": [
                            {"ovrs_pdno": "SPY", "ovrs_cblc_qty": "1", "pchs_avg_pric": "540"},
                            {"ovrs_pdno": "GLD", "ovrs_cblc_qty": "2", "pchs_avg_pric": "180"},
                        ],
                        "NASD": [
                            {"ovrs_pdno": "IEF", "ovrs_cblc_qty": "5", "pchs_avg_pric": "95"},
                        ],
                    },
                    key="output1",
                )
            )
            positions = await get_positions_resolving_market(
                client, access_token="t", app_key="k", app_secret="s", account=ACCOUNT
            )
    assert {p.symbol: p.qty for p in positions} == {"SPY": 1, "GLD": 2, "IEF": 5}


@pytest.mark.asyncio
async def test_positions_deduped_if_kis_returns_all_on_any_market() -> None:
    """방어: 같은 종목이 여러 거래소 응답에 와도 종목별 1회(보유 이중계상 방지)."""
    same = [{"ovrs_pdno": "SPY", "ovrs_cblc_qty": "1", "pchs_avg_pric": "540"}]
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get(BALANCE).mock(return_value=httpx.Response(200, json={"output1": same}))
            positions = await get_positions_resolving_market(
                client, access_token="t", app_key="k", app_secret="s", account=ACCOUNT
            )
    assert len(positions) == 1
    assert positions[0].symbol == "SPY"
    assert positions[0].qty == 1


# ----------------------------------------------------------- 잔고/NAV(inquire-balance + cash)


@pytest.mark.asyncio
async def test_balance_sums_holdings_across_exchanges_cash_once() -> None:
    """총 평가금액 = 현금(1회 조회) + 전 거래소 보유 평가금액 합."""
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get(BALANCE).mock(
                side_effect=_per_exchange(
                    {
                        "AMEX": [
                            {"ovrs_pdno": "SPY", "ovrs_cblc_qty": "1",
                             "pchs_avg_pric": "540", "frcr_evlu_amt2": "540"},
                            {"ovrs_pdno": "GLD", "ovrs_cblc_qty": "2",
                             "pchs_avg_pric": "180", "frcr_evlu_amt2": "360"},
                        ],
                        "NASD": [
                            {"ovrs_pdno": "IEF", "ovrs_cblc_qty": "5",
                             "pchs_avg_pric": "95", "frcr_evlu_amt2": "475"},
                        ],
                    },
                    key="output1",
                )
            )
            mock.get(PSAMOUNT).mock(
                return_value=httpx.Response(200, json={"output": {"ord_psbl_frcr_amt": "100"}})
            )
            balance = await get_balance_resolving_market(
                client, access_token="t", app_key="k", app_secret="s", account=ACCOUNT
            )
    assert balance.cash_usd == Decimal("100")
    assert balance.total_value_usd == Decimal("1475")  # 100 + 540 + 360 + 475


@pytest.mark.asyncio
async def test_balance_deduped_if_kis_returns_all_on_any_market() -> None:
    """방어: KIS 가 단일값에 전 거래소 보유를 반환해도 종목별 중복 제거로 평가금액 이중계상 0."""
    same = [
        {"ovrs_pdno": "SPY", "ovrs_cblc_qty": "1",
         "pchs_avg_pric": "540", "frcr_evlu_amt2": "540"}
    ]
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get(BALANCE).mock(return_value=httpx.Response(200, json={"output1": same}))
            mock.get(PSAMOUNT).mock(
                return_value=httpx.Response(200, json={"output": {"ord_psbl_frcr_amt": "0"}})
            )
            balance = await get_balance_resolving_market(
                client, access_token="t", app_key="k", app_secret="s", account=ACCOUNT
            )
    # 3개 거래소를 훑어도 SPY 평가금액 540 은 한 번만 계상(1620 이 아니다).
    assert balance.total_value_usd == Decimal("540")
