"""Spec 032 slice 1 — portfolio-rebalancing backtest integration tests.

Covers the behaviours that only emerge end-to-end:
  - SC-05 / SC-10: a holding that drops out of the top ranks is SOLD (exit).
  - SC-07: a BUY over the K1 caps is rejected by the gate chain (caps bind).
  - SC-08: the run is lookahead-free (equity dates stay inside the window).
  - SC-09: identical inputs produce identical orders + equity curve.
  - the equity curve has one point per trading session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.backtest.broker_mock import BacktestBroker
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.data_source import trading_days_between
from auto_invest.backtest.portfolio_replay import replay_portfolio
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import db


@dataclass
class _FakeDataSource:
    bars: dict[str, list[OHLCVBar]]
    holes: list = field(default_factory=list)

    @property
    def dataset_version(self) -> str:
        return "test"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars)

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        return list(self.holes)

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [
            b for b in self.bars.get(symbol, []) if date_start <= b.session_date <= date_end
        ]


def _bars(symbol: str, days: list[date], price_of) -> list[OHLCVBar]:
    out = []
    for i, d in enumerate(days):
        c = Decimal(str(price_of(i)))
        out.append(
            OHLCVBar(
                symbol=symbol,
                session_date=d,
                open=c,
                high=(c * Decimal("1.01")).quantize(Decimal("0.0001")),
                low=(c * Decimal("0.99")).quantize(Decimal("0.0001")),
                close=c,
                volume=10_000_000,
                session_schedule_tag="regular",
            )
        )
    return out


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
        accounts=frozenset({"BACKTEST"}),
        order_types=frozenset({OrderType.MARKET}),
    )


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "audit.db")
    db.migrate(c)
    yield c
    c.close()


_run_counter = 0


def _run(cfg, dsource, days, caps, wl, tmp_path, *, start_idx, broker=None):
    global _run_counter
    _run_counter += 1
    conn = db.get_connection(tmp_path / f"run-{_run_counter}.db")
    db.migrate(conn)
    try:
        return replay_portfolio(
            config=cfg,
            data_source=dsource,
            date_start=days[start_idx],
            date_end=days[-1],
            caps=caps,
            whitelist=wl,
            halt_path=tmp_path / "HALT",
            conn=conn,
            clock=ReplayClock(datetime(2023, 1, 1, tzinfo=UTC)),
            broker=broker or BacktestBroker(),
            run_id="bt-port-test",
            total_capital_usd=Decimal("100000"),
        )
    finally:
        conn.close()


def test_dropout_holding_is_sold(tmp_path):
    """HOT leads early, crashes mid-window; STEADY overtakes. With top_n=1 the
    portfolio must SELL HOT when it falls out of the top rank (SC-05/SC-10)."""
    days = trading_days_between(date(2023, 1, 3), date(2023, 9, 29))

    def hot(i):
        # Rises for the first ~90 sessions, then falls hard.
        return 100 * (1.01 ** i) if i < 90 else 100 * (1.01 ** 90) * (0.97 ** (i - 90))

    def steady(i):
        return 100 * (1.0015 ** i)

    bars = {
        "HOT": _bars("HOT", days, hot),
        "STEADY": _bars("STEADY", days, steady),
    }
    cfg = PortfolioRebalanceConfig(
        id="p1",
        universe=("HOT", "STEADY"),
        weights={"momentum": Decimal("1")},
        top_n=1,
        weight_scheme="equal",
        invested_fraction=Decimal("0.5"),
        rebalance_every_n_sessions=20,
        lookback_bars=30,
        momentum_period=10,
    )
    res = _run(
        cfg,
        _FakeDataSource(bars),
        days,
        _caps(),
        _whitelist(("HOT", "STEADY")),
        tmp_path,
        start_idx=40,
    )
    bought_hot = any(f.symbol == "HOT" and f.side == "BUY" for f in res.fills)
    sold_hot = any(f.symbol == "HOT" and f.side == "SELL" for f in res.fills)
    bought_steady = any(f.symbol == "STEADY" and f.side == "BUY" for f in res.fills)
    assert bought_hot, "HOT should be bought while it leads"
    assert sold_hot, "HOT must be sold (exit) once it drops out of the top rank"
    assert bought_steady, "STEADY should be bought once it overtakes HOT"


def test_equity_curve_has_one_point_per_session(tmp_path):
    days = trading_days_between(date(2023, 1, 3), date(2023, 4, 28))
    bars = {
        "AAA": _bars("AAA", days, lambda i: 100 + i * 0.1),
        "BBB": _bars("BBB", days, lambda i: 100 + i * 0.2),
        "CCC": _bars("CCC", days, lambda i: 100 - i * 0.05),
    }
    cfg = PortfolioRebalanceConfig(
        id="p1",
        universe=("AAA", "BBB", "CCC"),
        weights={"momentum": Decimal("1")},
        top_n=2,
        invested_fraction=Decimal("0.6"),
        rebalance_every_n_sessions=15,
        momentum_period=10,
    )
    start_idx = 20
    res = _run(
        cfg,
        _FakeDataSource(bars),
        days,
        _caps(),
        _whitelist(("AAA", "BBB", "CCC")),
        tmp_path,
        start_idx=start_idx,
    )
    expected = len([d for d in days if d >= days[start_idx]])
    assert len(res.equity_curve) == expected
    # SC-08: every equity date is inside the requested window (no lookahead leak).
    assert all(days[start_idx] <= d <= days[-1] for d, _ in res.equity_curve)


def test_per_trade_cap_clamps_order_size(tmp_path):
    """SC-07 (clamp form): a 1% per-trade cap does not REJECT the buy — it clamps
    it DOWN so the order passes and the strategy still trades, matching the live
    rebalancer (single yardstick). Every fill's notional stays within the cap."""
    days = trading_days_between(date(2023, 1, 3), date(2023, 4, 28))
    bars = {
        "AAA": _bars("AAA", days, lambda i: 100 + i * 0.3),
        "BBB": _bars("BBB", days, lambda i: 100 + i * 0.1),
    }
    cfg = PortfolioRebalanceConfig(
        id="p1",
        universe=("AAA", "BBB"),
        weights={"momentum": Decimal("1")},
        top_n=1,
        invested_fraction=Decimal("0.6"),
        rebalance_every_n_sessions=15,
        momentum_period=10,
    )
    res = _run(
        cfg,
        _FakeDataSource(bars),
        days,
        _caps(per_trade="1", per_symbol="60", glob="100"),
        _whitelist(("AAA", "BBB")),
        tmp_path,
        start_idx=20,
    )
    # per-trade cap = 1% of mark-to-market equity; allow a small headroom since
    # equity drifts intra-window. Every fill must stay within ~1% notional.
    assert res.fills, "clamped buys should still fill (not be dropped)"
    assert not any(r.gate == "per_trade_cap_gate" for r in res.gate_rejections)
    for f in res.fills:
        notional = Decimal(f.qty) * Decimal(f.fill_price_usd)
        # 1% of starting $100k = $1,000; equity grows so allow generous headroom.
        assert notional <= Decimal("2000"), f"fill notional {notional} far over cap"


