"""스펙 016 슬라이스 3 — 워크포워드(표본 외) 검증 하니스 테스트.

검증 대상:
  * 윈도우 생성(rolling/anchored, 연속 타일링, 경계, 너무 짧은 범위 오류)
  * 표본 외 요약이 일반 백테스트와 **같은 단일 잣대**를 쓴다(SC — 헌법 X.2)
  * WFE(OOS 샤프/IS 샤프)·과적합 판정 로직
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import exchange_calendars as ec
import pytest

from auto_invest.backtest.broker_mock import BacktestBroker
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.costs import BacktestCostModel
from auto_invest.backtest.data_model import BacktestSummary, OHLCVBar
from auto_invest.backtest.replay import replay
from auto_invest.backtest.report import build_per_rule_results, build_summary
from auto_invest.backtest.walk_forward import (
    WalkForwardError,
    WalkForwardWindow,
    WalkForwardWindowResult,
    _build_report,
    generate_windows,
    render_walk_forward_report,
    run_walk_forward,
)
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType, Side, StrategyStage
from auto_invest.config.rules import Action, TimeTrigger, TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import db

# ---------- fixtures / helpers --------------------------------------------


@dataclass
class _FakeDataSource:
    bars: dict[str, list[OHLCVBar]]

    @property
    def dataset_version(self) -> str:
        return "wf-test-dataset"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars.keys())

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        return []

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [
            b for b in self.bars.get(symbol, []) if date_start <= b.session_date <= date_end
        ]

    def close(self) -> None:  # pragma: no cover - interface parity
        pass


@pytest.fixture
def conn(tmp_path: Path):
    c = db.get_connection(tmp_path / "audit.db")
    db.migrate(c)
    yield c
    c.close()


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("5"),
        per_symbol_pct=Decimal("90"),
        global_exposure_pct=Decimal("90"),
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


def _daily_buy_rule() -> TradingRule:
    """Fires at the winter XNYS close (21:00 UTC) every session; tiny buy that
    fills (limit far above price) so the equity curve varies with close."""
    return TradingRule(
        id="r1",
        symbol="AAPL",
        stage=StrategyStage.BACKTEST,
        priority=0,
        trigger=TimeTrigger(at_time="21:00", cooldown_seconds=0),
        action=Action(side=Side.BUY, order_type=OrderType.LIMIT, qty=1, limit_price="500.00"),
    )


_XNYS = ec.get_calendar("XNYS")


def _session_bars(start: date, end: date) -> dict[str, list[OHLCVBar]]:
    """Deterministic oscillating closes on every real XNYS session in [start, end]."""
    sessions = _XNYS.sessions_in_range(start.isoformat(), end.isoformat())
    bars: list[OHLCVBar] = []
    for i, ts in enumerate(sessions):
        # Oscillate so daily returns have both signs (non-trivial sortino).
        close = Decimal("200") + Decimal(str((i % 7) - 3))
        bars.append(
            OHLCVBar(
                symbol="AAPL",
                session_date=ts.date(),
                open=close,
                high=close + Decimal("5"),
                low=close - Decimal("5"),
                close=close,
                volume=1_000_000,
                session_schedule_tag="regular",
            )
        )
    return {"AAPL": bars}


def _summary(*, return_pct: str, sharpe: str, sortino: str = "0", dd: str = "0") -> BacktestSummary:
    return BacktestSummary(
        aggregate_return_pct=Decimal(return_pct),
        aggregate_max_drawdown_pct=Decimal(dd),
        aggregate_sharpe=Decimal(sharpe),
        aggregate_sortino=Decimal(sortino),
        total_orders=0,
        total_fills=0,
        total_gate_rejections=0,
    )


def _window_result(
    idx: int, *, is_sharpe: str, oos_sharpe: str, oos_return: str = "1", oos_sortino: str = "0"
) -> WalkForwardWindowResult:
    is_s = _summary(return_pct="1", sharpe=is_sharpe)
    oos_s = _summary(return_pct=oos_return, sharpe=oos_sharpe, sortino=oos_sortino)
    is_sh = Decimal(is_sharpe)
    wfe = None if is_sh <= 0 else Decimal(oos_sharpe) / is_sh
    return WalkForwardWindowResult(
        window=WalkForwardWindow(
            idx, date(2024, 1, 1), date(2024, 1, 10), date(2024, 1, 11), date(2024, 1, 20)
        ),
        is_summary=is_s,
        oos_summary=oos_s,
        wfe_sharpe=wfe,
        wfe_sortino=None,
        wfe_return=None,
    )


# ---------- window generation ---------------------------------------------


def test_generate_windows_rolling_contiguous_oos() -> None:
    windows = generate_windows(
        date(2024, 1, 1),
        date(2024, 1, 31),
        in_sample_days=10,
        out_of_sample_days=5,
    )
    # OOS starts at Jan11, Jan16, Jan21, Jan26 (end Jan30); Jan31 start would end Feb4 > Jan31.
    assert [w.oos_start for w in windows] == [
        date(2024, 1, 11),
        date(2024, 1, 16),
        date(2024, 1, 21),
        date(2024, 1, 26),
    ]
    # Contiguous OOS tiling: each OOS picks up the day after the prior one.
    for prev, nxt in zip(windows, windows[1:], strict=False):
        assert nxt.oos_start == prev.oos_end + timedelta(days=1)
    # Rolling IS has fixed length and ends the day before OOS.
    for w in windows:
        assert (w.is_end - w.is_start).days == 9  # 10 inclusive days
        assert w.oos_start == w.is_end + timedelta(days=1)


def test_generate_windows_anchored_is_expands() -> None:
    windows = generate_windows(
        date(2024, 1, 1),
        date(2024, 2, 29),
        in_sample_days=10,
        out_of_sample_days=10,
        mode="anchored",
    )
    assert len(windows) >= 2
    # Anchored: every IS starts at the very beginning and grows.
    assert all(w.is_start == date(2024, 1, 1) for w in windows)
    assert windows[1].is_end > windows[0].is_end


def test_generate_windows_too_short_raises() -> None:
    with pytest.raises(WalkForwardError, match="too short"):
        generate_windows(
            date(2024, 1, 1),
            date(2024, 1, 5),
            in_sample_days=10,
            out_of_sample_days=10,
        )


def test_generate_windows_bad_params_raise() -> None:
    with pytest.raises(WalkForwardError):
        generate_windows(
            date(2024, 1, 1), date(2024, 2, 1), in_sample_days=0, out_of_sample_days=5
        )
    with pytest.raises(WalkForwardError):
        generate_windows(
            date(2024, 1, 1),
            date(2024, 2, 1),
            in_sample_days=5,
            out_of_sample_days=5,
            mode="bogus",
        )


# ---------- single-yardstick consistency (the key SC) ---------------------


def test_oos_summary_uses_same_yardstick_as_direct_backtest(conn, tmp_path) -> None:
    """SC: a window's OOS metrics byte-equal an independent backtest over the
    exact same OOS dates — proving the harness reuses build_summary (헌법 X.2)."""
    data = _session_bars(date(2024, 1, 1), date(2024, 3, 31))
    rules = [_daily_buy_rule()]
    cost_model = BacktestCostModel.kis_default()

    report = run_walk_forward(
        rules=rules,
        data_source=_FakeDataSource(data),
        date_start=date(2024, 1, 1),
        date_end=date(2024, 3, 31),
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        in_sample_days=20,
        out_of_sample_days=10,
        cost_model=cost_model,
    )
    assert len(report.windows) >= 2

    w0 = report.windows[0].window
    # Independent backtest over exactly window 0's OOS range.
    broker = BacktestBroker()
    clock = ReplayClock(datetime.combine(w0.oos_start, datetime.min.time(), UTC))
    direct = replay(
        rules=rules,
        data_source=_FakeDataSource(data),
        date_start=w0.oos_start,
        date_end=w0.oos_end,
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        conn=conn,
        clock=clock,
        broker=broker,
        run_id="direct-cmp",
        cost_model=cost_model,
    )
    direct_summary = build_summary(direct, build_per_rule_results(direct))

    oos = report.windows[0].oos_summary
    assert oos.aggregate_sharpe == direct_summary.aggregate_sharpe
    assert oos.aggregate_return_pct == direct_summary.aggregate_return_pct
    assert oos.aggregate_sortino == direct_summary.aggregate_sortino
    assert oos.aggregate_max_drawdown_pct == direct_summary.aggregate_max_drawdown_pct


def test_run_walk_forward_in_memory_conn(tmp_path) -> None:
    """No conn passed → harness opens its own in-memory audit DB and still runs."""
    data = _session_bars(date(2024, 1, 1), date(2024, 2, 29))
    report = run_walk_forward(
        rules=[_daily_buy_rule()],
        data_source=_FakeDataSource(data),
        date_start=date(2024, 1, 1),
        date_end=date(2024, 2, 29),
        caps=_caps(),
        whitelist=_whitelist(),
        halt_path=tmp_path / "HALT",
        in_sample_days=15,
        out_of_sample_days=10,
    )
    assert report.windows
    assert report.in_sample_days == 15
    # render must not raise and must mention the verdict.
    md = render_walk_forward_report(report)
    assert "워크포워드" in md
    assert "표본 외 집계" in md


# ---------- WFE / overfit verdict logic -----------------------------------


def test_verdict_stable_when_oos_tracks_is() -> None:
    windows = [
        _window_result(i, is_sharpe="1.0", oos_sharpe="0.9", oos_return="2") for i in range(3)
    ]
    report = _build_report(
        windows, mode="rolling", in_sample_days=20, out_of_sample_days=10, step_days=10,
        wfe_threshold=Decimal("0.5"),
    )
    assert report.overfit_suspected is False
    assert report.overfit_reasons == []
    assert report.mean_wfe_sharpe == Decimal("0.900000")
    assert report.windows_oos_profitable == 3


def test_verdict_overfit_when_wfe_below_threshold() -> None:
    windows = [
        _window_result(i, is_sharpe="2.0", oos_sharpe="0.2", oos_return="1") for i in range(3)
    ]
    report = _build_report(
        windows, mode="rolling", in_sample_days=20, out_of_sample_days=10, step_days=10,
        wfe_threshold=Decimal("0.5"),
    )
    assert report.overfit_suspected is True
    assert any("WFE" in r for r in report.overfit_reasons)


def test_verdict_overfit_when_oos_edge_vanishes() -> None:
    """Positive in-sample sharpe but non-positive out-of-sample + losing windows."""
    windows = [
        _window_result(i, is_sharpe="1.0", oos_sharpe="-0.5", oos_return="-3") for i in range(3)
    ]
    report = _build_report(
        windows, mode="rolling", in_sample_days=20, out_of_sample_days=10, step_days=10,
        wfe_threshold=Decimal("0.5"),
    )
    assert report.overfit_suspected is True
    # Both the edge-vanish reason and the <half-profitable reason should fire.
    assert any("우위 소멸" in r for r in report.overfit_reasons)
    assert any("과반 미만" in r for r in report.overfit_reasons)
    assert report.windows_oos_profitable == 0


def test_wfe_none_when_is_sharpe_non_positive() -> None:
    """IS sharpe <= 0 → WFE undefined (None), excluded from the mean."""
    windows = [
        _window_result(0, is_sharpe="0", oos_sharpe="0.5", oos_return="1"),
        _window_result(1, is_sharpe="1.0", oos_sharpe="0.8", oos_return="1"),
    ]
    report = _build_report(
        windows, mode="rolling", in_sample_days=20, out_of_sample_days=10, step_days=10,
        wfe_threshold=Decimal("0.5"),
    )
    assert windows[0].wfe_sharpe is None
    # Mean WFE computed only over the defined window (0.8).
    assert report.mean_wfe_sharpe == Decimal("0.800000")
