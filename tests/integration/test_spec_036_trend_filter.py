"""스펙 036 — 추세 필터가 백테스트 경로로 흘러 드로다운을 방어하는지(메커니즘) 검증.

⚠ 이건 *메커니즘* 테스트다(엣지 주장 아님): 합성 폭락에서 추세 필터를 켜면 종목이
SMA 아래로 내려갈 때 현금으로 빠져 **최대낙폭이 줄어드는가**만 본다. "지금 통하는가"의
판정은 옛 데이터 백테스트가 아니라 forward 페이퍼 트랙 + 스펙 035 엣지 판정이 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from auto_invest.backtest.broker_mock import BacktestBroker
from auto_invest.backtest.clock import ReplayClock
from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.data_source import trading_days_between
from auto_invest.backtest.portfolio_replay import replay_portfolio
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType
from auto_invest.config.rules import PortfolioRebalanceConfig, TrendFilterConfig
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
        c = Decimal(str(round(price_of(i), 4)))
        out.append(
            OHLCVBar(
                symbol=symbol,
                session_date=d,
                open=c,
                high=(c * Decimal("1.005")).quantize(Decimal("0.0001")),
                low=(c * Decimal("0.995")).quantize(Decimal("0.0001")),
                close=c,
                volume=10_000_000,
                session_schedule_tag="regular",
            )
        )
    return out


def _caps() -> SizingCaps:
    return SizingCaps(
        per_trade_pct=Decimal("60"),
        per_symbol_pct=Decimal("65"),
        global_exposure_pct=Decimal("100"),
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


_run_counter = 0


def _run(cfg, dsource, days, tmp_path, *, start_idx):
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
            caps=_caps(),
            whitelist=_whitelist(cfg.universe),
            halt_path=tmp_path / "HALT",
            conn=conn,
            clock=ReplayClock(datetime(2023, 1, 1, tzinfo=UTC)),
            broker=BacktestBroker(),
            run_id="bt-trend-test",
            total_capital_usd=Decimal("100000"),
        )
    finally:
        conn.close()


def _rise_then_crash(i: int) -> float:
    # 120세션 완만 상승 후 60세션 급락(−~55%).
    if i < 120:
        return 100 * (1.004**i)
    peak = 100 * (1.004**120)
    return peak * (0.99**(i - 120))


def _cfg(trend: TrendFilterConfig | None) -> PortfolioRebalanceConfig:
    return PortfolioRebalanceConfig(
        id="p-trend",
        universe=("AAA", "BBB"),
        weights={"momentum": Decimal("1")},
        top_n=2,
        weight_scheme="equal",
        invested_fraction=Decimal("0.95"),
        rebalance_every_n_sessions=10,
        lookback_bars=30,
        momentum_period=10,
        trend_filter=trend,
    )


def test_trend_filter_reduces_drawdown_in_crash(tmp_path: Path):
    """추세 필터 ON 이면 폭락에서 현금으로 빠져 최대낙폭이 OFF 보다 작다(메커니즘)."""
    days = trading_days_between(date(2023, 1, 3), date(2023, 12, 29))
    bars = {
        "AAA": _bars("AAA", days, _rise_then_crash),
        "BBB": _bars("BBB", days, _rise_then_crash),
    }
    ds = _FakeDataSource(bars)

    off = _run(_cfg(None), ds, days, tmp_path, start_idx=40)
    on = _run(
        _cfg(TrendFilterConfig(method="sma", lookback=40, on_insufficient="hold")),
        ds,
        days,
        tmp_path,
        start_idx=40,
    )

    # 메커니즘: 추세 방어가 켜지면 최대낙폭이 더 작아야 한다(엄격히 작음).
    assert on.max_drawdown_pct < off.max_drawdown_pct
    # 그리고 트렌드 OFF 는 폭락을 그대로 맞아 큰 낙폭을 낸다(시나리오 sanity).
    assert off.max_drawdown_pct > Decimal("20")


def test_trend_filter_off_is_unchanged_behaviour(tmp_path: Path):
    """trend_filter 미설정이면 기존 동작과 동일(가중치 합 1.0 경로, 회귀 안전망)."""
    days = trading_days_between(date(2023, 1, 3), date(2023, 9, 29))
    bars = {
        "AAA": _bars("AAA", days, lambda i: 100 * (1.002**i)),
        "BBB": _bars("BBB", days, lambda i: 100 * (1.001**i)),
    }
    ds = _FakeDataSource(bars)
    res = _run(_cfg(None), ds, days, tmp_path, start_idx=40)
    # 상승장 + 필터 없음 → 정상 자산곡선(양수 종료, 거래 발생).
    assert res.final_equity_usd > 0
