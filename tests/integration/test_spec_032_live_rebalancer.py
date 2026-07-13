"""Spec 032 slice 2 — live/paper rebalance executor integration tests.

Runs the executor against a real OrderRouter in PAPER mode (no broker calls),
with seeded daily bars + holdings and an injected quote provider. Verifies:
  - the rebalance buys the top names AND sells a dropped-out holding (exit),
  - every routed order passes the real K1 gate chain (PAPER_FILLED),
  - large orders are clamped DOWN to the per-trade cap (never rejected),
  - the run is deterministic.

No money moves: paper mode records ORDER_PAPER_FILLED to the audit log only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from auto_invest.broker.client import AsyncTokenBucket, CircuitBreaker, ResilientClient
from auto_invest.broker.models import Quote
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderOutcome, OrderRouter
from auto_invest.execution.rebalancer import execute_rebalance
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db
from auto_invest.persistence import positions as positions_mod

_D0 = datetime(2023, 1, 3, tzinfo=UTC)
ACCOUNT = "REBAL-ACCT"


def _caps(per_trade="60", per_symbol="65", glob="100") -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal(per_trade),
        per_symbol_pct=Decimal(per_symbol),
        global_exposure_pct=Decimal(glob),
        canary_capital_pct=Decimal("1"),
        canary_min_duration_days=5,
        canary_acceptance_drawdown_pct=Decimal("80"),
    )


def _whitelist(symbols) -> Whitelist:
    return Whitelist(
        symbols=frozenset(symbols),
        accounts=frozenset({ACCOUNT}),
        order_types=frozenset({OrderType.LIMIT}),
    )


def _seed_bars(conn, symbol: str, closes: list[float], timeframe="1d") -> None:
    for i, c in enumerate(closes):
        price = Decimal(str(c))
        insert_bar(
            conn,
            PriceBar(
                symbol=symbol,
                timeframe=timeframe,
                bar_open_utc=(_D0 + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00.000Z"),
                open_usd=price,
                high_usd=(price * Decimal("1.01")).quantize(Decimal("0.0001")),
                low_usd=(price * Decimal("0.99")).quantize(Decimal("0.0001")),
                close_usd=price,
                volume=10_000_000,
            ),
        )


def _seed_holding(conn, symbol: str, qty: int, price: str) -> None:
    positions_mod.update_from_fill(
        conn,
        symbol=symbol,
        side=Side.BUY,
        qty=qty,
        price_usd=Decimal(price),
        ts_utc="2023-01-02T00:00:00.000Z",
    )


def _quote_provider(prices: dict[str, str]):
    async def provider(symbol: str) -> Quote:
        p = Decimal(prices[symbol])
        return Quote(
            symbol=symbol,
            last_price_usd=p,
            bid_usd=(p * Decimal("0.999")).quantize(Decimal("0.01")),
            ask_usd=(p * Decimal("1.001")).quantize(Decimal("0.01")),
            quoted_at_utc=datetime(2023, 6, 1, tzinfo=UTC),
        )

    return provider


def _paper_router(conn, tmp_path: Path, whitelist, caps) -> OrderRouter:
    inner = httpx.AsyncClient(base_url="http://test")
    client = ResilientClient(
        inner,
        rate_limiter=AsyncTokenBucket(rate_per_sec=100.0, capacity=10.0),
        breaker=CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0),
        max_retries=1,
    )
    return OrderRouter(
        conn=conn,
        broker=client,
        access_token="tok",
        app_key="app",
        app_secret="sec",
        account_no=ACCOUNT,
        whitelist=whitelist,
        caps=caps,
        halt_path=tmp_path / "halt.flag",
        market="NASD",
        paper_mode=True,
        paper_session_id=1,
    )


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "rebal.db")
    db.migrate(c)
    yield c
    c.close()


def _cfg(universe, **overrides) -> PortfolioRebalanceConfig:
    base = dict(
        id="p1",
        universe=universe,
        weights={"momentum": Decimal("1")},
        top_n=2,
        weight_scheme="equal",
        invested_fraction=Decimal("0.6"),
        lookback_bars=30,
        momentum_period=10,
    )
    base.update(overrides)
    return PortfolioRebalanceConfig(**base)


@pytest.mark.asyncio
async def test_rebalance_buys_top_and_exits_dropout(conn, tmp_path):
    # WIN/MID trend up (top momentum); LOSE trends down; we already hold LOSE.
    _seed_bars(conn, "WIN", [100 * (1.01**i) for i in range(40)])
    _seed_bars(conn, "MID", [100 * (1.005**i) for i in range(40)])
    _seed_bars(conn, "LOSE", [100 * (0.99**i) for i in range(40)])
    _seed_holding(conn, "LOSE", 10, "100")

    universe = ("WIN", "MID", "LOSE")
    router = _paper_router(conn, tmp_path, _whitelist(universe), _caps())
    out = await execute_rebalance(
        config=_cfg(universe),
        router=router,
        conn=conn,
        quote_provider=_quote_provider({"WIN": "150", "MID": "120", "LOSE": "60"}),
        total_capital_usd=Decimal("100000"),
        caps=_caps(),
    )

    by_symbol = {r.symbol: r for r in out.results}
    # WIN/MID are the top-2 momentum names -> bought and paper-filled.
    assert by_symbol["WIN"].side == "BUY" and by_symbol["WIN"].state == "PAPER_FILLED"
    assert by_symbol["MID"].side == "BUY" and by_symbol["MID"].state == "PAPER_FILLED"
    # LOSE dropped out -> fully sold (the exit dimension), and the sell fills.
    assert by_symbol["LOSE"].side == "SELL" and by_symbol["LOSE"].state == "PAPER_FILLED"
    assert by_symbol["LOSE"].routed_qty == 10


@pytest.mark.asyncio
async def test_large_order_clamped_to_per_trade_cap(conn, tmp_path):
    # top_n=1 with invested 0.5 -> a single 50% target. With a 10% per-trade cap
    # the order is clamped DOWN to ~10% notional and PAPER_FILLED (never rejected).
    _seed_bars(conn, "AAA", [100 * (1.01**i) for i in range(40)])
    _seed_bars(conn, "BBB", [100 * (1.001**i) for i in range(40)])
    universe = ("AAA", "BBB")
    caps = _caps(per_trade="10", per_symbol="60", glob="100")
    router = _paper_router(conn, tmp_path, _whitelist(universe), caps)
    out = await execute_rebalance(
        config=_cfg(universe, top_n=1, invested_fraction=Decimal("0.5")),
        router=router,
        conn=conn,
        quote_provider=_quote_provider({"AAA": "100", "BBB": "100"}),
        total_capital_usd=Decimal("100000"),
        caps=caps,
    )
    aaa = next(r for r in out.results if r.symbol == "AAA")
    assert aaa.side == "BUY"
    assert aaa.state == "PAPER_FILLED"
    # per-trade cap = 10% of 100k = $10,000; at limit ~$100.10 -> floor(10000/100.1)=99.
    assert aaa.routed_qty <= 100
    assert aaa.routed_qty < aaa.requested_qty  # clamped down


@pytest.mark.asyncio
async def test_rebalance_reserves_successful_buys_before_next_buy(conn, tmp_path):
    _seed_bars(conn, "AAA", [100 * (1.01**i) for i in range(40)])
    _seed_bars(conn, "BBB", [100 * (1.009**i) for i in range(40)])
    universe = ("AAA", "BBB")
    caps = _caps(per_trade="50", per_symbol="50", glob="50")
    router = _paper_router(conn, tmp_path, _whitelist(universe), caps)

    out = await execute_rebalance(
        config=_cfg(universe, top_n=2, invested_fraction=Decimal("0.6")),
        router=router,
        conn=conn,
        quote_provider=_quote_provider({"AAA": "100", "BBB": "100"}),
        total_capital_usd=Decimal("100000"),
        caps=caps,
    )

    buy_states = [r.state for r in out.results if r.side == "BUY"]
    assert buy_states.count("PAPER_FILLED") == 1
    assert buy_states.count("REJECTED_BY_GATE") == 1
    rejected = next(r for r in out.results if r.state == "REJECTED_BY_GATE")
    assert rejected.reason is not None
    assert "global exposure" in rejected.reason


@pytest.mark.asyncio
async def test_rebalance_deterministic(conn, tmp_path):
    _seed_bars(conn, "AAA", [100 + i * 0.5 for i in range(40)])
    _seed_bars(conn, "BBB", [100 + i * 0.3 for i in range(40)])
    _seed_bars(conn, "CCC", [100 + i * 0.1 for i in range(40)])
    universe = ("AAA", "BBB", "CCC")
    caps = _caps()

    async def run():
        c = db.get_connection(tmp_path / f"d{datetime.now(UTC).timestamp()}.db")
        db.migrate(c)
        _seed_bars(c, "AAA", [100 + i * 0.5 for i in range(40)])
        _seed_bars(c, "BBB", [100 + i * 0.3 for i in range(40)])
        _seed_bars(c, "CCC", [100 + i * 0.1 for i in range(40)])
        router = _paper_router(c, tmp_path, _whitelist(universe), caps)
        out = await execute_rebalance(
            config=_cfg(universe, top_n=2),
            router=router,
            conn=c,
            quote_provider=_quote_provider({"AAA": "120", "BBB": "110", "CCC": "100"}),
            total_capital_usd=Decimal("100000"),
            caps=caps,
        )
        c.close()
        return [(r.symbol, r.side, r.routed_qty, r.state) for r in out.results]

    assert await run() == await run()


@pytest.mark.asyncio
async def test_rebalance_threads_per_symbol_order_exchange(conn, tmp_path):
    """리밸런서는 각 종목의 시세 거래소(quote.resolved_market)를 주문 거래소로 옮긴다.

    검증된 멀티에셋 유니버스(SPY=AMS→AMEX, IEF=NAS→NASD)가 라이브로 갈 때 각 주문이
    *종목별 올바른 거래소*로 라우팅돼야 한다 — 단일 고정 거래소면 SPY 가 거부된다. 여기서는
    submit_order 가 받은 order_exchange 를 캡처해 SPY→AMEX, IEF→NASD 임을 직접 검증한다.
    """
    # 둘 다 추세 위(상승)라 보유 대상. top_n=2 = 둘 다 매수.
    _seed_bars(conn, "SPY", [100 * (1.01**i) for i in range(40)])
    _seed_bars(conn, "IEF", [100 * (1.002**i) for i in range(40)])
    universe = ("SPY", "IEF")

    resolved = {"SPY": "AMS", "IEF": "NAS"}  # 시세 해석기가 알아낸 상장 거래소

    def _provider_with_market(prices: dict[str, str]):
        async def provider(symbol: str) -> Quote:
            p = Decimal(prices[symbol])
            return Quote(
                symbol=symbol,
                last_price_usd=p,
                bid_usd=(p * Decimal("0.999")).quantize(Decimal("0.01")),
                ask_usd=(p * Decimal("1.001")).quantize(Decimal("0.01")),
                quoted_at_utc=datetime(2023, 6, 1, tzinfo=UTC),
                resolved_market=resolved[symbol],
            )

        return provider

    class _CapturingRouter:
        def __init__(self) -> None:
            self.seen: dict[str, str | None] = {}

        async def submit_order(self, *, rule, order_exchange=None, **kwargs):  # noqa: ANN001
            self.seen[rule.symbol] = order_exchange
            return OrderOutcome(state="PAPER_FILLED", correlation_id="c")

    router = _CapturingRouter()
    await execute_rebalance(
        config=_cfg(universe, top_n=2),
        router=router,
        conn=conn,
        quote_provider=_provider_with_market({"SPY": "540", "IEF": "95"}),
        total_capital_usd=Decimal("100000"),
        caps=_caps(),
    )
    # 각 종목이 시세 거래소에 맞는 주문 거래소로 라우팅됐는지: SPY(AMS)→AMEX, IEF(NAS)→NASD.
    assert router.seen["SPY"] == "AMEX"
    assert router.seen["IEF"] == "NASD"


@pytest.mark.asyncio
async def test_dry_run_computes_plan_but_routes_nothing(conn, tmp_path):
    """`dry_run=True` previews the full plan (buys top names, sells the dropout)
    but NEVER calls the router — proven by a router that explodes if touched."""
    _seed_bars(conn, "WIN", [100 * (1.01 ** i) for i in range(40)])
    _seed_bars(conn, "MID", [100 * (1.005 ** i) for i in range(40)])
    _seed_bars(conn, "LOSE", [100 * (0.99 ** i) for i in range(40)])
    _seed_holding(conn, "LOSE", 10, "100")
    universe = ("WIN", "MID", "LOSE")

    class _BoomRouter:
        async def submit_order(self, **kwargs):
            raise AssertionError("dry_run must not route any order")

    out = await execute_rebalance(
        config=_cfg(universe),
        router=_BoomRouter(),
        conn=conn,
        quote_provider=_quote_provider({"WIN": "150", "MID": "120", "LOSE": "60"}),
        total_capital_usd=Decimal("100000"),
        caps=_caps(),
        dry_run=True,
    )
    assert out.results
    assert all(r.state == "DRY_RUN" for r in out.results)
    sides = {(r.symbol, r.side) for r in out.results}
    assert ("LOSE", "SELL") in sides  # dropout previewed as a sell
    assert ("WIN", "BUY") in sides  # top name previewed as a buy


@pytest.mark.asyncio
async def test_account_wide_cash_shortfall_runs_sell_only_and_withholds_buys(
    conn, tmp_path
):
    """계좌 전체 모드는 브로커 보유를 실제 자본으로 보되, 현금 부족이면 매도부터 한다."""
    for sym, growth in (("SPYM", 1.01), ("IEF", 1.004), ("GLDM", 1.006)):
        _seed_bars(conn, sym, [100 * (growth**i) for i in range(40)])

    class _BoomRouter:
        async def submit_order(self, **kwargs):
            raise AssertionError("dry_run must not route any order")

    out = await execute_rebalance(
        config=_cfg(("SPYM", "IEF", "GLDM"), top_n=3, invested_fraction=Decimal("0.99")),
        router=_BoomRouter(),
        conn=conn,
        quote_provider=_quote_provider(
            {
                "SPYM": "90",
                "IEF": "95",
                "GLDM": "65",
                "BHP": "48",
                "MRK": "80",
            }
        ),
        total_capital_usd=Decimal("1000"),
        caps=_caps(per_trade="100", per_symbol="100", glob="100"),
        dry_run=True,
        account_holdings={"BHP": 1, "MRK": 3, "UNMANAGED": 2},
        liquidation_only_symbols=frozenset({"BHP", "MRK"}),
        execution_side="both",
        purchasable_cash_usd=Decimal("10"),
    )

    assert out.account_wide is True
    assert out.effective_side == "sell"
    assert out.planned_buy_notional_usd > 0
    assert out.planned_sell_notional_usd > 0
    assert {(r.symbol, r.side) for r in out.results} == {("BHP", "SELL"), ("MRK", "SELL")}
    assert all(r.state == "DRY_RUN" for r in out.results)
    withheld = {(w.symbol, w.side, w.reason) for w in out.withheld}
    assert ("SPYM", "BUY", "cash_shortfall_sell_first") in withheld
    assert ("UNMANAGED", "SELL", "unmanaged_holding") in withheld


@pytest.mark.asyncio
async def test_account_wide_refuses_liquidation_only_buy_symbol(conn, tmp_path):
    _seed_bars(conn, "BHP", [100 * (1.01**i) for i in range(40)])
    _seed_bars(conn, "IEF", [100 * (1.002**i) for i in range(40)])

    class _BoomRouter:
        async def submit_order(self, **kwargs):
            raise AssertionError("must fail before routing")

    with pytest.raises(ValueError, match="liquidation-only.*target"):
        await execute_rebalance(
            config=_cfg(("BHP", "IEF"), top_n=1, invested_fraction=Decimal("0.99")),
            router=_BoomRouter(),
            conn=conn,
            quote_provider=_quote_provider({"BHP": "48", "IEF": "95"}),
            total_capital_usd=Decimal("1000"),
            caps=_caps(),
            dry_run=True,
            account_holdings={},
            liquidation_only_symbols=frozenset({"BHP"}),
            execution_side="both",
            purchasable_cash_usd=Decimal("1000"),
        )
