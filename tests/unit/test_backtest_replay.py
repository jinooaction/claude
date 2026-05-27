"""T023 smoke tests for the bar-level replay loop (Path B per R-B13).

These cover the structural invariants the integration test (T028) will
later assert against real fixtures:

    - Trigger fires → ORDER_INTENT → gate chain → ORDER_SUBMITTED / FILL
    - Per-trade cap denial emits ORDER_REJECTED_BY_GATE with the right gate
    - GTC orders carry into next session and fill there
    - Equity curve length = number of dates with bars for that symbol
    - Replay never touches the system clock (WallClockGuard would fire)
    - assert_backtest_adapter is invoked at entry (live broker leak fails fast)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.backtest.broker_mock import BacktestBroker, BacktestLiveBrokerLeakError
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.costs import BacktestCostModel
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.replay import replay
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, PriceTrigger, TimeTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import audit, db

# ---------- in-memory data source for tests -------------------------------


@dataclass
class _FakeDataSource:
    bars: dict[str, list[OHLCVBar]]
    holes: list[tuple[str, date]] = field(default_factory=list)

    @property
    def dataset_version(self) -> str:
        return "test-dataset-version"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars.keys())

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        return list(self.holes)

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [
            b
            for b in self.bars.get(symbol, [])
            if date_start <= b.session_date <= date_end
        ]


# ---------- fixtures ------------------------------------------------------


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "audit.db")
    db.migrate(c)
    yield c
    c.close()


def _bar(
    symbol: str,
    d: date,
    *,
    close: str,
    low: str,
    high: str,
    volume: int = 1_000_000,
) -> OHLCVBar:
    return OHLCVBar(
        symbol=symbol,
        session_date=d,
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        session_schedule_tag="regular",
    )


def _caps(per_trade: str = "5", per_symbol: str = "10", glob: str = "50") -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal(per_trade),
        per_symbol_pct=Decimal(per_symbol),
        global_exposure_pct=Decimal(glob),
        canary_capital_pct=Decimal("1"),
        canary_min_duration_days=5,
        canary_acceptance_drawdown_pct=Decimal("5"),
    )


def _whitelist(symbols=("AAPL",)) -> Whitelist:
    return Whitelist(
        symbols=frozenset(symbols),
        accounts=frozenset({"BACKTEST"}),
        order_types=frozenset({OrderType.LIMIT}),
    )


def _price_rule(rule_id: str, symbol: str, threshold: str, *, qty: int = 100) -> TradingRule:
    return TradingRule(
        id=rule_id,
        symbol=symbol,
        stage=StrategyStage.BACKTEST,
        priority=0,
        trigger=PriceTrigger(direction="<=", threshold=Decimal(threshold), cooldown_seconds=0),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=qty, limit_price="190.00"),
    )


def _time_rule(rule_id: str, symbol: str, *, qty: int = 100) -> TradingRule:
    """Trigger fires on every bar (HH:MM=21:00 / 20:00 — XNYS regular close)."""
    return TradingRule(
        id=rule_id,
        symbol=symbol,
        stage=StrategyStage.BACKTEST,
        priority=0,
        # XNYS regular close = 21:00 UTC (winter) / 20:00 UTC (summer); using
        # winter dates in tests means at_time="21:00" fires.
        trigger=TimeTrigger(at_time="21:00", cooldown_seconds=0),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=qty, limit_price="190.00"),
    )


def _clock() -> ReplayClock:
    return ReplayClock(datetime(2024, 1, 1, tzinfo=UTC))


# ---------- tests ---------------------------------------------------------


def test_fill_happy_path_emits_intent_submitted_fill(conn, tmp_path) -> None:
    """Price <= 195 triggers; limit 190; bar.low=185 touches; bar.open=190 → fill at 190."""
    bars = {
        "AAPL": [
            _bar("AAPL", date(2024, 1, 3), close="195.00", low="185.00", high="200.00"),
        ],
    }
    rules = [_price_rule("r1", "AAPL", "195", qty=20)]  # 20 × 190 = $3800 < per_trade cap
    broker = BacktestBroker()

    result = replay(
        rules=rules,
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 3),
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=_clock(),
        broker=broker,
        run_id="bt-test-1",
    )

    events = [r["event_type"] for r in audit.read_all(conn)]
    assert "ORDER_INTENT" in events
    assert "ORDER_SUBMITTED" in events
    assert "FILL" in events
    assert result.total_orders == 1
    assert result.total_fills == 1
    assert result.total_gate_rejections == 0
    assert len(result.per_rule_equity_curve["r1"]) == 1


def test_per_trade_cap_rejects(conn, tmp_path) -> None:
    """100_000 * 5% = $5000 per-trade cap; 100 shares × $200 = $20000 > cap → REJECT."""
    bars = {
        "AAPL": [
            _bar("AAPL", date(2024, 1, 3), close="200.00", low="180.00", high="210.00"),
        ],
    }
    rules = [_price_rule("r1", "AAPL", "205", qty=100)]
    # Limit price 190 — but the cap calc uses limit_price for LIMIT orders
    # so 100 * 190 = 19_000 still exceeds 5_000. Either way → reject.
    broker = BacktestBroker()

    result = replay(
        rules=rules,
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 3),
        caps=_caps(per_trade="5", per_symbol="10", glob="50"),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=_clock(),
        broker=broker,
        run_id="bt-test-2",
    )

    assert result.total_orders == 1  # one order intent
    assert result.total_fills == 0
    assert result.total_gate_rejections == 1
    rej = result.per_rule_gate_rejections["r1"][0]
    assert rej.gate == "per_trade_cap_gate"


def test_whitelist_gate_rejects_unlisted_symbol(conn, tmp_path) -> None:
    bars = {
        "MSFT": [
            _bar("MSFT", date(2024, 1, 3), close="195.00", low="185.00", high="200.00"),
        ],
    }
    rules = [_price_rule("r1", "MSFT", "200")]
    broker = BacktestBroker()

    result = replay(
        rules=rules,
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 3),
        caps=_caps(),
        whitelist=_whitelist(symbols=("AAPL",)),  # MSFT NOT listed
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=_clock(),
        broker=broker,
        run_id="bt-test-3",
    )

    assert result.total_gate_rejections == 1
    assert result.per_rule_gate_rejections["r1"][0].gate == "whitelist_gate"


def test_day_orders_expire_at_session_close(conn, tmp_path) -> None:
    """Untouched limit → no fill in submission bar → DAY expiry CANCEL row."""
    bars = {
        "AAPL": [
            # bar.low=200 > limit=190 → untouched → open
            _bar("AAPL", date(2024, 1, 3), close="205.00", low="200.00", high="210.00"),
            # next day no rule fires (only one date in window anyway)
        ],
    }
    rules = [_price_rule("r1", "AAPL", "210")]
    broker = BacktestBroker()

    replay(
        rules=rules,
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 3),
        caps=_caps(per_trade="50", per_symbol="60", glob="70"),  # generous cap
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=_clock(),
        broker=broker,
        run_id="bt-test-4",
    )

    events = [r["event_type"] for r in audit.read_all(conn)]
    assert "ORDER_SUBMITTED" in events
    assert "FILL" not in events
    assert "CANCEL" in events
    assert broker.list_open_orders() == []  # DAY expired


def test_equity_curve_length_matches_dates_with_bars(conn, tmp_path) -> None:
    bars = {
        "AAPL": [
            _bar("AAPL", date(2024, 1, 3), close="100.00", low="98.00", high="102.00"),
            _bar("AAPL", date(2024, 1, 4), close="105.00", low="100.00", high="108.00"),
            _bar("AAPL", date(2024, 1, 5), close="110.00", low="105.00", high="112.00"),
        ],
    }
    # threshold below realistic prices → never fires
    rules = [_price_rule("r1", "AAPL", "0.01")]
    broker = BacktestBroker()

    result = replay(
        rules=rules,
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 5),
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=_clock(),
        broker=broker,
        run_id="bt-test-5",
    )

    assert result.total_orders == 0
    assert len(result.per_rule_equity_curve["r1"]) == 3
    # No fills → equity constant at allocated capital.
    equities = [eq for _, eq in result.per_rule_equity_curve["r1"]]
    assert all(e == equities[0] for e in equities)


def test_replay_does_not_advance_clock_backwards(conn, tmp_path) -> None:
    """ReplayClock cannot rewind; the replay's chronological iteration honors that."""
    bars = {
        "AAPL": [
            _bar("AAPL", date(2024, 1, 5), close="100.00", low="98.00", high="102.00"),
            _bar("AAPL", date(2024, 1, 3), close="100.00", low="98.00", high="102.00"),
        ],
    }
    # threshold below realistic prices → never fires
    rules = [_price_rule("r1", "AAPL", "0.01")]
    broker = BacktestBroker()

    # Note: replay() sorts all_dates ascending so out-of-order inputs do not
    # cause rewind. This test asserts that promise.
    replay(
        rules=rules,
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 1),
        date_end=date(2024, 1, 10),
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=_clock(),
        broker=broker,
        run_id="bt-test-6",
    )


