"""Integration tests for the order router (T043)."""

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
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import (
    Action,
    PriceTrigger,
    TradingRule,
)
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import (
    LimitPriceExprError,
    OrderRouter,
    evaluate_limit_price,
    verify_stage_uniqueness,
)
from auto_invest.persistence import audit, db
from auto_invest.worker.halt import set_halt

BASE = "https://api.example"
ACCOUNT = "1234567801"


def _rule(
    *,
    rule_id: str = "spy-rule",
    symbol: str = "AAPL",
    qty: int = 5,
    limit_price: str = "100.00",
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
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            qty=qty,
            limit_price=limit_price,
        ),
    )


def _whitelist() -> Whitelist:
    return Whitelist(symbols={"AAPL"}, accounts={ACCOUNT})


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
async def _router(
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
        )

    conn.close()


# ------------------------------------------------------ limit_price expression


def test_evaluate_limit_price_literal():
    assert evaluate_limit_price(
        "100.50", trigger_price=Decimal("99"), last_close=None
    ) == Decimal("100.50")


def test_evaluate_limit_price_trigger_minus():
    result = evaluate_limit_price(
        "trigger - 0.10", trigger_price=Decimal("100"), last_close=None
    )
    assert result == Decimal("99.90")


def test_evaluate_limit_price_trigger_plus():
    result = evaluate_limit_price(
        "trigger + 0.25", trigger_price=Decimal("100"), last_close=None
    )
    assert result == Decimal("100.25")


def test_evaluate_limit_price_last_close_factor():
    result = evaluate_limit_price(
        "last_close * 1.001",
        trigger_price=Decimal("0"),
        last_close=Decimal("100"),
    )
    assert result == Decimal("100.100")


def test_evaluate_limit_price_last_close_required():
    with pytest.raises(LimitPriceExprError, match="last_close"):
        evaluate_limit_price(
            "last_close * 1.001",
            trigger_price=Decimal("100"),
            last_close=None,
        )


def test_evaluate_limit_price_unknown_form():
    with pytest.raises(LimitPriceExprError, match="unsupported"):
        evaluate_limit_price(
            "trigger ** 2", trigger_price=Decimal("10"), last_close=None
        )


# ------------------------------------------------------ stage uniqueness


def test_verify_stage_uniqueness_passes_for_distinct_symbols():
    rules = [
        _rule(rule_id="r1", symbol="AAPL", stage=StrategyStage.CANARY),
        _rule(rule_id="r2", symbol="AAPL", stage=StrategyStage.CANARY),
    ]
    decisions = verify_stage_uniqueness(rules)
    assert all(d.allow for d in decisions)


def test_verify_stage_uniqueness_denies_lower_when_higher_active():
    rules = [
        _rule(rule_id="canary", symbol="AAPL", stage=StrategyStage.CANARY),
        _rule(rule_id="live", symbol="AAPL", stage=StrategyStage.FULL_LIVE),
    ]
    decisions = verify_stage_uniqueness(rules)
    # canary rule should be denied because FULL_LIVE is also active.
    assert decisions[0].allow is False
    assert decisions[1].allow is True


# ------------------------------------------------------ submit_order paths


@pytest.mark.asyncio
async def test_submit_order_happy_path(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ODNO": "K-001"}}
                )
            )

            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )
        assert outcome.state == "SUBMITTED"
        assert outcome.kis_order_id == "K-001"

        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert events == ["ORDER_INTENT", "ORDER_SUBMITTED"]

        order_row = router.conn.execute(
            "SELECT state, kis_order_id FROM orders"
        ).fetchone()
        assert order_row["state"] == "SUBMITTED"
        assert order_row["kis_order_id"] == "K-001"


@pytest.mark.asyncio
async def test_submit_order_rejected_by_per_trade_cap(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )

            # qty 100 * price 100 = 10000 > per_trade cap 500 (5% of 10000)
            big_rule = _rule(qty=100)
            outcome = await router.submit_order(
                rule=big_rule,
                quote_price_usd=Decimal("100"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "per_trade_cap_gate"
        assert placed.call_count == 0  # broker never reached

        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert events == ["ORDER_INTENT", "ORDER_REJECTED_BY_GATE"]

        order_row = router.conn.execute(
            "SELECT state FROM orders"
        ).fetchone()
        assert order_row["state"] == "REJECTED_BY_GATE"


@pytest.mark.asyncio
async def test_submit_order_blocked_by_halt(tmp_path: Path):
    async with _router(tmp_path, halt_set=True) as router:
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )

            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "halt_gate"
        assert placed.call_count == 0


@pytest.mark.asyncio
async def test_submit_order_rejected_by_broker_5xx(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(500, json={"err": "x"})
            )

            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "REJECTED_BY_BROKER"
        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert "ORDER_REJECTED_BY_BROKER" in events

        order_row = router.conn.execute(
            "SELECT state FROM orders"
        ).fetchone()
        assert order_row["state"] == "REJECTED_BY_BROKER"


@pytest.mark.asyncio
async def test_submit_order_records_correlation_id_across_events(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(
                    200, json={"output": {"ODNO": "K-001"}}
                )
            )

            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        rows = audit.read_by_correlation(router.conn, outcome.correlation_id)
        assert [r["event_type"] for r in rows] == [
            "ORDER_INTENT",
            "ORDER_SUBMITTED",
        ]
