from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.models import OrderRequest
from auto_invest.broker.overseas import KisOrderError, place_order
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, PriceTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderRouter
from auto_invest.persistence import db

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


def _order(side: Side = Side.BUY) -> OrderRequest:
    return OrderRequest(
        account=ACCOUNT,
        symbol="IEF",
        side=side,
        order_type=OrderType.LIMIT,
        qty=1,
        limit_price_usd=Decimal("94.55"),
    )


@pytest.mark.asyncio
async def test_place_order_normal_buy_payload_matches_kis_sample_fields():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"output": {"ODNO": "KIS123"}})

    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(side_effect=handler)
            result = await place_order(
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                request=_order(Side.BUY),
                market="NASD",
            )

    assert result.kis_order_id == "KIS123"
    assert captured["headers"]["tr_id"] == "TTTT1002U"  # type: ignore[index]
    body = captured["body"]
    assert body == {
        "CANO": "12345678",
        "ACNT_PRDT_CD": "01",
        "OVRS_EXCG_CD": "NASD",
        "PDNO": "IEF",
        "ORD_QTY": "1",
        "OVRS_ORD_UNPR": "94.55",
        "CTAC_TLNO": "",
        "MGCO_APTM_ODNO": "",
        "SLL_TYPE": "",
        "ORD_SVR_DVSN_CD": "0",
        "ORD_DVSN": "00",
    }


@pytest.mark.asyncio
async def test_place_order_normal_sell_payload_sets_sell_type():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"output": {"ODNO": "KIS124"}})

    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(side_effect=handler)
            await place_order(
                client,
                access_token="tok",
                app_key="app",
                app_secret="sec",
                request=_order(Side.SELL),
                market="NASD",
            )

    assert captured["headers"]["tr_id"] == "TTTT1006U"  # type: ignore[index]
    body = captured["body"]
    assert body["SLL_TYPE"] == "00"  # type: ignore[index]
    assert body["ORD_SVR_DVSN_CD"] == "0"  # type: ignore[index]


@pytest.mark.asyncio
async def test_place_order_http_error_preserves_masked_kis_diagnostics():
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(
                    500,
                    json={
                        "rt_cd": "1",
                        "msg_cd": "APBK0000",
                        "msg1": "주문 가능 시간이 아닙니다",
                        "CANO": "12345678",
                    },
                )
            )
            with pytest.raises(KisOrderError) as raised:
                await place_order(
                    client,
                    access_token="tok",
                    app_key="app",
                    app_secret="sec",
                    request=_order(Side.BUY),
                    market="NASD",
                )

    diagnostics = raised.value.diagnostics
    assert diagnostics["http_status"] == 500
    assert diagnostics["kis_msg_cd"] == "APBK0000"
    assert diagnostics["kis_msg1"] == "주문 가능 시간이 아닙니다"
    assert diagnostics["endpoint"] == "/uapi/overseas-stock/v1/trading/order"
    body = diagnostics["request_summary"]["body"]
    assert body["CANO"] != "12345678"
    assert body["ACNT_PRDT_CD"] == "**"
    assert "12345678" not in json.dumps(diagnostics, ensure_ascii=False)
    assert "12345678" not in diagnostics["response_body_preview"]
    assert "tok" not in json.dumps(diagnostics, ensure_ascii=False)
    assert body["ORD_SVR_DVSN_CD"] == "0"


@pytest.mark.asyncio
async def test_place_order_non_json_error_preserves_body_preview():
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(500, text="internal server error")
            )
            with pytest.raises(KisOrderError) as raised:
                await place_order(
                    client,
                    access_token="tok",
                    app_key="app",
                    app_secret="sec",
                    request=_order(Side.BUY),
                    market="NASD",
                )

    diagnostics = raised.value.diagnostics
    assert diagnostics["http_status"] == 500
    assert diagnostics["response_body_preview"] == "internal server error"
    assert diagnostics["response_json"] is None


