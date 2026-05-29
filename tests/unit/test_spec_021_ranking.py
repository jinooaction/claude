"""스펙 021 — 횡단면 모멘텀 순위 필터 테스트.

SC-01: 3종목 유니버스에서 1위 심볼 → top_n=2 통과
SC-02: 3종목 유니버스에서 3위 심볼 → top_n=2 미통과 → SKIPPED_BY_RANKING
SC-03: top_pct=50 필터 — 4종목 유니버스에서 3위 이하 스킵
SC-04: 바 부족 심볼은 순위 맨 뒤 → 데이터 충분한 심볼에 밀려 스킵
SC-05: ranking_filter=None → 주문 경로 byte 동일 (PAPER_FILLED)
SC-06: 백테스트 replay에서 랭킹 필터 적용 → 하위 종목 주문 수 감소
SC-07: 기존 테스트 전부 통과 (이 파일 외부 검증)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import exchange_calendars as ec
import pytest

from auto_invest.backtest.broker_mock import BacktestBroker
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.replay import replay
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, RankingFilter, TimeTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderRouter
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db as _db_mod
from auto_invest.strategy.ranking import cross_sectional_momentum, is_top_n, is_top_pct

_CAL = ec.get_calendar("XNYS")


# =========================================================================== #
# helpers                                                                      #
# =========================================================================== #


def _open_db(path: Path) -> sqlite3.Connection:
    conn = _db_mod.get_connection(path)
    _db_mod.migrate(conn)
    return conn


def _sessions(start: date, n: int) -> list[date]:
    sessions = _CAL.sessions_in_range(
        start.strftime("%Y-%m-%d"),
        (start + timedelta(days=n * 3)).strftime("%Y-%m-%d"),
    )
    return [s.date() for s in sessions[:n]]


def _make_bars(symbol: str, closes: list[float]) -> list[PriceBar]:
    """Build PriceBars with sequential fake timestamps."""
    bars = []
    base = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)
    for i, c in enumerate(closes):
        ts = (base + timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        p = Decimal(str(c))
        bars.append(
            PriceBar(
                symbol=symbol,
                timeframe="1d",
                bar_open_utc=ts,
                open_usd=p,
                high_usd=p,
                low_usd=p,
                close_usd=p,
                volume=1000,
            )
        )
    return bars


def _insert_bars(conn: sqlite3.Connection, bars: list[PriceBar]) -> None:
    for b in bars:
        insert_bar(conn, b)


def _make_time_rule(symbol: str, *, ranking_filter: RankingFilter | None = None) -> TradingRule:
    return TradingRule(
        id=f"rule-{symbol.lower()}",
        symbol=symbol,
        stage=StrategyStage.FULL_LIVE,
        priority=1,
        trigger=TimeTrigger(at_time="14:30", cooldown_seconds=0),
        action=Action(side=Side.BUY, order_type=OrderType.MARKET, qty=10, limit_price="100"),
        ranking_filter=ranking_filter,
    )


def _make_caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("10"),
        per_symbol_pct=Decimal("20"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("3"),
    )


def _make_whitelist(*symbols: str) -> Whitelist:
    return Whitelist(
        symbols=list(symbols),
        order_types=["MARKET"],
        accounts=["x"],
    )


def _make_router(  # noqa: PLR0913
    conn: sqlite3.Connection, *symbols: str, tmp_path: Path | None = None
) -> OrderRouter:
    halt = (tmp_path / "halt") if tmp_path else Path("/tmp/halt-021")
    return OrderRouter(
        conn=conn,
        broker=MagicMock(),
        access_token="x",
        app_key="x",
        app_secret="x",
        account_no="x",
        whitelist=_make_whitelist(*symbols),
        caps=_make_caps(),
        halt_path=halt,
        paper_mode=True,
    )


async def _submit(router: OrderRouter, rule: TradingRule, price: Decimal = Decimal("100")):
    return await router.submit_order(
        rule=rule,
        quote_price_usd=price,
        total_capital_usd=Decimal("100000"),
        current_symbol_exposure_usd=Decimal("0"),
        current_global_exposure_usd=Decimal("0"),
    )


# =========================================================================== #
# unit tests — ranking module                                                  #
# =========================================================================== #


def test_cross_sectional_momentum_order():
    """Best performer comes first."""
    universe = {
        "AAA": _make_bars("AAA", [100, 110]),   # +10%
        "BBB": _make_bars("BBB", [100, 105]),   # +5%
        "CCC": _make_bars("CCC", [100, 102]),   # +2%
    }
    ranked = cross_sectional_momentum(universe, period=1)
    symbols = [s for s, _ in ranked]
    assert symbols == ["AAA", "BBB", "CCC"]


def test_insufficient_bars_goes_last():
    """Symbol with < period+1 bars is sorted to bottom with -Inf sentinel."""
    universe = {
        "GOOD": _make_bars("GOOD", [100, 120]),   # +20%, period=1 OK
        "POOR": _make_bars("POOR", [100]),         # only 1 bar, period=1 needs 2
    }
    ranked = cross_sectional_momentum(universe, period=1)
    assert ranked[0][0] == "GOOD"
    assert ranked[1][0] == "POOR"
    assert ranked[1][1] == Decimal("-Inf")


def test_is_top_n_pass():
    ranked = [("A", Decimal("10")), ("B", Decimal("5")), ("C", Decimal("1"))]
    assert is_top_n("A", ranked, 2) is True
    assert is_top_n("B", ranked, 2) is True


def test_is_top_n_fail():
    ranked = [("A", Decimal("10")), ("B", Decimal("5")), ("C", Decimal("1"))]
    assert is_top_n("C", ranked, 2) is False


def test_is_top_pct_boundary():
    """4 symbols, top_pct=50 → top 2."""
    ranked = [
        ("A", Decimal("10")),
        ("B", Decimal("8")),
        ("C", Decimal("3")),
        ("D", Decimal("1")),
    ]
    assert is_top_pct("A", ranked, 50) is True
    assert is_top_pct("B", ranked, 50) is True
    assert is_top_pct("C", ranked, 50) is False
    assert is_top_pct("D", ranked, 50) is False


# =========================================================================== #
# SC-01: 1위 심볼 → top_n=2 통과                                              #
# =========================================================================== #


@pytest.mark.asyncio
async def test_sc01_top_symbol_passes(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    # AAA: +10%, BBB: +5%, CCC: +2%
    _insert_bars(conn, _make_bars("AAA", [100, 110]))
    _insert_bars(conn, _make_bars("BBB", [100, 105]))
    _insert_bars(conn, _make_bars("CCC", [100, 102]))

    rf = RankingFilter(universe=("AAA", "BBB", "CCC"), period=1, top_n=2)
    rule = _make_time_rule("AAA", ranking_filter=rf)
    router = _make_router(conn, "AAA", "BBB", "CCC", tmp_path=tmp_path)

    outcome = await _submit(router, rule)
    assert outcome.state == "PAPER_FILLED", outcome


# =========================================================================== #
# SC-02: 3위 심볼 → top_n=2 미통과                                            #
# =========================================================================== #


@pytest.mark.asyncio
async def test_sc02_bottom_symbol_skipped(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    _insert_bars(conn, _make_bars("AAA", [100, 110]))
    _insert_bars(conn, _make_bars("BBB", [100, 105]))
    _insert_bars(conn, _make_bars("CCC", [100, 102]))

    rf = RankingFilter(universe=("AAA", "BBB", "CCC"), period=1, top_n=2)
    rule = _make_time_rule("CCC", ranking_filter=rf)
    router = _make_router(conn, "AAA", "BBB", "CCC", tmp_path=tmp_path)

    outcome = await _submit(router, rule)
    assert outcome.state == "SKIPPED_BY_RANKING"
    assert outcome.reason == "not_in_top"


# =========================================================================== #
# SC-03: top_pct=50, 4종목 유니버스                                           #
# =========================================================================== #


@pytest.mark.asyncio
async def test_sc03_top_pct_filter(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    _insert_bars(conn, _make_bars("A", [100, 120]))  # +20% rank 1
    _insert_bars(conn, _make_bars("B", [100, 115]))  # +15% rank 2
    _insert_bars(conn, _make_bars("C", [100, 105]))  # +5%  rank 3
    _insert_bars(conn, _make_bars("D", [100, 101]))  # +1%  rank 4

    rf = RankingFilter(universe=("A", "B", "C", "D"), period=1, top_pct=50.0)
    router = _make_router(conn, "A", "B", "C", "D", tmp_path=tmp_path)

    outcome_a = await _submit(router, _make_time_rule("A", ranking_filter=rf))
    outcome_c = await _submit(router, _make_time_rule("C", ranking_filter=rf))

    assert outcome_a.state == "PAPER_FILLED"
    assert outcome_c.state == "SKIPPED_BY_RANKING"


# =========================================================================== #
# SC-04: 바 부족 심볼은 순위 맨 뒤                                            #
# =========================================================================== #


@pytest.mark.asyncio
async def test_sc04_insufficient_bars_goes_last(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    _insert_bars(conn, _make_bars("RICH", [100, 110]))  # 2 bars, period=1 OK
    _insert_bars(conn, _make_bars("POOR", [100]))        # 1 bar, insufficient

    rf = RankingFilter(universe=("RICH", "POOR"), period=1, top_n=1)
    router = _make_router(conn, "RICH", "POOR", tmp_path=tmp_path)

    outcome_poor = await _submit(router, _make_time_rule("POOR", ranking_filter=rf))
    assert outcome_poor.state == "SKIPPED_BY_RANKING"

    outcome_rich = await _submit(router, _make_time_rule("RICH", ranking_filter=rf))
    assert outcome_rich.state == "PAPER_FILLED"


# =========================================================================== #
# SC-05: ranking_filter=None → 기존 경로 동일                                 #
# =========================================================================== #


@pytest.mark.asyncio
async def test_sc05_no_filter_passthrough(tmp_path):
    conn = _open_db(tmp_path / "db.sqlite3")
    rule = _make_time_rule("SPY")  # no ranking_filter
    router = _make_router(conn, "SPY", tmp_path=tmp_path)

    outcome = await _submit(router, rule)
    assert outcome.state == "PAPER_FILLED"


# =========================================================================== #
# SC-06: 백테스트 replay 랭킹 필터 적용                                       #
# =========================================================================== #


def _make_ohlcv(symbol: str, sessions: list[date], prices: list[float]) -> list[OHLCVBar]:
    bars = []
    for s, p in zip(sessions, prices, strict=True):
        pd = Decimal(str(p))
        bars.append(
            OHLCVBar(
                symbol=symbol,
                session_date=s,
                open=pd,
                high=pd * Decimal("1.001"),
                low=pd * Decimal("0.999"),
                close=pd,
                volume=10000,
                session_schedule_tag="regular",
            )
        )
    return bars


@dataclass
class _FakeDS:
    bars: dict[str, list[OHLCVBar]]

    @property
    def dataset_version(self) -> str:
        return "021-test"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars.keys())

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        return []

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [b for b in self.bars.get(symbol, []) if date_start <= b.session_date <= date_end]

    def close(self) -> None:
        pass


def test_sc06_replay_ranking_filter(tmp_path):
    """Replay with ranking_filter: bottom-ranked symbol should have fewer orders."""
    start = date(2024, 1, 2)
    n_sessions = 15
    slist = _sessions(start, n_sessions)
    # WIN: consistently rising (strong momentum)
    winner_prices = [100.0 + i * 2 for i in range(n_sessions)]
    # LOSE: consistently falling (weak momentum)
    loser_prices = [100.0 - i * 1 for i in range(n_sessions)]

    winner_bars = _make_ohlcv("WIN", slist, winner_prices)
    loser_bars = _make_ohlcv("LOSE", slist, loser_prices)

    rf = RankingFilter(universe=("WIN", "LOSE"), period=2, top_n=1)

    win_rule = TradingRule(
        id="rule-win",
        symbol="WIN",
        stage=StrategyStage.FULL_LIVE,
        priority=1,
        trigger=TimeTrigger(kind="time", at_time="21:00", cooldown_seconds=0),
        action=Action(
            side=Side.BUY, order_type=OrderType.LIMIT, qty=1, limit_price="last_close * 1.0"
        ),
        ranking_filter=rf,
    )
    lose_rule = TradingRule(
        id="rule-lose",
        symbol="LOSE",
        stage=StrategyStage.FULL_LIVE,
        priority=1,
        trigger=TimeTrigger(kind="time", at_time="21:00", cooldown_seconds=0),
        action=Action(
            side=Side.BUY, order_type=OrderType.LIMIT, qty=1, limit_price="last_close * 1.0"
        ),
        ranking_filter=rf,
    )

    ds = _FakeDS({"WIN": winner_bars, "LOSE": loser_bars})
    conn = _open_db(tmp_path / "bt.sqlite3")
    clock = ReplayClock(datetime(2024, 1, 2, tzinfo=UTC))

    result = replay(
        conn=conn,
        rules=[win_rule, lose_rule],
        data_source=ds,
        date_start=slist[3],   # after period+1 bars are available
        date_end=slist[-1],
        whitelist=Whitelist(
            symbols=frozenset(["WIN", "LOSE"]),
            accounts=frozenset({"BACKTEST"}),
            order_types=frozenset({OrderType.LIMIT}),
            sessions=frozenset({"REGULAR"}),
        ),
        caps=_make_caps(),
        halt_path=tmp_path / "halt",
        clock=clock,
        broker=BacktestBroker(),
        run_id="bt-021-sc06",
    )

    win_orders = len(result.per_rule_orders.get("rule-win", []))
    lose_orders = len(result.per_rule_orders.get("rule-lose", []))

    assert lose_orders < win_orders, (
        f"Expected LOSE orders ({lose_orders}) < WIN orders ({win_orders})"
    )


# =========================================================================== #
# RankingFilter validation                                                     #
# =========================================================================== #


def test_ranking_filter_requires_exactly_one_selector():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        RankingFilter(universe=("A", "B"), period=1)  # neither top_n nor top_pct

    with pytest.raises(pydantic.ValidationError):
        RankingFilter(universe=("A", "B"), period=1, top_n=1, top_pct=50.0)  # both


def test_ranking_filter_universe_min_size():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        RankingFilter(universe=("A",), period=1, top_n=1)  # only 1 symbol
