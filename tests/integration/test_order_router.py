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
from auto_invest.execution.authority import ExecutionAuthority
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
    side: Side = Side.BUY,
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
        action=Action(side=side, order_type=OrderType.LIMIT, qty=qty, limit_price=limit_price),
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


def _authority_lock_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM execution_authority_locks").fetchone()[0]


@asynccontextmanager
async def _router(
    tmp_path: Path,
    *,
    halt_set: bool = False,
    live_order_guard=None,  # noqa: ANN001 - injectable safety hook for tests.
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
            live_order_guard=live_order_guard,
        )

    conn.close()


# ------------------------------------------------------ limit_price expression


def test_evaluate_limit_price_literal():
    assert evaluate_limit_price("100.50", trigger_price=Decimal("99"), last_close=None) == Decimal(
        "100.50"
    )


def test_evaluate_limit_price_trigger_minus():
    result = evaluate_limit_price("trigger - 0.10", trigger_price=Decimal("100"), last_close=None)
    assert result == Decimal("99.90")


def test_evaluate_limit_price_trigger_plus():
    result = evaluate_limit_price("trigger + 0.25", trigger_price=Decimal("100"), last_close=None)
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
        evaluate_limit_price("trigger ** 2", trigger_price=Decimal("10"), last_close=None)


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
async def test_submit_order_rejected_when_execution_authority_locked(tmp_path: Path):
    async with _router(tmp_path) as router:
        router.execution_authority = ExecutionAuthority(
            conn=router.conn,
            broker=router.broker,
            access_token=router.access_token,
            app_key=router.app_key,
            app_secret=router.app_secret,
            account_no=router.account_no,
            lock_timeout_seconds=0,
        )
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )
            async with router.execution_authority.account_lock("already routing"):
                outcome = await router.submit_order(
                    rule=_rule(),
                    quote_price_usd=Decimal("99"),
                    total_capital_usd=Decimal("10000"),
                    current_symbol_exposure_usd=Decimal("0"),
                    current_global_exposure_usd=Decimal("0"),
                )

        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "execution_authority_lock"
        assert placed.call_count == 0

        rejected = next(
            r for r in audit.read_all(router.conn)
            if r["event_type"] == "ORDER_REJECTED_BY_GATE"
        )
        payload = audit.parse_payload(rejected)
        assert payload["metadata"]["account_no"] == ACCOUNT


@pytest.mark.asyncio
async def test_submit_order_happy_path(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-001"}})
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

        order_row = router.conn.execute("SELECT state, kis_order_id FROM orders").fetchone()
        assert order_row["state"] == "SUBMITTED"
        assert order_row["kis_order_id"] == "K-001"
        transitions = [
            (r["from_state"], r["to_state"])
            for r in router.conn.execute(
                """
                SELECT from_state, to_state
                FROM order_state_history
                ORDER BY seq
                """
            ).fetchall()
        ]
        assert transitions == [
            (None, "INTENT"),
            ("INTENT", "SUBMITTING"),
            ("SUBMITTING", "SUBMITTED"),
        ]
        assert _authority_lock_count(router.conn) == 0


@pytest.mark.asyncio
async def test_live_order_guard_rechecks_each_broker_submission(tmp_path: Path):
    checks = iter([None, "XNYS regular session is closed"])

    async with _router(tmp_path, live_order_guard=lambda: next(checks)) as router:
        with respx.mock(base_url=BASE) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-001"}})
            )
            first = await router.submit_order(
                rule=_rule(rule_id="first"),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )
            second = await router.submit_order(
                rule=_rule(rule_id="second"),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert first.state == "SUBMITTED"
        assert second.state == "REJECTED_BY_GATE"
        assert second.gate == "market_hours_gate"
        assert second.reason == "XNYS regular session is closed"
        assert placed.call_count == 1

        rejected = [
            row
            for row in audit.read_all(router.conn)
            if row["event_type"] == "ORDER_REJECTED_BY_GATE"
        ]
        assert audit.parse_payload(rejected[-1])["gate"] == "market_hours_gate"
        assert _authority_lock_count(router.conn) == 0


@pytest.mark.asyncio
async def test_submit_order_routes_to_per_symbol_exchange(tmp_path: Path):
    """order_exchange 가 주어지면 그 거래소(OVRS_EXCG_CD)로 주문이 나간다.

    검증된 멀티에셋 유니버스(SPY·GLD=AMEX)는 라우터 기본 거래소(NASD)가 아니라 시세
    해석기가 알아낸 종목별 거래소로 라우팅돼야 한다 — 그래야 라이브 첫 실주문이 거부 안 됨.
    """
    import json as _json

    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-AMEX"}})
            )
            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
                order_exchange="AMEX",
            )
        assert outcome.state == "SUBMITTED"
        sent = _json.loads(route.calls.last.request.content)
        assert sent["OVRS_EXCG_CD"] == "AMEX"