@pytest.mark.asyncio
async def test_place_order_http_200_error_body_preserves_kis_diagnostics():
    async with _client() as client:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "rt_cd": "1",
                        "msg_cd": "APBK1234",
                        "msg1": "주문 가능 금액 부족",
                        "CANO": "12345678",
                    },
                )
            )
            with pytest.raises(KisOrderError) as raised:
                await place_order(
                    client,
                    access_token="tok",
                    app_key="app",
                    app_secret="sec",
                    request=_order(Side.BUY),
                    market="NASD",
                )

    assert str(raised.value) == "KIS order response missing output"
    diagnostics = raised.value.diagnostics
    assert diagnostics["http_status"] == 200
    assert diagnostics["kis_rt_cd"] == "1"
    assert diagnostics["kis_msg_cd"] == "APBK1234"
    assert diagnostics["kis_msg1"] == "주문 가능 금액 부족"
    assert diagnostics["endpoint"] == "/uapi/overseas-stock/v1/trading/order"
    body = diagnostics["request_summary"]["body"]
    assert body["CANO"] != "12345678"
    assert body["ACNT_PRDT_CD"] == "**"
    assert "12345678" not in json.dumps(diagnostics, ensure_ascii=False)
    assert "tok" not in json.dumps(diagnostics, ensure_ascii=False)


@pytest.mark.asyncio
async def test_order_router_persists_broker_diagnostics_in_audit_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    diagnostics = {
        "http_status": 500,
        "kis_msg_cd": "APBK0000",
        "kis_msg1": "주문 가능 시간이 아닙니다",
        "request_summary": {"body": {"CANO": "******78"}},
    }

    class BrokerBoom(RuntimeError):
        def __init__(self) -> None:
            super().__init__("KIS order request failed")
            self.diagnostics = diagnostics

    async def fake_place_order(*args, **kwargs):
        raise BrokerBoom()

    monkeypatch.setattr("auto_invest.execution.order_router.place_order", fake_place_order)

    conn = db.get_connection(tmp_path / "orders.db")
    db.migrate(conn)
    async with httpx.AsyncClient(base_url=BASE) as inner:
        broker = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        router = OrderRouter(
            conn=conn,
            broker=broker,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no=ACCOUNT,
            whitelist=Whitelist(
                symbols={"IEF"},
                accounts={ACCOUNT},
                order_types=frozenset({OrderType.LIMIT}),
            ),
            caps=SizingCaps(
                per_trade_pct=Decimal("5"),
                per_symbol_pct=Decimal("20"),
                global_exposure_pct=Decimal("80"),
                canary_capital_pct=Decimal("5"),
                canary_min_duration_days=10,
                canary_acceptance_drawdown_pct=Decimal("3"),
            ),
            halt_path=tmp_path / "halt.flag",
            market="NASD",
            paper_mode=False,
        )

        outcome = await router.submit_order(
            rule=TradingRule(
                id="diag-test",
                symbol="IEF",
                stage=StrategyStage.CANARY,
                priority=1,
                trigger=PriceTrigger(
                    direction="<=",
                    threshold=Decimal("100"),
                    cooldown_seconds=60,
                ),
                action=Action(
                    side=Side.BUY,
                    order_type=OrderType.LIMIT,
                    qty=1,
                    limit_price="94.55",
                ),
            ),
            quote_price_usd=Decimal("94.55"),
            quote_ask_usd=Decimal("94.55"),
            quote_bid_usd=Decimal("94.50"),
            total_capital_usd=Decimal("10000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )

    assert outcome.state == "REJECTED_BY_BROKER"
    assert outcome.reason is not None
    assert json.loads(outcome.reason)["kis_msg_cd"] == "APBK0000"

    row = conn.execute(
        "SELECT payload_json FROM audit_log WHERE event_type = 'ORDER_REJECTED_BY_BROKER'"
    ).fetchone()
    payload = json.loads(row["payload_json"])
    assert payload["broker_code"] == "BrokerBoom"
    assert payload["diagnostics"]["kis_msg1"] == "주문 가능 시간이 아닙니다"
    assert payload["diagnostics"]["request_summary"]["body"]["CANO"] == "******78"
    conn.close()
