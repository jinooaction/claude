"""Spec 017 — volatility-aware position sizing (slices 1 + 2).

Two layers:
  * Pure unit tests for strategy/sizing.py (deterministic Decimal helpers).
  * Replay integration: a target_vol rule throttles qty below the declared base
    during a volatile window (slice 1, down-only); with max_scale>1 it sizes
    above the base during a calm window (slice 2, bidirectional targeting) yet
    the K1 caps still reject anything over the ceiling; fixed/None sizing and the
    default max_scale=1 stay byte-equal to v1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import exchange_calendars as ec
import pytest

from auto_invest.backtest.broker_mock import BacktestBroker
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.replay import replay
from auto_invest.backtest.walk_forward import render_walk_forward_report, run_walk_forward
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, SizingConfig, TimeTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import db
from auto_invest.strategy.sizing import (
    realized_volatility,
    sized_quantity,
    volatility_scale,
)

# --------------------------------------------------------------------------- #
# Pure helpers                                                                #
# --------------------------------------------------------------------------- #


def _d(values: list[str]) -> list[Decimal]:
    return [Decimal(v) for v in values]


def test_realized_volatility_needs_at_least_two_returns() -> None:
    assert realized_volatility([]) is None
    assert realized_volatility(_d(["100"])) is None
    assert realized_volatility(_d(["100", "101"])) is None  # only 1 return
    assert realized_volatility(_d(["100", "101", "102"])) is not None  # 2 returns


def test_realized_volatility_constant_growth_is_zero() -> None:
    # Constant +10% per bar → identical returns → zero dispersion.
    closes = _d(["100", "110", "121", "133.1", "146.41"])
    assert realized_volatility(closes) == Decimal("0")


def test_realized_volatility_nonpositive_close_is_none() -> None:
    assert realized_volatility(_d(["100", "0", "100"])) is None
    assert realized_volatility(_d(["100", "-5", "100"])) is None


def test_realized_volatility_positive_for_dispersed_returns() -> None:
    rv = realized_volatility(_d(["100", "110", "100", "110", "100"]))
    assert rv is not None
    assert rv > Decimal("0")


def test_volatility_scale_clamps_to_one_when_calm() -> None:
    # realized below target → would scale up, but slice 1 is down-only.
    assert volatility_scale(Decimal("0.01"), Decimal("0.02")) == Decimal("1")


def test_volatility_scale_shrinks_when_turbulent() -> None:
    # target 2% / realized 10% = 0.2.
    assert volatility_scale(Decimal("0.10"), Decimal("0.02")) == Decimal("0.2")


def test_volatility_scale_zero_realized_is_one() -> None:
    assert volatility_scale(Decimal("0"), Decimal("0.02")) == Decimal("1")
    assert volatility_scale(Decimal("-1"), Decimal("0.02")) == Decimal("1")


def test_volatility_scale_respects_min_scale_floor() -> None:
    # raw = 0.02/0.10 = 0.2, but min_scale floors it to 0.5.
    assert volatility_scale(
        Decimal("0.10"), Decimal("0.02"), min_scale=Decimal("0.5")
    ) == Decimal("0.5")


def test_volatility_scale_default_max_is_down_only() -> None:
    # Slice 1 invariant: without max_scale the factor never exceeds 1, even when
    # realized (1%) is well below target (2%) so target/realized = 2.0.
    assert volatility_scale(Decimal("0.01"), Decimal("0.02")) == Decimal("1")


def test_volatility_scale_amplifies_when_calm_and_bidirectional() -> None:
    # Slice 2: realized 1% / target 2% → raw 2.0, allowed up to max_scale 3.
    assert volatility_scale(
        Decimal("0.01"), Decimal("0.02"), max_scale=Decimal("3")
    ) == Decimal("2")


def test_volatility_scale_caps_upscale_at_max_scale() -> None:
    # raw = 0.04/0.01 = 4, but max_scale ceilings it to 2.
    assert volatility_scale(
        Decimal("0.01"), Decimal("0.04"), max_scale=Decimal("2")
    ) == Decimal("2")


def test_volatility_scale_zero_realized_is_neutral_even_bidirectional() -> None:
    # No reliable measurement → neutral 1, never an unbounded upscale.
    assert volatility_scale(
        Decimal("0"), Decimal("0.02"), max_scale=Decimal("3")
    ) == Decimal("1")


def _sizing(**kw: object) -> SizingConfig:
    base: dict[str, object] = {
        "mode": "target_vol",
        "target_volatility_pct": Decimal("2.0"),
        "lookback_bars": 20,
    }
    base.update(kw)
    return SizingConfig(**base)  # type: ignore[arg-type]


def test_sized_quantity_none_and_fixed_return_base() -> None:
    closes = _d(["100", "110", "100", "110", "100"])
    assert sized_quantity(base_qty=50, closes=closes, sizing=None) == 50
    # mode="fixed" is the SizingConfig default.
    assert sized_quantity(base_qty=50, closes=closes, sizing=SizingConfig()) == 50


def test_sized_quantity_calm_market_keeps_base() -> None:
    # Constant growth → realized 0 → scale 1 → unchanged (down-only invariant).
    closes = _d(["100", "110", "121", "133.1", "146.41"])
    assert sized_quantity(base_qty=50, closes=closes, sizing=_sizing()) == 50


def test_sized_quantity_throttles_when_turbulent() -> None:
    closes = _d(["100", "110", "100", "110", "100", "112", "98"])
    sized = sized_quantity(base_qty=100, closes=closes, sizing=_sizing(lookback_bars=6))
    assert 0 <= sized < 100  # turbulence shrinks the position


def test_sized_quantity_never_exceeds_base() -> None:
    # Even a tiny target can never size *up* (slice 1 down-only).
    closes = _d(["100", "100.5", "100", "100.5", "100"])
    sizing = _sizing(target_volatility_pct=Decimal("0.01"), lookback_bars=4)
    assert sized_quantity(base_qty=10, closes=closes, sizing=sizing) <= 10


def test_sized_quantity_default_max_keeps_base_in_calm_market() -> None:
    # Calm market (low realized vol) + default max_scale=1 → stays at base.
    closes = _d(["100", "100.5", "100", "100.5", "100"])
    sizing = _sizing(target_volatility_pct=Decimal("2.0"), lookback_bars=4)
    assert sized_quantity(base_qty=10, closes=closes, sizing=sizing) == 10


def test_sized_quantity_bidirectional_scales_up_in_calm_market() -> None:
    # Slice 2: calm market + max_scale 3 sizes the position ABOVE the base.
    closes = _d(["100", "100.5", "100", "100.5", "100"])
    sizing = _sizing(
        target_volatility_pct=Decimal("2.0"), lookback_bars=4, max_scale=Decimal("3")
    )
    sized = sized_quantity(base_qty=10, closes=closes, sizing=sizing)
    assert sized > 10  # bidirectional targeting grew the position
    assert sized <= 30  # never above base * max_scale


def test_sized_quantity_bidirectional_still_throttles_when_turbulent() -> None:
    # max_scale>1 does not disable the down-side: turbulence still shrinks.
    closes = _d(["100", "110", "100", "110", "100", "112", "98"])
    sizing = _sizing(
        target_volatility_pct=Decimal("1.0"), lookback_bars=6, max_scale=Decimal("3")
    )
    assert sized_quantity(base_qty=100, closes=closes, sizing=sizing) < 100


def test_sized_quantity_failsafe_insufficient_data_returns_base() -> None:
    # Fewer than 3 closes in window → cannot measure → keep declared base.
    assert sized_quantity(base_qty=42, closes=_d(["100", "101"]), sizing=_sizing()) == 42


def test_sized_quantity_is_deterministic() -> None:
    closes = _d(["100", "110", "100", "110", "100", "112", "98", "105"])
    a = sized_quantity(base_qty=77, closes=closes, sizing=_sizing(lookback_bars=7))
    b = sized_quantity(base_qty=77, closes=closes, sizing=_sizing(lookback_bars=7))
    assert a == b


def test_sized_quantity_floors_via_helpers() -> None:
    # sized_quantity must equal floor(base * scale) computed from the same window.
    closes = _d(["100", "110", "100", "110", "100", "112", "98"])
    sizing = _sizing(lookback_bars=6)
    window = closes[-(sizing.lookback_bars + 1) :]
    rv = realized_volatility(window)
    assert rv is not None
    target = sizing.target_volatility_pct / Decimal(100)
    scale = volatility_scale(rv, target, min_scale=sizing.min_scale)
    expected = int((Decimal(100) * scale).to_integral_value(rounding="ROUND_FLOOR"))
    assert sized_quantity(base_qty=100, closes=closes, sizing=sizing) == max(expected, 0)


# --------------------------------------------------------------------------- #
# Replay integration                                                          #
# --------------------------------------------------------------------------- #


@dataclass
class _FakeDataSource:
    bars: dict[str, list[OHLCVBar]]
    holes: list[tuple[str, date]] = field(default_factory=list)

    @property
    def dataset_version(self) -> str:
        return "test-sizing"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars.keys())

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        return list(self.holes)

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [b for b in self.bars.get(symbol, []) if date_start <= b.session_date <= date_end]


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "audit.db")
    db.migrate(c)
    yield c
    c.close()


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("20"),
        per_symbol_pct=Decimal("40"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("1"),
        canary_min_duration_days=5,
        canary_acceptance_drawdown_pct=Decimal("5"),
    )


def _whitelist() -> Whitelist:
    return Whitelist(
        symbols=frozenset({"AAPL"}),
        accounts=frozenset({"BACKTEST"}),
        order_types=frozenset({OrderType.LIMIT}),
    )


def _sessions(n: int) -> list[date]:
    cal = ec.get_calendar("XNYS")
    sess = cal.sessions_in_range("2024-01-02", "2024-02-29")
    return [d.date() for d in sess.to_pydatetime()][:n]


def _volatile_bars(symbol: str, sessions: list[date]) -> list[OHLCVBar]:
    """Alternating ~10% swings → high realized volatility. Lows touch the limit."""
    bars: list[OHLCVBar] = []
    for i, d in enumerate(sessions):
        close = Decimal("100") if i % 2 == 0 else Decimal("110")
        bars.append(
            OHLCVBar(
                symbol=symbol,
                session_date=d,
                open=close,
                high=close + Decimal("5"),
                low=Decimal("90"),  # <= limit 200 → BUY limit fills
                close=close,
                volume=1_000_000,
                session_schedule_tag="regular",
            )
        )
    return bars


def _calm_bars(symbol: str, sessions: list[date]) -> list[OHLCVBar]:
    """Tiny ~0.3% swings → low realized volatility (< target). Bidirectional
    targeting scales UP toward the target risk budget. Lows touch the limit."""
    bars: list[OHLCVBar] = []
    for i, d in enumerate(sessions):
        close = Decimal("100") if i % 2 == 0 else Decimal("100.3")
        bars.append(
            OHLCVBar(
                symbol=symbol,
                session_date=d,
                open=close,
                high=close + Decimal("0.5"),
                low=Decimal("99"),  # <= limit 200 → BUY limit fills
                close=close,
                volume=1_000_000,
                session_schedule_tag="regular",
            )
        )
    return bars


def _time_rule(rule_id: str, *, qty: int, sizing: SizingConfig | None) -> TradingRule:
    return TradingRule(
        id=rule_id,
        symbol="AAPL",
        stage=StrategyStage.BACKTEST,
        priority=0,
        trigger=TimeTrigger(at_time="21:00", cooldown_seconds=0),  # winter XNYS close
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=qty, limit_price="200.00"),
        sizing=sizing,
    )


def _run(conn, tmp_path, rule: TradingRule, *, bars_fn=_volatile_bars, n=25, caps=None):
    sessions = _sessions(n)
    bars = {"AAPL": bars_fn("AAPL", sessions)}
    return replay(
        rules=[rule],
        data_source=_FakeDataSource(bars),
        date_start=sessions[0],
        date_end=sessions[-1],
        caps=caps if caps is not None else _caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=ReplayClock(datetime(2024, 1, 1, tzinfo=UTC)),
        broker=BacktestBroker(),
        run_id=f"bt-sizing-{rule.id}",
    )


def test_replay_fixed_sizing_matches_none(conn, tmp_path) -> None:
    """SC-S03 — mode=fixed produces the same order quantities as sizing=None."""
    none_result = _run(conn, tmp_path, _time_rule("r_none", qty=30, sizing=None))
    fixed_result = _run(conn, tmp_path, _time_rule("r_fixed", qty=30, sizing=SizingConfig()))
    none_orders = none_result.per_rule_orders["r_none"]
    fixed_orders = fixed_result.per_rule_orders["r_fixed"]
    assert [o.qty for o in none_orders] == [o.qty for o in fixed_orders]
    assert all(o.qty == 30 for o in none_orders)
    assert len(none_orders) > 0


def test_replay_target_vol_throttles_below_base(conn, tmp_path) -> None:
    """SC-S01/SC-S02 — turbulent window shrinks qty, never above the declared base."""
    sizing = _sizing(target_volatility_pct=Decimal("1.0"), lookback_bars=20)
    rule = _time_rule("r_vol", qty=30, sizing=sizing)
    orders = _run(conn, tmp_path, rule).per_rule_orders["r_vol"]
    assert len(orders) > 0
    assert all(o.qty <= 30 for o in orders)  # down-only invariant
    assert any(o.qty < 30 for o in orders)  # at least one fire was throttled
    assert all(o.qty >= 1 for o in orders)  # qty=0 orders are never recorded


def test_replay_bidirectional_scales_up_in_calm_market(conn, tmp_path) -> None:
    """SC-S08 — a calm window with max_scale>1 sizes ABOVE the declared base
    (bidirectional targeting), while the default max_scale=1 rule stays at the
    base (down-only). Both flow through the same replay path."""
    bidi = _sizing(
        target_volatility_pct=Decimal("2.0"), lookback_bars=20, max_scale=Decimal("3")
    )
    down = _sizing(target_volatility_pct=Decimal("2.0"), lookback_bars=20)  # max 1
    bidi_orders = _run(
        conn, tmp_path, _time_rule("r_bidi", qty=10, sizing=bidi), bars_fn=_calm_bars
    ).per_rule_orders["r_bidi"]
    down_orders = _run(
        conn, tmp_path, _time_rule("r_down", qty=10, sizing=down), bars_fn=_calm_bars
    ).per_rule_orders["r_down"]
    assert any(o.qty > 10 for o in bidi_orders)  # calm market grew the position
    assert all(o.qty <= 30 for o in bidi_orders)  # capped at base * max_scale
    assert down_orders and all(o.qty == 10 for o in down_orders)  # default = down-only


def test_replay_bidirectional_upscale_still_bound_by_k1_caps(conn, tmp_path) -> None:
    """SC-S09 (slice-2 safety) — upscaling cannot breach K1: with a tight
    per-trade cap the enlarged order is REJECTED by the gate chain, while the
    down-only rule (same base) fills. K1 is the true ceiling."""
    tight = SizingCaps(
        per_trade_pct=Decimal("3"),  # 3% of $100k = $3,000 per-trade cap
        per_symbol_pct=Decimal("40"),
        global_exposure_pct=Decimal("80"),
        canary_capital_pct=Decimal("1"),
        canary_min_duration_days=5,
        canary_acceptance_drawdown_pct=Decimal("5"),
    )
    # Same calm data + same base 10, the only difference is max_scale.
    # limit 200, down-only qty 10: notional = $2,000 < $3,000 → always fills.
    # bidi qty 30 (once lookback fills): notional = $6,000 > $3,000 → rejected by K1.
    bidi = _sizing(
        target_volatility_pct=Decimal("2.0"), lookback_bars=20, max_scale=Decimal("3")
    )
    down = _sizing(target_volatility_pct=Decimal("2.0"), lookback_bars=20)
    bidi_res = _run(
        conn, tmp_path, _time_rule("r_bidi_cap", qty=10, sizing=bidi),
        bars_fn=_calm_bars, caps=tight,
    )
    down_res = _run(
        conn, tmp_path, _time_rule("r_down_cap", qty=10, sizing=down),
        bars_fn=_calm_bars, caps=tight,
    )
    # The upscaled orders are rejected by the per-trade cap gate — K1 binds.
    bidi_rejections = bidi_res.per_rule_gate_rejections.get("r_bidi_cap", [])
    assert bidi_rejections
    assert all(r.gate == "per_trade_cap_gate" for r in bidi_rejections)
    # The down-only rule never breaches the cap: it fills with no gate rejection.
    assert not down_res.per_rule_gate_rejections.get("r_down_cap")
    assert down_res.per_rule_orders.get("r_down_cap")


def test_walk_forward_runs_with_volatility_sizing(conn, tmp_path) -> None:
    """SC-S06 — a target_vol rule flows through run_walk_forward (sizing is
    validated out-of-sample via the same replay path), and a report renders."""
    sessions = _sessions(40)
    bars = {"AAPL": _volatile_bars("AAPL", sessions)}
    sizing = _sizing(target_volatility_pct=Decimal("1.0"), lookback_bars=20)
    report = run_walk_forward(
        rules=[_time_rule("r_vol", qty=30, sizing=sizing)],
        data_source=_FakeDataSource(bars),
        date_start=sessions[0],
        date_end=sessions[-1],
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        in_sample_days=20,
        out_of_sample_days=10,
    )
    assert report.windows
    md = render_walk_forward_report(report)
    assert "워크포워드" in md