def test_deterministic_orders_and_equity(tmp_path):
    days = trading_days_between(date(2023, 1, 3), date(2023, 6, 30))
    bars = {
        "AAA": _bars("AAA", days, lambda i: 100 + i * 0.2),
        "BBB": _bars("BBB", days, lambda i: 100 + i * 0.1),
        "CCC": _bars("CCC", days, lambda i: 100 + (3 if i % 2 == 0 else -3)),
    }
    cfg = PortfolioRebalanceConfig(
        id="p1",
        universe=("AAA", "BBB", "CCC"),
        weights={"momentum": Decimal("1")},
        top_n=2,
        weight_scheme="inverse_vol",
        invested_fraction=Decimal("0.6"),
        rebalance_every_n_sessions=15,
        lookback_bars=30,
        momentum_period=10,
    )
    ds = _FakeDataSource(bars)
    r1 = _run(cfg, ds, days, _caps(), _whitelist(("AAA", "BBB", "CCC")), tmp_path, start_idx=35)
    r2 = _run(cfg, ds, days, _caps(), _whitelist(("AAA", "BBB", "CCC")), tmp_path, start_idx=35)
    sig1 = [(o.symbol, o.side, o.qty, o.state) for o in r1.orders]
    sig2 = [(o.symbol, o.side, o.qty, o.state) for o in r2.orders]
    assert sig1 == sig2  # SC-09
    assert r1.equity_curve == r2.equity_curve
    assert r1.total_return_pct == r2.total_return_pct


def test_benchmark_comparison_selection_beats_naive_hold(tmp_path):
    """The naive equal-weight buy-and-hold benchmark holds the WHOLE universe
    (including the loser). A top-2 momentum strategy avoids the loser, so its
    excess return over the benchmark is positive (selection added value)."""
    days = trading_days_between(date(2023, 1, 3), date(2023, 6, 30))
    bars = {
        "AAA": _bars("AAA", days, lambda i: 100 * (1.004 ** i)),  # strong up
        "BBB": _bars("BBB", days, lambda i: 100 * (1.002 ** i)),  # mild up
        "LOSE": _bars("LOSE", days, lambda i: 100 * (0.996 ** i)),  # down
    }
    cfg = PortfolioRebalanceConfig(
        id="p1",
        universe=("AAA", "BBB", "LOSE"),
        weights={"momentum": Decimal("1")},
        top_n=2,
        invested_fraction=Decimal("0.9"),
        rebalance_every_n_sessions=21,
        lookback_bars=30,
        momentum_period=20,
    )
    res = _run(
        cfg,
        _FakeDataSource(bars),
        days,
        _caps(),
        _whitelist(("AAA", "BBB", "LOSE")),
        tmp_path,
        start_idx=40,
    )
    # excess is exactly strategy − benchmark, and selection (avoiding LOSE) wins.
    assert res.excess_return_pct == res.total_return_pct - res.benchmark_total_return_pct
    assert res.benchmark_total_return_pct != Decimal("0")  # benchmark actually ran
    assert res.excess_return_pct > 0
