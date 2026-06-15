"""스펙 032 — 포트폴리오 워크포워드(표본 외 + 디플레이티드 샤프) 평가 테스트.

운영자 우려(한 벤치마크·한 기간 과적합)를 막는 장치가 의도대로 동작하는지:
판정 로직이 다중검정 보정(DSR)을 강제하는지, 합성 데이터에서 구간 분할·집계가
형성되는지 확인한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from auto_invest.backtest.data_model import OHLCVBar
from auto_invest.backtest.data_source import trading_days_between
from auto_invest.backtest.portfolio_walk_forward import (
    _verdict,
    run_portfolio_walk_forward,
)
from auto_invest.backtest.walk_forward import WalkForwardError
from auto_invest.config.caps import SizingCaps
from auto_invest.config.enums import OrderType
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import db
from auto_invest.portfolio.backtest_anchored import backtest_anchored_verdict

# ----------------------------------------------------------- _verdict 단위


def test_verdict_requires_dsr_to_call_an_edge_robust():
    # 과반 승 + 평균 샤프 우위인데도 DSR<0.95 면 "엣지 없음"이어야 한다
    # (이게 운영자가 걱정한 '벤치마크는 이겼지만 우연' 사례를 막는 핵심 가드).
    v = _verdict(
        n_segments=4,
        wins=3,
        mean_strat=Decimal("1.37"),
        mean_bench=Decimal("1.35"),
        psr=Decimal("0.99"),
        dsr=Decimal("0.90"),  # 시도 횟수 보정 후 미달
    )
    assert "강건한 엣지 없음" in v
    assert "디플레이티드 샤프 미달" in v


def test_verdict_robust_only_when_all_three_pass():
    v = _verdict(
        n_segments=4,
        wins=3,
        mean_strat=Decimal("1.37"),
        mean_bench=Decimal("1.35"),
        psr=Decimal("0.99"),
        dsr=Decimal("0.97"),  # 다중검정 통과
    )
    assert "강건한 엣지 신호" in v


def test_verdict_flags_segment_minority_and_low_mean():
    v = _verdict(
        n_segments=4,
        wins=1,
        mean_strat=Decimal("0.2"),
        mean_bench=Decimal("1.3"),
        psr=Decimal("0.5"),
        dsr=Decimal("0.03"),
    )
    assert "강건한 엣지 없음" in v
    assert "구간 과반 실패" in v
    assert "평균 샤프가 단순 보유 이하" in v
    assert "라이브 배포 정당화 안 됨" in v


# ----------------------------------------------------------- 합성 전 구간 실행


@dataclass
class _FakeSource:
    bars: dict[str, list[OHLCVBar]]

    @property
    def dataset_version(self) -> str:
        return "wf-test"

    def list_symbols(self) -> list[str]:
        return sorted(self.bars)

    def session_dates(self, symbol: str) -> list[date]:
        return [b.session_date for b in self.bars.get(symbol, [])]

    def coverage_holes(self, symbols, date_start, date_end):  # noqa: ANN001
        return []

    def read_bars(self, symbol: str, date_start: date, date_end: date) -> list[OHLCVBar]:
        return [b for b in self.bars.get(symbol, []) if date_start <= b.session_date <= date_end]

    def close(self) -> None:  # CSVDataSource parity
        pass


def _series(symbol: str, sessions: list[date], base: float, drift: float) -> list[OHLCVBar]:
    bars = []
    price = base
    for d in sessions:
        price *= 1.0 + drift
        p = Decimal(str(round(price, 2)))
        bars.append(
            OHLCVBar(
                symbol=symbol,
                session_date=d,
                open=p,
                high=p,
                low=p,
                close=p,
                volume=1000,
                session_schedule_tag="regular",
            )
        )
    return bars


def test_run_portfolio_walk_forward_builds_segmented_report(tmp_path: Path):
    start = date(2015, 1, 2)
    end = date(2017, 6, 30)
    sessions = trading_days_between(start, end)  # real XNYS sessions
    uni = ("AAA", "BBB", "CCC")
    # 서로 다른 드리프트 → 횡단면 순위/재조정이 의미를 갖도록.
    src = _FakeSource(
        bars={
            "AAA": _series("AAA", sessions, 100.0, 0.0008),
            "BBB": _series("BBB", sessions, 100.0, 0.0003),
            "CCC": _series("CCC", sessions, 100.0, -0.0002),
        }
    )
    caps = SizingCaps(
        per_trade_pct=Decimal("20"),
        per_symbol_pct=Decimal("50"),
        global_exposure_pct=Decimal("100"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("40"),
    )
    wl = Whitelist(
        symbols=frozenset(uni),
        accounts=frozenset({"BACKTEST"}),
        order_types=frozenset({OrderType.MARKET}),
    )
    cfg = PortfolioRebalanceConfig(
        id="t",
        universe=uni,
        weights={"momentum": Decimal("1")},
        weight_scheme="equal",
        top_n=2,
        invested_fraction=Decimal("0.95"),
        rebalance_every_n_sessions=21,
        lookback_bars=40,
        momentum_period=30,
        rebalance_threshold_pct=Decimal("1.0"),
        min_notional_usd=Decimal("50"),
    )
    conn = db.get_connection(tmp_path / "a.db")
    db.migrate(conn)
    report = run_portfolio_walk_forward(
        config=cfg,
        data_source=src,
        date_start=start,
        date_end=end,
        caps=caps,
        whitelist=wl,
        halt_path=tmp_path / "halt.flag",
        conn=conn,
        lookback_buffer_days=120,
        segment_days=180,
        mode="rolling",
        total_capital_usd=Decimal("100000"),
        num_trials=5,
    )
    conn.close()

    assert report.n_segments >= 2
    assert len(report.segments) == report.n_segments
    assert 0 <= report.segments_strategy_wins <= report.n_segments
    # num_trials 가 보고서로 흐른다(다중검정 보정 기준).
    assert report.num_trials == 5
    # 시도>=2 이므로 DSR 이 계산되어야 한다.
    assert report.strategy_dsr is not None
    # 각 구간이 전략·벤치 지표를 갖는다.
    for s in report.segments:
        assert s.n_sessions > 0
        assert isinstance(s.strategy_sharpe, Decimal)
        assert isinstance(s.benchmark_sharpe, Decimal)
    assert report.verdict  # 비어있지 않은 한글 판정


def test_run_portfolio_walk_forward_raises_when_period_too_short(tmp_path: Path):
    start = date(2015, 1, 2)
    sessions = trading_days_between(start, date(2015, 2, 15))
    uni = ("AAA", "BBB")
    src = _FakeSource(
        bars={
            "AAA": _series("AAA", sessions, 100.0, 0.001),
            "BBB": _series("BBB", sessions, 100.0, 0.0005),
        }
    )
    caps = SizingCaps(
        per_trade_pct=Decimal("20"),
        per_symbol_pct=Decimal("50"),
        global_exposure_pct=Decimal("100"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("40"),
    )
    wl = Whitelist(
        symbols=frozenset(uni),
        accounts=frozenset({"BACKTEST"}),
        order_types=frozenset({OrderType.MARKET}),
    )
    cfg = PortfolioRebalanceConfig(
        id="t", universe=uni, weights={"momentum": Decimal("1")}, weight_scheme="equal",
        top_n=1, rebalance_every_n_sessions=5, lookback_bars=30, momentum_period=5,
    )
    conn = db.get_connection(tmp_path / "a.db")
    db.migrate(conn)
    # in_sample_buffer + segment 가 가용 기간보다 길면 generate_windows 가 던진다.
    with pytest.raises(WalkForwardError):
        run_portfolio_walk_forward(
            config=cfg, data_source=src, date_start=start, date_end=date(2015, 2, 15),
            caps=caps, whitelist=wl, halt_path=tmp_path / "h", conn=conn,
            lookback_buffer_days=200, segment_days=200, num_trials=1,
        )
    conn.close()


def test_pooled_returns_feed_backtest_anchored(tmp_path: Path):
    """배선 검증: walk-forward 가 OOS 일수익률(pooled_returns)을 내고, 그게
    backtest_anchored_verdict 에 그대로 들어가 판정을 만든다 — 가속기 파이프라인.

    이게 운영자 지적의 실제 해법: 깊은 OOS(여기선 합성 walk-forward)가 엣지 증거를
    제공하고, 짧은 forward 는 지속성만 확인 → 일별 20일 재발견 불필요.
    """
    start = date(2015, 1, 2)
    end = date(2017, 6, 30)
    sessions = trading_days_between(start, end)
    uni = ("AAA", "BBB", "CCC")
    src = _FakeSource(
        bars={
            "AAA": _series("AAA", sessions, 100.0, 0.0009),
            "BBB": _series("BBB", sessions, 100.0, 0.0004),
            "CCC": _series("CCC", sessions, 100.0, -0.0001),
        }
    )
    caps = SizingCaps(
        per_trade_pct=Decimal("20"),
        per_symbol_pct=Decimal("50"),
        global_exposure_pct=Decimal("100"),
        canary_capital_pct=Decimal("5"),
        canary_min_duration_days=10,
        canary_acceptance_drawdown_pct=Decimal("40"),
    )
    wl = Whitelist(
        symbols=frozenset(uni),
        accounts=frozenset({"BACKTEST"}),
        order_types=frozenset({OrderType.MARKET}),
    )
    cfg = PortfolioRebalanceConfig(
        id="t",
        universe=uni,
        weights={"momentum": Decimal("1")},
        weight_scheme="equal",
        top_n=2,
        invested_fraction=Decimal("0.95"),
        rebalance_every_n_sessions=21,
        lookback_bars=40,
        momentum_period=30,
        rebalance_threshold_pct=Decimal("1.0"),
        min_notional_usd=Decimal("50"),
    )
    conn = db.get_connection(tmp_path / "a.db")
    db.migrate(conn)
    report = run_portfolio_walk_forward(
        config=cfg,
        data_source=src,
        date_start=start,
        date_end=end,
        caps=caps,
        whitelist=wl,
        halt_path=tmp_path / "halt.flag",
        conn=conn,
        lookback_buffer_days=120,
        segment_days=180,
        mode="rolling",
        total_capital_usd=Decimal("100000"),
        num_trials=1,
    )
    conn.close()

    # walk-forward 가 OOS 일수익률 사슬을 노출한다.
    assert len(report.pooled_returns) == report.pooled_obs
    assert len(report.pooled_returns) >= 20

    # 그 OOS 가 앵커드 판정 엔진에 그대로 들어간다(짧은 forward 는 OOS 꼬리로 일관 가정).
    forward = report.pooled_returns[-6:]
    v = backtest_anchored_verdict(
        oos_returns=report.pooled_returns,
        forward_returns=forward,
        min_oos_obs=20,
        min_forward_obs=5,
    )
    # 파이프라인이 일관된 판정을 만든다(OOS 관측이 그대로 전달됨).
    assert v.verdict in ("EDGE_CONFIRMED", "NO_EDGE", "INSUFFICIENT_DATA")
    assert v.oos_n_obs == len(report.pooled_returns)
    assert v.forward_n_obs == 6