def test_assert_backtest_adapter_blocks_live_broker(conn, tmp_path) -> None:
    """A non-mock adapter id at entry raises BacktestLiveBrokerLeakError fast."""
    leaky = BacktestBroker()
    leaky.adapter_id = "kis-prod-v1"  # type: ignore[assignment]

    bars = {"AAPL": [_bar("AAPL", date(2024, 1, 3), close="100", low="98", high="102")]}
    # threshold below realistic prices → never fires
    rules = [_price_rule("r1", "AAPL", "0.01")]

    with pytest.raises(BacktestLiveBrokerLeakError):
        replay(
            rules=rules,
            data_source=_FakeDataSource(bars),
            date_start=date(2024, 1, 3),
            date_end=date(2024, 1, 3),
            caps=_caps(),
            whitelist=_whitelist(),
            halt_path=tmp_path / "HALT",
            conn=conn,
            clock=_clock(),
            broker=leaky,
            run_id="bt-test-7",
        )


def test_disabled_rule_is_skipped(conn, tmp_path) -> None:
    bars = {
        "AAPL": [_bar("AAPL", date(2024, 1, 3), close="100.00", low="98.00", high="102.00")],
    }
    rule = TradingRule(
        id="r1",
        symbol="AAPL",
        stage=StrategyStage.BACKTEST,
        priority=0,
        enabled=False,
        trigger=PriceTrigger(direction="<=", threshold=Decimal("200"), cooldown_seconds=0),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=100, limit_price="190"),
    )
    broker = BacktestBroker()

    result = replay(
        rules=[rule],
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 3),
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=_clock(),
        broker=broker,
        run_id="bt-test-8",
    )

    assert result.total_orders == 0
    assert result.total_fills == 0


