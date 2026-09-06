"""Official cumulative execution and continuation contracts; no network."""

from decimal import Decimal

import httpx
import pytest

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.overseas import get_order_executions


def row(**updates):
    return {
        "odno": "1",
        "pdno": "SPY",
        "sll_buy_dvsn_cd": "02",
        "ft_ccld_qty": "2",
        "ft_ccld_unpr3": "99",
        "nccs_qty": "3",
        "ord_dt": "20260908",
        "ord_tmd": "103000",
        "ovrs_excg_cd": "AMEX",
        **updates,
    }


async def query(handler, *, strict_contract=True):
    async with httpx.AsyncClient(
        base_url="https://kis.invalid", transport=httpx.MockTransport(handler)
    ) as http:
        client = ResilientClient(
            http,
            max_retries=0,
            rate_limiter=AsyncTokenBucket(100, 100),
            breaker=CircuitBreaker(3, 10),
        )
        return await get_order_executions(
            client,
            access_token="test",
            app_key="test",
            app_secret="test",
            account="1234567801",
            order_date_yyyymmdd="20260908",
            strict_contract=strict_contract,
        )


@pytest.mark.asyncio
async def test_continuation_preserves_cursor_and_deduplicates_cumulative_snapshot():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["SORT_SQN"] == "DS"
        assert "SORT_SQN_DVSN" not in request.url.params
        assert request.url.params["ORD_GNO_BRNO"] == ""
        if len(calls) == 1:
            return httpx.Response(
                200,
                headers={"tr_cont": "M"},
                json={
                    "rt_cd": "0",
                    "output": [row()],
                    "ctx_area_fk200": " f ",
                    "ctx_area_nk200": " n ",
                },
            )
        assert request.headers["tr_cont"] == "N"
        assert request.url.params["CTX_AREA_FK200"] == " f "
        assert request.url.params["CTX_AREA_NK200"] == " n "
        return httpx.Response(
            200,
            headers={"tr_cont": "D"},
            json={
                "rt_cd": "0",
                "output": [row(), row(ft_ccld_qty="3", ft_ccld_unpr3="99.30", nccs_qty="2")],
            },
        )

    result = await query(handler)
    assert len(calls) == 2 and len(result) == 1
    assert result[0].filled_qty == 3
    assert result[0].avg_fill_price_usd == Decimal("99.30")
    assert result[0].market == "AMEX"
    assert result[0].ordered_at_utc is None


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"output": []}, {"rt_cd": "1", "output": []}, {"rt_cd": "0"}])
async def test_unconfirmed_response_never_looks_like_empty_account(body):
    with pytest.raises(ValueError):
        await query(lambda request: httpx.Response(200, json=body))


@pytest.mark.asyncio
async def test_repeated_cursor_rejects_partial_history():
    with pytest.raises(ValueError, match="STALLED"):
        await query(
            lambda request: httpx.Response(
                200,
                headers={"tr_cont": "F"},
                json={
                    "rt_cd": "0",
                    "output": [row()],
                    "ctx_area_fk200": "f",
                    "ctx_area_nk200": "n",
                },
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("strict_contract", [True, False])
@pytest.mark.parametrize(
    "status,qty,terminal",
    [("완료", "3", True), ("거부", "3", False), ("전송", "3", False), ("완료", "1", False)],
)
async def test_cancel_rows_require_confirmed_full_remainder(status, qty, terminal, strict_contract):
    cancel = row(
        odno="C1",
        orgn_odno="1",
        rvse_cncl_dvsn="02",
        prcs_stat_name=status,
        ft_ord_qty=qty,
        ft_ccld_qty="0",
    )
    result = await query(
        lambda request: httpx.Response(200, json={"rt_cd": "0", "output": [row(), cancel]}),
        strict_contract=strict_contract,
    )
    assert len(result) == 1
    assert result[0].filled_qty == 2 and result[0].terminal is terminal
