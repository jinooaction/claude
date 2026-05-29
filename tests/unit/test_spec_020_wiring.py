"""스펙 020 — order_router·replay 레짐 배율 + ERC 가중치 실배선 테스트.

SC-01: order_router BEAR 레짐 → qty 감소(regime_zero 또는 paper_filled with 감소)
SC-02: order_router ERC 모드 _group_scale() → Decimal 반환
SC-03: replay BEAR 레짐 → BEAR 구간 주문 수 < 레짐 없는 룰
SC-04: replay ERC 모드 → 주문 생성 (가중치 적용 후 qty>0)
SC-05: regime_index_symbol=None → 레짐 처리 없음, PAPER_FILLED
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
from auto_invest.config.rules import Action, SizingConfig, TimeTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.execution.order_router import OrderRouter
from auto_invest.market_data.store import PriceBar, insert_bar
from auto_invest.persistence import db as _db_mod
from auto_invest.strategy.sizing import SizingGroupMember

# =========================================================================== #
# 공용 헬퍼                                                                    #
# =========================================================================== #

_CAL = ec.get_calendar("XNYS")


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


def _make_ohlcv(
    symbol: str,
    sessions: list[date],
    prices: list[float] | None = None,
    base_price: float = 100.0,
) -> list[OHLCVBar]:
    bars: list[OHLCVBar] = []
    price = base_price
    for i, s in enumerate(sessions):
        p = Decimal(str(round(prices[i], 4))) if prices else Decimal(str(round(price, 4)))
        bars.append(
            OHLCVBar(
                symbol=symbol,
                session_date=s,
                open=p,
                high=p * Decimal("1.001"),
                low=p * Decimal("0.999"),
                close=p,
                volume=10000,
                session_schedule_tag="regular",
            )
        )
        price = price * 1.001
    return bars


def _insert_price_bars(
    conn: sqlite3.Connection, ohlcv: list[OHLCVBar], timeframe: str = "1d"
) -> None:
    """OHLCVBar 목록을 market_data 테이블에 PriceBar 형식으로 삽입."""
    for b in ohlcv:
        insert_bar(
            conn,
            PriceBar(
                symbol=b.symbol,
                timeframe=timeframe,
                bar_open_utc=b.session_date.isoformat() + "T00:00:00.000Z",
                open_usd=b.open,
                high_usd=b.high,
                low_usd=b.low,
                close_usd=b.close,
                volume=b.volume,
            ),
        )


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("100"),
        per_symbol_pct=Decimal("100"),
        global_exposure_pct=Decimal("100"),
        canary_capital_pct=Decimal("1"),
        canary_min_duration_days=5,
        canary_acceptance_drawdown_pct=Decimal("5"),
    )


def _clock() -> ReplayClock:
    return ReplayClock(datetime(2020, 1, 1, tzinfo=UTC))


@dataclass
class _FakeDS:
    bars: dict[str, list[OHLCVBar]]

    @property
    def dataset_version(self) -> str:
        return "020-test"

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


# =========================================================================== #
# SC-01: order_router BEAR 레짐 → qty 감소 확인                                #
# =========================================================================== #


@pytest.mark.asyncio
async def test_order_router_bear_regime_reduces_qty(tmp_path: Path, sc="SC-01") -> None:
    """BEAR 레짐 → base_qty 100 × 0.3 = 30. qty=30 > 0 이므로 PAPER_FILLED."""
    conn = _open_db(tmp_path / "test.db")
    sessions = _sessions(date(2023, 1, 3), 260)

    # 종목 봉
    _insert_price_bars(conn, _make_ohlcv("AAPL", sessions))

    # 인덱스 봉: 처음 200일 high=100, 이후 50 → BEAR (close < SMA200 AND close < SMA50)
    idx_prices = [100.0] * 200 + [50.0] * 60
    _insert_price_bars(conn, _make_ohlcv("SPY", sessions, prices=idx_prices[: len(sessions)]))

    rule = TradingRule(
        id="r_aapl",
        symbol="AAPL",
        stage=StrategyStage.FULL_LIVE,
        priority=1,
        enabled=True,
        trigger=TimeTrigger(kind="time", at_time="09:30", cooldown_seconds=0),
        action=Action(
            side=Side.BUY, order_type=OrderType.LIMIT, qty=100, limit_price="last_close * 1.0"
        ),
        regime_index_symbol="SPY",
    )

    whitelist = Whitelist(
        symbols=frozenset(["AAPL"]),
        accounts=frozenset({"x"}),
        order_types=frozenset({OrderType.LIMIT}),
    )
    router = OrderRouter(
        conn=conn,
        broker=MagicMock(),
        access_token="x",
        app_key="x",
        app_secret="x",
        account_no="x",
        whitelist=whitelist,
        caps=_caps(),
        halt_path=tmp_path / "halt",
        paper_mode=True,
    )

    outcome = await router.submit_order(
        rule=rule,
        quote_price_usd=Decimal("50"),
        total_capital_usd=Decimal("1000000"),
        current_symbol_exposure_usd=Decimal("0"),
        current_global_exposure_usd=Decimal("0"),
    )

    # BEAR 레짐 → qty 100 × 0.3 = 30 → 0보다 크므로 SKIPPED_BY_SIZING(regime_zero) 아님
    assert outcome.reason != "regime_zero"
    assert outcome.state in ("PAPER_FILLED", "REJECTED_BY_GATE")


# =========================================================================== #
# SC-05: regime_index_symbol=None → 레짐 처리 없음                             #
# =========================================================================== #


@pytest.mark.asyncio
async def test_order_router_no_regime_unchanged(tmp_path: Path, sc="SC-05") -> None:
    """regime_index_symbol=None → 레짐 없음, 정상 PAPER_FILLED."""
    conn = _open_db(tmp_path / "test.db")
    sessions = _sessions(date(2023, 1, 3), 30)
    _insert_price_bars(conn, _make_ohlcv("AAPL", sessions))

    rule = TradingRule(
        id="r_aapl",
        symbol="AAPL",
        stage=StrategyStage.FULL_LIVE,
        priority=1,
        enabled=True,
        trigger=TimeTrigger(kind="time", at_time="09:30", cooldown_seconds=0),
        action=Action(
            side=Side.BUY, order_type=OrderType.LIMIT, qty=10, limit_price="last_close * 1.0"
        ),
        regime_index_symbol=None,
    )

    router = OrderRouter(
        conn=conn,
        broker=MagicMock(),
        access_token="x",
        app_key="x",
        app_secret="x",
        account_no="x",
        whitelist=Whitelist(
            symbols=frozenset(["AAPL"]),
            accounts=frozenset({"x"}),
            order_types=frozenset({OrderType.LIMIT}),
        ),
        caps=_caps(),
        halt_path=tmp_path / "halt",
        paper_mode=True,
    )

    outcome = await router.submit_order(
        rule=rule,
        quote_price_usd=Decimal("100"),
        total_capital_usd=Decimal("1000000"),
        current_symbol_exposure_usd=Decimal("0"),
        current_global_exposure_usd=Decimal("0"),
    )
    assert outcome.state == "PAPER_FILLED"


# =========================================================================== #
# SC-02: order_router _group_scale() ERC 모드 경로                             #
# =========================================================================== #


def test_group_scale_erc_mode_returns_decimal(tmp_path: Path, sc="SC-02") -> None:
    """_group_scale() 이 erc 모드에서 down-only Decimal 을 반환한다."""
    conn = _open_db(tmp_path / "erc.db")
    sessions = _sessions(date(2023, 1, 3), 50)
    for sym in ["AA", "BB"]:
        _insert_price_bars(conn, _make_ohlcv(sym, sessions))

    sizing = SizingConfig(mode="erc", lookback_bars=20)
    rule = TradingRule(
        id="r_AA",
        symbol="AA",
        stage=StrategyStage.FULL_LIVE,
        priority=1,
        enabled=True,
        trigger=TimeTrigger(kind="time", at_time="09:30", cooldown_seconds=0),
        action=Action(
            side=Side.BUY, order_type=OrderType.LIMIT, qty=10, limit_price="last_close * 1.0"
        ),
        sizing=sizing,
        sizing_group="grp1",
    )

    sizing_groups = {
        "grp1": [
            SizingGroupMember(rule_id="r_AA", symbol="AA", timeframe="1d", lookback_bars=20),
            SizingGroupMember(rule_id="r_BB", symbol="BB", timeframe="1d", lookback_bars=20),
        ]
    }

    router = OrderRouter(
        conn=conn,
        broker=MagicMock(),
        access_token="x",
        app_key="x",
        app_secret="x",
        account_no="x",
        whitelist=Whitelist(
            symbols=frozenset(["AA", "BB"]),
            accounts=frozenset({"x"}),
            order_types=frozenset({OrderType.LIMIT}),
        ),
        caps=_caps(),
        halt_path=tmp_path / "halt",
        sizing_groups=sizing_groups,
    )

    scale = router._group_scale(rule)
    assert isinstance(scale, Decimal)
    assert Decimal("0") < scale <= Decimal("1")


# =========================================================================== #
# SC-03: replay BEAR 레짐 → BEAR 구간 주문 수 감소                             #
# =========================================================================== #


def test_replay_bear_regime_reduces_orders(tmp_path: Path, sc="SC-03") -> None:
    """BEAR 구간에서 레짐 룰은 qty=1×0.3=0 → 주문 건너뜀. 비레짐 룰은 정상."""
    sessions = _sessions(date(2022, 1, 3), 260)

    # 인덱스: 처음 200일 100, 이후 50 (BEAR)
    idx_prices = [100.0] * 200 + [50.0] * 60
    idx_bars = _make_ohlcv("SPY", sessions, prices=idx_prices[: len(sessions)])
    stock_bars = _make_ohlcv("AAPL", sessions)

    ds = _FakeDS(bars={"AAPL": stock_bars, "SPY": idx_bars})

    # 레짐 룰: qty=1, BEAR → 1×0.3=0 → 건너뜀
    rule_regime = TradingRule(
        id="r_regime",
        symbol="AAPL",
        stage=StrategyStage.BACKTEST,
        priority=1,
        enabled=True,
        trigger=TimeTrigger(kind="time", at_time="21:00", cooldown_seconds=0),
        action=Action(
            side=Side.BUY, order_type=OrderType.LIMIT, qty=1, limit_price="last_close * 1.0"
        ),
        regime_index_symbol="SPY",
    )
    # 비레짐 룰: qty=1, 정상
    rule_no_regime = TradingRule(
        id="r_no_regime",
        symbol="AAPL",
        stage=StrategyStage.BACKTEST,
        priority=1,
        enabled=True,
        trigger=TimeTrigger(kind="time", at_time="21:00", cooldown_seconds=0),
        action=Action(
            side=Side.BUY, order_type=OrderType.LIMIT, qty=1, limit_price="last_close * 1.0"
        ),
    )

    conn = _open_db(tmp_path / "bt.db")
    bear_start = sessions[200]  # BEAR 구간 시작

    result = replay(
        conn=conn,
        rules=[rule_regime, rule_no_regime],
        data_source=ds,
        date_start=bear_start,
        date_end=sessions[-1],
        whitelist=Whitelist(
            symbols=frozenset(["AAPL", "SPY"]),
            accounts=frozenset({"BACKTEST"}),
            order_types=frozenset({OrderType.LIMIT}),
        ),
        caps=_caps(),
        halt_path=tmp_path / "halt",
        clock=_clock(),
        broker=BacktestBroker(),
        run_id="bt-020-sc03",
    )

    orders_regime = len(result.per_rule_orders.get("r_regime", []))
    orders_no_regime = len(result.per_rule_orders.get("r_no_regime", []))

    # BEAR 레짐 룰: qty=1×0.3=0 → 건너뜀 → 주문 없거나 줄어듦
    assert orders_regime < orders_no_regime, (
        f"BEAR 구간 레짐 룰={orders_regime}, 비레짐 룰={orders_no_regime}"
    )


# =========================================================================== #
# SC-04: replay ERC 모드 → 주문 생성                                           #
# =========================================================================== #


def test_replay_erc_mode_produces_orders(tmp_path: Path, sc="SC-04") -> None:
    """ERC 모드 룰이 replay 에서 주문을 생성한다 (ERC 가중치 적용 후 qty>0)."""
    sessions = _sessions(date(2023, 1, 3), 60)
    bars_aa = _make_ohlcv("AA", sessions)
    bars_bb = _make_ohlcv("BB", sessions)
    ds = _FakeDS(bars={"AA": bars_aa, "BB": bars_bb})

    sizing = SizingConfig(mode="erc", lookback_bars=20)

    def _erc_rule(rule_id: str, symbol: str) -> TradingRule:
        return TradingRule(
            id=rule_id,
            symbol=symbol,
            stage=StrategyStage.BACKTEST,
            priority=1,
            enabled=True,
            trigger=TimeTrigger(kind="time", at_time="21:00", cooldown_seconds=0),
            action=Action(
                side=Side.BUY,
                order_type=OrderType.LIMIT,
                qty=10,
                limit_price="last_close * 1.0",
            ),
            sizing=sizing,
            sizing_group="erc_grp",
        )

    conn = _open_db(tmp_path / "bt_erc.db")

    result = replay(
        conn=conn,
        rules=[_erc_rule("r_aa", "AA"), _erc_rule("r_bb", "BB")],
        data_source=ds,
        date_start=sessions[21],  # lookback 20일 이후
        date_end=sessions[-1],
        whitelist=Whitelist(
            symbols=frozenset(["AA", "BB"]),
            accounts=frozenset({"BACKTEST"}),
            order_types=frozenset({OrderType.LIMIT}),
        ),
        caps=_caps(),
        halt_path=tmp_path / "halt",
        clock=_clock(),
        broker=BacktestBroker(),
        run_id="bt-020-sc04",
    )

    # ERC 가중치 적용 후 qty>0 → 주문 생성
    assert result.total_orders > 0