@pytest.mark.asyncio
async def test_submit_order_falls_back_to_router_market_exchange(tmp_path: Path):
    """order_exchange 가 None 이면 라우터에 설정된 기본 거래소(self.market)로 폴백한다.

    단일 거래소 룰 워커는 항상 None 을 넘기므로 종전 동작과 byte 동일(회귀 0).
    """
    import json as _json

    async with _router(tmp_path) as router:  # router.market == "NASD"
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-DFLT"}})
            )
            await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )
        sent = _json.loads(route.calls.last.request.content)
        assert sent["OVRS_EXCG_CD"] == "NASD"


@pytest.mark.asyncio
async def test_submit_order_records_decision_price_on_intent(tmp_path: Path):
    """spec 028 FR-028-02 — ORDER_INTENT 에 결정 순간의 arrival 시세·호가가 기록된다."""
    import json as _json

    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-009"}})
            )
            await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("98.50"),
                quote_ask_usd=Decimal("98.60"),
                quote_bid_usd=Decimal("98.40"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )
        intent = next(
            r for r in audit.read_all(router.conn) if r["event_type"] == "ORDER_INTENT"
        )
        p = _json.loads(intent["payload_json"])
        assert p["decision_price_usd"] == "98.50"
        assert p["decision_ask_usd"] == "98.60"
        assert p["decision_bid_usd"] == "98.40"


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

        order_row = router.conn.execute("SELECT state FROM orders").fetchone()
        assert order_row["state"] == "REJECTED_BY_GATE"
        assert _authority_lock_count(router.conn) == 0


