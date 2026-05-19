"""Spec 009 T007 + T008 — OrderRouter 단일 차단 지점 회귀 가드.

paper_mode=True인 OrderRouter는 broker 주문 호출을 절대 하지 않는다 (FR-004).
이 테스트는 그 invariant를 다음 방식으로 보장:

  - ResilientClient.post를 raise하도록 monkeypatch.
  - paper-mode OrderRouter로 submit_order를 N회 호출.
  - 예외 발생 0건 + audit_log에 ORDER_PAPER_FILLED row N건 + KIS 주문
    API 호출 0건.

또한 paper-mode에서도 게이트(whitelist·cap·halt)는 live와 동일하게 동작함을
검증 (FR-005, SC-004).

대응 변경:
  - `src/auto_invest/execution/order_router.py`의 `OrderRouter`에
    `paper_mode: bool = False`, `quote_ask_usd: Decimal | None`,
    `quote_bid_usd: Decimal | None`을 추가.
  - broker 호출 직전 분기에서 `OrderPaperFilledPayload` 기록.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from auto_invest.broker.client import (
    AsyncTokenBucket,
    CircuitBreaker,
    ResilientClient,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, PriceTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderRouter
from auto_invest.persistence import db
from auto_invest.worker.halt import set_halt

BASE = "https://api.example"
ACCOUNT = "1234567801"


def _rule(
    *,
    rule_id: str = "paper-test-rule",
    symbol: str = "AAPL",
    qty: int = 5,
    side: Side = Side.BUY,
    stage: StrategyStage = StrategyStage.CANARY,
) -> TradingRule:
    return TradingRule(
        id=rule_id,
        symbol=symbol,
        stage=stage,
        priority=10,
        enabled=True,
        trigger=PriceTrigger(
            direction="<=",
            threshold=Decimal("100"),
            cooldown_seconds=60,
        ),
        action=Action(
            side=side,
            order_type=OrderType.MARKET,
            qty=qty,
            limit_price="0",  # unused for MARKET orders
        ),
    )


def _whitelist() -> Whitelist:
    return Whitelist(
        symbols={"AAPL", "MSFT"},
        accounts={ACCOUNT},
        order_types=frozenset({OrderType.MARKET, OrderType.LIMIT}),
    )


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )


@asynccontextmanager
async def _paper_router(
    tmp_path: Path,
    *,
    halt_set: bool = False,
) -> AsyncIterator[OrderRouter]:
    halt_path = tmp_path / "halt.flag"
    if halt_set:
        set_halt(halt_path, "test halt")

    conn = db.get_connection(tmp_path / "t.db")
    db.migrate(conn)

    async with httpx.AsyncClient(base_url=BASE) as inner:
        client = ResilientClient(
            inner,
            rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
            breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
            max_retries=1,
        )
        yield OrderRouter(
            conn=conn,
            broker=client,
            access_token="tok",
            app_key="app",
            app_secret="sec",
            account_no=ACCOUNT,
            whitelist=_whitelist(),
            caps=_caps(),
            halt_path=halt_path,
            market="NASD",
            paper_mode=True,
            paper_session_id=42,
        )
    conn.close()


# ----------------------------------------------------------- core invariant


@pytest.mark.asyncio
async def test_paper_mode_never_calls_broker(tmp_path, monkeypatch):
    """SC-001 핵심 — paper_mode=True에서 broker.post는 단 한 번도 호출되지 않는다."""

    call_count = {"n": 0}

    async def fake_request(*args, **kwargs):
        call_count["n"] += 1
        raise RuntimeError("paper-mode가 broker.request를 호출했다 — FR-004 위반")

    monkeypatch.setattr(ResilientClient, "request", fake_request)

    async with _paper_router(tmp_path) as router:
        for i in range(20):
            outcome = await router.submit_order(
                rule=_rule(rule_id=f"r{i}"),
                quote_price_usd=Decimal("100.00"),
                quote_ask_usd=Decimal("100.05"),
                quote_bid_usd=Decimal("99.95"),
                total_capital_usd=Decimal("100000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )
            assert outcome.state == "PAPER_FILLED", (
                f"iter {i}: paper_mode에서 SUBMITTED 또는 다른 상태가 나옴"
            )

        # 20회 호출 동안 broker.post 0건
        assert call_count["n"] == 0


@pytest.mark.asyncio
async def test_paper_fill_records_audit_event(tmp_path, monkeypatch):
    """paper-mode에서 게이트 통과 시 ORDER_PAPER_FILLED audit row 1건."""

    monkeypatch.setattr(ResilientClient, "request", _raise_request)

    async with _paper_router(tmp_path) as router:
        outcome = await router.submit_order(
            rule=_rule(),
            quote_price_usd=Decimal("100.00"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )
        assert outcome.state == "PAPER_FILLED"

        rows = list(
            router.conn.execute(
                "SELECT event_type, rule_id, symbol, correlation_id, payload_json "
                "FROM audit_log WHERE event_type = 'ORDER_PAPER_FILLED'"
            )
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["rule_id"] == "paper-test-rule"
        assert row["symbol"] == "AAPL"
        # correlation_id가 audit_log 컬럼에도 들어간다
        assert row["correlation_id"] is not None
        import json
        payload = json.loads(row["payload_json"])
        assert payload["quote_source"] == "ask"  # BUY → ask
        assert payload["simulated_fill_price_usd"] == "100.05"
        assert payload["paper_session_id"] == 42


@pytest.mark.asyncio
async def test_paper_sell_uses_bid_price(tmp_path, monkeypatch):
    """SELL 주문의 시뮬 가격은 bid (FR-007)."""

    monkeypatch.setattr(ResilientClient, "request", _raise_request)

    async with _paper_router(tmp_path) as router:
        await router.submit_order(
            rule=_rule(side=Side.SELL),
            quote_price_usd=Decimal("100.00"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("500"),
            current_global_exposure_usd=Decimal("500"),
        )
        rows = list(router.conn.execute(
            "SELECT payload_json FROM audit_log "
            "WHERE event_type = 'ORDER_PAPER_FILLED'"
        ))
        import json
        payload = json.loads(rows[0]["payload_json"])
        assert payload["quote_source"] == "bid"
        assert payload["simulated_fill_price_usd"] == "99.95"


@pytest.mark.asyncio
async def test_paper_fallback_to_last_when_ask_missing(tmp_path, monkeypatch):
    """ask 없으면 last(quote_price_usd) 폴백."""

    monkeypatch.setattr(ResilientClient, "request", _raise_request)

    async with _paper_router(tmp_path) as router:
        await router.submit_order(
            rule=_rule(),
            quote_price_usd=Decimal("100.00"),
            quote_ask_usd=None,
            quote_bid_usd=None,
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )
        rows = list(router.conn.execute(
            "SELECT payload_json FROM audit_log "
            "WHERE event_type = 'ORDER_PAPER_FILLED'"
        ))
        import json
        payload = json.loads(rows[0]["payload_json"])
        assert payload["quote_source"] == "last"
        assert payload["simulated_fill_price_usd"] == "100.00"


# ----------------------------------------------------------- gates still block


@pytest.mark.asyncio
async def test_paper_whitelist_gate_still_blocks(tmp_path, monkeypatch):
    """T008 — whitelist 위반 시그널은 paper에서도 차단된다 (FR-005)."""

    monkeypatch.setattr(ResilientClient, "request", _raise_request)

    async with _paper_router(tmp_path) as router:
        outcome = await router.submit_order(
            rule=_rule(symbol="UNKNOWN"),
            quote_price_usd=Decimal("100.00"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )
        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "whitelist_gate"

        # ORDER_PAPER_FILLED는 기록되지 않음
        rows = list(router.conn.execute(
            "SELECT COUNT(*) as n FROM audit_log "
            "WHERE event_type = 'ORDER_PAPER_FILLED'"
        ))
        assert rows[0]["n"] == 0


@pytest.mark.asyncio
async def test_paper_halt_gate_still_blocks(tmp_path, monkeypatch):
    """halt flag가 켜져 있으면 paper에서도 차단."""

    monkeypatch.setattr(ResilientClient, "request", _raise_request)

    async with _paper_router(tmp_path, halt_set=True) as router:
        outcome = await router.submit_order(
            rule=_rule(),
            quote_price_usd=Decimal("100.00"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )
        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "halt_gate"


@pytest.mark.asyncio
async def test_paper_per_trade_cap_gate_still_blocks(tmp_path, monkeypatch):
    """per_trade_cap (5% of 100000 = 5000 USD 한도)을 초과하는 주문 차단."""

    monkeypatch.setattr(ResilientClient, "request", _raise_request)

    async with _paper_router(tmp_path) as router:
        outcome = await router.submit_order(
            # qty=100 × $100 = $10000 → 5% cap($5000) 초과
            rule=_rule(qty=100),
            quote_price_usd=Decimal("100.00"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )
        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "per_trade_cap_gate"


# ----------------------------------------------------------- live row protection


@pytest.mark.asyncio
async def test_paper_does_not_touch_orders_table(tmp_path, monkeypatch):
    """SC-006 — paper-mode에서 orders 테이블에 row가 INSERT되지 않는다."""

    monkeypatch.setattr(ResilientClient, "request", _raise_request)

    async with _paper_router(tmp_path) as router:
        await router.submit_order(
            rule=_rule(),
            quote_price_usd=Decimal("100.00"),
            quote_ask_usd=Decimal("100.05"),
            quote_bid_usd=Decimal("99.95"),
            total_capital_usd=Decimal("100000"),
            current_symbol_exposure_usd=Decimal("0"),
            current_global_exposure_usd=Decimal("0"),
        )

        # orders 테이블 비어 있음
        rows = list(router.conn.execute("SELECT COUNT(*) as n FROM orders"))
        assert rows[0]["n"] == 0

        # order_state_history 테이블도 비어 있음
        rows = list(router.conn.execute(
            "SELECT COUNT(*) as n FROM order_state_history"
        ))
        assert rows[0]["n"] == 0


# ----------------------------------------------------------- helpers


async def _raise_request(*args, **kwargs):
    raise RuntimeError("paper-mode가 broker.request를 호출했다 — FR-004 위반")