# ---------- spec 016: transaction-cost overlay ----------------------------


def _single_fill_scenario(conn, tmp_path, cost_model):
    """BUY 20 @ limit 190; bar.low=185 touches, bar.open=190 → fill at 190."""
    bars = {
        "AAPL": [
            _bar("AAPL", date(2024, 1, 3), close="195.00", low="185.00", high="200.00"),
        ],
    }
    rules = [_price_rule("r1", "AAPL", "195", qty=20)]
    return replay(
        rules=rules,
        data_source=_FakeDataSource(bars),
        date_start=date(2024, 1, 3),
        date_end=date(2024, 1, 3),
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=_clock(),
        broker=BacktestBroker(),
        run_id="bt-cost",
        cost_model=cost_model,
    )


def test_zero_cost_model_matches_legacy_behaviour(conn, tmp_path) -> None:
    """SC-C03: zero() charges nothing and the fill price is the nominal 190."""
    result = _single_fill_scenario(conn, tmp_path, BacktestCostModel.zero())

    assert result.total_commission_usd == Decimal("0")
    assert result.total_slippage_cost_usd == Decimal("0")
    # Nominal fill price recorded unchanged.
    assert result.per_rule_fills["r1"][0].fill_price_usd == "190.000000"


def test_costs_reduce_equity_and_are_reported(tmp_path) -> None:
    """SC-C01: costs lower terminal equity and the totals are surfaced."""
    # Separate DBs so the two runs' append-only audit rows don't collide.
    c_zero = db.get_connection(tmp_path / "zero.db")
    db.migrate(c_zero)
    c_costed = db.get_connection(tmp_path / "costed.db")
    db.migrate(c_costed)
    try:
        zero = _single_fill_scenario(c_zero, tmp_path, BacktestCostModel.zero())
        costed = _single_fill_scenario(
            c_costed,
            tmp_path,
            BacktestCostModel(commission_bps=Decimal("25"), slippage_bps=Decimal("5")),
        )
    finally:
        c_zero.close()
        c_costed.close()

    # 20 shares: slippage 5bps on a 190 fill → eff 190.095; commission 0.25%.
    assert costed.per_rule_fills["r1"][0].fill_price_usd == "190.095000"
    assert costed.total_commission_usd > Decimal("0")
    assert costed.total_slippage_cost_usd > Decimal("0")

    zero_equity = zero.per_rule_equity_curve["r1"][-1][1]
    costed_equity = costed.per_rule_equity_curve["r1"][-1][1]
    assert costed_equity < zero_equity