@pytest.mark.parametrize("open_state", ["SUBMITTED", "PARTIALLY_FILLED"])
@pytest.mark.asyncio
async def test_submit_order_counts_open_buy_orders_as_reserved_global_exposure(
    tmp_path: Path,
    open_state: str,
):
    async with _router(tmp_path) as router:
        router.conn.execute(
            """
            INSERT INTO orders
                (correlation_id, rule_id, symbol, side, order_type, qty,
                 limit_price_usd, state)
            VALUES ('ord-open-buy', 'open-rule', 'MSFT', 'BUY', 'LIMIT', 79,
                    '100.00', ?)
            """,
            (open_state,),
        )
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )

            # Existing open BUY reserves $7,900. New BUY is only $200, but the
            # combined exposure exceeds the global cap: 80% of $10,000 = $8,000.
            outcome = await router.submit_order(
                rule=_rule(qty=2, limit_price="100.00"),
                quote_price_usd=Decimal("100"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "global_exposure_gate"
        assert placed.call_count == 0

        rejected = next(
            r for r in audit.read_all(router.conn)
            if r["event_type"] == "ORDER_REJECTED_BY_GATE"
        )
        payload = audit.parse_payload(rejected)
        assert payload["metadata"]["would_become_usd"] == "8100.00"


@pytest.mark.asyncio
async def test_submit_order_blocks_buy_when_execution_state_degraded(tmp_path: Path):
    from auto_invest.execution.execution_state import (
        ExecutionState,
        ExecutionStateReason,
    )

    async with _router(tmp_path) as router:
        router.execution_state_provider = lambda: ExecutionState.degraded(
            [
                ExecutionStateReason(
                    code="fill_sync_error",
                    detail="fill sync failed while open orders exist",
                )
            ]
        )
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )

            outcome = await router.submit_order(
                rule=_rule(side=Side.BUY),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "execution_state_gate"
        assert placed.call_count == 0

        rejected = next(
            r for r in audit.read_all(router.conn)
            if r["event_type"] == "ORDER_REJECTED_BY_GATE"
        )
        payload = audit.parse_payload(rejected)
        assert payload["metadata"]["status"] == "DEGRADED_SELL_ONLY"
        assert payload["metadata"]["reason_codes"] == ["fill_sync_error"]


@pytest.mark.asyncio
async def test_submit_order_blocks_buy_when_submission_unknown_buy_exists(
    tmp_path: Path,
):
    async with _router(tmp_path) as router:
        router.conn.execute(
            """
            INSERT INTO orders
                (correlation_id, rule_id, symbol, side, order_type, qty,
                 limit_price_usd, state)
            VALUES ('ord-unknown-buy', 'unknown-rule', 'AAPL', 'BUY', 'LIMIT', 1,
                    '100.00', 'SUBMISSION_UNKNOWN')
            """
        )
        with respx.mock(base_url=BASE, assert_all_called=False) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "x"}})
            )

            outcome = await router.submit_order(
                rule=_rule(side=Side.BUY),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "REJECTED_BY_GATE"
        assert outcome.gate == "execution_state_gate"
        assert placed.call_count == 0


@pytest.mark.asyncio
async def test_submit_order_allows_sell_when_execution_state_degraded(tmp_path: Path):
    from auto_invest.execution.execution_state import (
        ExecutionState,
        ExecutionStateReason,
    )

    async with _router(tmp_path) as router:
        router.execution_state_provider = lambda: ExecutionState.degraded(
            [
                ExecutionStateReason(
                    code="reconciliation_inconclusive",
                    detail="latest reconciliation could not read broker state",
                )
            ]
        )
        router.conn.execute(
            """
            INSERT INTO current_positions(symbol, qty, avg_cost_usd, last_updated_utc)
            VALUES ('AAPL', 5, '100.00', '2026-07-21T00:00:00.000Z')
            """
        )
        with respx.mock(base_url=BASE) as mock:
            placed = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-SELL"}})
            )

            outcome = await router.submit_order(
                rule=_rule(side=Side.SELL),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("500"),
                current_global_exposure_usd=Decimal("500"),
            )

        assert outcome.state == "SUBMITTED"
        assert outcome.kis_order_id == "K-SELL"
        assert placed.call_count == 1


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
async def test_submit_order_submission_unknown_on_broker_5xx(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(500, json={"err": "x"})
            )

            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "SUBMISSION_UNKNOWN"
        assert route.call_count == 1
        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert "ORDER_SUBMISSION_UNKNOWN" in events
        assert "ORDER_REJECTED_BY_BROKER" not in events

        order_row = router.conn.execute("SELECT state FROM orders").fetchone()
        assert order_row["state"] == "SUBMISSION_UNKNOWN"
        transition = router.conn.execute(
            """
            SELECT from_state, to_state
            FROM order_state_history
            ORDER BY seq DESC
            LIMIT 1
            """
        ).fetchone()
        assert (transition["from_state"], transition["to_state"]) == (
            "SUBMITTING",
            "SUBMISSION_UNKNOWN",
        )
        unknown_payload = next(
            audit.parse_payload(r)
            for r in audit.read_all(router.conn)
            if r["event_type"] == "ORDER_SUBMISSION_UNKNOWN"
        )
        assert "자동 재시도하지" in unknown_payload["next_action"]
        assert _authority_lock_count(router.conn) == 0


@pytest.mark.asyncio
async def test_submit_order_submission_unknown_on_transport_error(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                side_effect=httpx.ConnectError("wire dropped")
            )

            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "SUBMISSION_UNKNOWN"
        assert route.call_count == 1
        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert events == ["ORDER_INTENT", "ORDER_SUBMISSION_UNKNOWN"]

        order_row = router.conn.execute("SELECT state, kis_order_id FROM orders").fetchone()
        assert order_row["state"] == "SUBMISSION_UNKNOWN"
        assert order_row["kis_order_id"] is None


@pytest.mark.asyncio
async def test_submit_order_keeps_kis_business_rejection_as_broker_rejection(
    tmp_path: Path,
):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            route = mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "rt_cd": "1",
                        "msg_cd": "APBK1234",
                        "msg1": "주문 가능 금액 부족",
                    },
                )
            )

            outcome = await router.submit_order(
                rule=_rule(),
                quote_price_usd=Decimal("99"),
                total_capital_usd=Decimal("10000"),
                current_symbol_exposure_usd=Decimal("0"),
                current_global_exposure_usd=Decimal("0"),
            )

        assert outcome.state == "REJECTED_BY_BROKER"
        assert route.call_count == 1
        events = [r["event_type"] for r in audit.read_all(router.conn)]
        assert "ORDER_REJECTED_BY_BROKER" in events
        assert "ORDER_SUBMISSION_UNKNOWN" not in events


@pytest.mark.asyncio
async def test_submit_order_records_correlation_id_across_events(tmp_path: Path):
    async with _router(tmp_path) as router:
        with respx.mock(base_url=BASE) as mock:
            mock.post("/uapi/overseas-stock/v1/trading/order").mock(
                return_value=httpx.Response(200, json={"output": {"ODNO": "K-001"}})
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
