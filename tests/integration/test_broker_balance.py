"""KIS 잔고 조회 회귀 테스트 — 외화예수금 0원 표시 버그 방어.

지난 세션 회귀:
  `get_balance`가 KIS 해외주식 잔고조회(TTTS3012R)의 output2에서
  `frcr_dncl_amt_2` 필드를 읽었으나 이 필드는 국내주식 종합잔고 응답에만
  존재. 해외 endpoint는 cash 필드 자체를 반환하지 않아 항상 잔고 0원으로
  표시됨.

회귀 방어 포인트:
  1. cash는 별도 `inquire-psamount`(TTTS3007R) endpoint에서 조회됨.
  2. 보유 종목 평가금액은 inquire-balance output1에서 합산됨.
  3. total_value_usd = cash + 평가금액 합계.
  4. output2가 list[dict]로 와도 에러 없이 처리.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

import httpx
import pytest
import respx

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.broker.overseas import (
    get_balance,
    get_purchasable_cash_usd,
)

BASE = "https://api.example"
ACCOUNT = "1234567801"


@asynccontextmanager
async def _client() -> AsyncIterator[ResilientClient]:
    async with httpx.AsyncClient(base_url=BASE) as inner:
        yield ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )


@pytest.mark.asyncio
async def test_get_purchasable_cash_reads_ord_psbl_frcr_amt():
    """primary 필드 `ord_psbl_frcr_amt`에서 USD 예수금을 읽는다."""
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-psamount").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ord_psbl_frcr_amt": "1234.56"}}
                )
            )
            cash = await get_purchasable_cash_usd(
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
            )
    assert cash == Decimal("1234.56")


@pytest.mark.asyncio
async def test_get_purchasable_cash_falls_back_to_alternate_keys():
    """KIS 응답 키가 모의/실전에 따라 달라도 후보 필드 순차 시도로 추출."""
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-psamount").mock(
                return_value=httpx.Response(
                    200, json={"output": {"frcr_ord_psbl_amt1": "500"}}
                )
            )
            cash = await get_purchasable_cash_usd(
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
            )
    assert cash == Decimal("500")


@pytest.mark.asyncio
async def test_get_balance_combines_cash_plus_holdings_value():
    """회귀 방어: total_value_usd = cash + 보유 종목 평가금액 합."""
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-balance").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "output1": [
                            {
                                "ovrs_pdno": "VOO",
                                "ovrs_cblc_qty": "2",
                                "pchs_avg_pric": "400",
                                "frcr_evlu_amt2": "850.00",
                            },
                            {
                                "ovrs_pdno": "QQQ",
                                "ovrs_cblc_qty": "1",
                                "pchs_avg_pric": "450",
                                "frcr_evlu_amt2": "470.00",
                            },
                        ],
                        "output2": {"tot_evlu_pfls_amt": "20"},
                    },
                )
            )
            mock.get("/uapi/overseas-stock/v1/trading/inquire-psamount").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ord_psbl_frcr_amt": "100.00"}}
                )
            )
            balance = await get_balance(
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
            )
    assert balance.cash_usd == Decimal("100.00")
    assert balance.total_value_usd == Decimal("1420.00")  # 100 + 850 + 470


@pytest.mark.asyncio
async def test_get_balance_handles_missing_eval_field_via_qty_price_fallback():
    """평가금액 필드가 응답에 없으면 수량 * 현재가로 fallback 계산."""
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-balance").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "output1": [
                            {
                                "ovrs_pdno": "AAPL",
                                "ovrs_cblc_qty": "3",
                                "pchs_avg_pric": "150",
                                "now_pric2": "200.00",
                            },
                        ],
                        "output2": {},
                    },
                )
            )
            mock.get("/uapi/overseas-stock/v1/trading/inquire-psamount").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ord_psbl_frcr_amt": "50.00"}}
                )
            )
            balance = await get_balance(
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
            )
    assert balance.cash_usd == Decimal("50.00")
    assert balance.total_value_usd == Decimal("650.00")  # 50 + 3*200


@pytest.mark.asyncio
async def test_get_balance_handles_empty_holdings():
    """보유 종목 없으면 total_value_usd == cash_usd."""
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.get("/uapi/overseas-stock/v1/trading/inquire-balance").mock(
                return_value=httpx.Response(
                    200, json={"output1": [], "output2": {}}
                )
            )
            mock.get("/uapi/overseas-stock/v1/trading/inquire-psamount").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ord_psbl_frcr_amt": "777.77"}}
                )
            )
            balance = await get_balance(
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                account=ACCOUNT,
            )
    assert balance.cash_usd == Decimal("777.77")
    assert balance.total_value_usd == Decimal("777.77")
