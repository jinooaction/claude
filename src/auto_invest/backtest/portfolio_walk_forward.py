"""스펙 032 — 포트폴리오 재조정 전략의 표본 외(워크포워드) + 다중검정 보정 평가.

운영자 우려: "단순 보유라는 한 벤치마크만 이기려다 한 기간에 과적합된 전략이 될까".
그 함정을 *코드로* 막는 평가 장치다. 단일 표본 내 총수익 비교(backtest-portfolio)
대신:

1. **구간 분할(표본 외 일관성)** — 평가 기간을 연속된 여러 구간으로 잘라 각 구간을
   독립 실행(신선한 장부)한다. 엣지가 한 구간의 요행인지, 여러 구간에 일관된지 본다.
   각 구간은 `replay_portfolio` 가 `date.min` 부터 과거를 로드하므로 신호 룩백을 받는다.
2. **위험조정·다중 벤치마크** — 총수익이 아니라 구간별 샤프·최대낙폭으로 전략 vs
   단순 보유를 비교한다. "강세장 총수익 이기기"라는 편향된 목표를 피한다.
3. **디플레이티드 샤프(다중검정 보정)** — 운영자/튜너가 *시도한 모든 설정*의 샤프를
   세어, 그중 하나가 우연히 좋아 보일 확률만큼 선택된 설정의 샤프를 깎는다(스펙 027).
   이게 "여러 설정을 돌려보고 제일 좋은 걸 골랐다"는 과적합을 직접 처벌한다.

표본 외 풀(여러 구간의 일별 수익률을 이어붙임)에 PSR/DSR 을 적용해 통계적 유의성을
낸다. 수익률은 척도 무관이라 구간 경계를 이어붙여도 안전(스펙 027 의 규약과 동일).

오프라인·읽기 전용. Kernel 터치 0건. 돈을 움직이지 않는다.
"""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.config.whitelist import Whitelist

from .broker_mock import BacktestBroker
from .clock import ReplayClock
from .costs import BacktestCostModel
from .data_model import canonicalise_decimal
from .data_source import HistoricalDataSource
from .metrics import daily_returns_from_equity
from .portfolio_replay import replay_portfolio
from .significance import (
    deflated_sharpe_ratio,
    deflated_sharpe_ratio_from_trial_sharpes,
    significance_summary,
)
from .walk_forward import generate_windows


@dataclass(frozen=True)
class PortfolioSegmentResult:
    """One contiguous out-of-sample segment: strategy vs benchmark, risk-adjusted."""

    index: int
    start: date
    end: date
    n_sessions: int
    strategy_return_pct: Decimal
    benchmark_return_pct: Decimal
    strategy_sharpe: Decimal
    benchmark_sharpe: Decimal
    strategy_maxdd_pct: Decimal
    benchmark_maxdd_pct: Decimal

    @property
    def strategy_beats_benchmark(self) -> bool:
        """Risk-adjusted win: higher Sharpe (NOT just higher total return)."""
        return self.strategy_sharpe > self.benchmark_sharpe


@dataclass(frozen=True)
class PortfolioWalkForwardReport:
    """Out-of-sample, risk-adjusted, multiple-testing-corrected verdict."""

    segments: list[PortfolioSegmentResult] = field(default_factory=list)
    n_segments: int = 0
    # Per-segment consistency (risk-adjusted).
    segments_strategy_wins: int = 0
    mean_strategy_sharpe: Decimal | None = None
    mean_benchmark_sharpe: Decimal | None = None
    # Pooled out-of-sample track (concatenated daily returns across segments).
    pooled_strategy_sharpe_annual: Decimal | None = None
    pooled_obs: int = 0
    # Multiple-testing-corrected significance on the pooled strategy track.
    num_trials: int = 1
    strategy_psr: Decimal | None = None
    strategy_dsr: Decimal | None = None
    verdict: str = ""


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    return Decimal(canonicalise_decimal(sum(values, start=Decimal("0")) / Decimal(len(values))))


def run_portfolio_walk_forward(
    *,
    config: PortfolioRebalanceConfig,
    data_source: HistoricalDataSource,
    date_start: date,
    date_end: date,
    caps: SizingCaps,
    whitelist: Whitelist,
    halt_path: Path,
    conn,
    lookback_buffer_days: int,
    segment_days: int,
    mode: str = "anchored",
    total_capital_usd: Decimal = Decimal("100000"),
    cost_model: BacktestCostModel | None = None,
    num_trials: int = 1,
    trial_sharpes_annual: Sequence[Decimal] | None = None,
) -> PortfolioWalkForwardReport:
    """Tile [date_start, date_end] into contiguous OOS segments, run the fixed
    rebalancing ``config`` independently in each, and return a risk-adjusted,
    deflated-Sharpe verdict.

    ``lookback_buffer_days`` is reserved before the first segment so the strategy's
    momentum/lookback has history (the IS field from ``generate_windows`` — we do
    NOT fit anything on it; a fixed rebalancing config has no fitted parameters,
    so the only overfitting channel is *config selection*, handled by DSR).
    ``segment_days`` is each OOS segment's length; segments tile contiguously.

    ``num_trials`` (or the explicit ``trial_sharpes_annual`` list) is how many
    distinct configs were tried in the whole search — the deflation base.
    """
    cost = cost_model or BacktestCostModel.kis_default()
    windows = generate_windows(
        date_start,
        date_end,
        in_sample_days=lookback_buffer_days,
        out_of_sample_days=segment_days,
        mode=mode,
    )

    segments: list[PortfolioSegmentResult] = []
    pooled_returns: list[Decimal] = []
    strat_sharpes: list[Decimal] = []
    bench_sharpes: list[Decimal] = []

    for w in windows:
        broker = BacktestBroker()
        clock = ReplayClock(datetime.combine(w.oos_start, datetime.min.time(), UTC))
        result = replay_portfolio(
            config=config,
            data_source=data_source,
            date_start=w.oos_start,
            date_end=w.oos_end,
            caps=caps,
            whitelist=whitelist,
            halt_path=halt_path,
            conn=conn,
            clock=clock,
            broker=broker,
            run_id=f"pwf-{w.index}",
            total_capital_usd=total_capital_usd,
            cost_model=cost,
        )
        equities = [e for _, e in result.equity_curve]
        if len(equities) >= 2:
            with contextlib.suppress(ValueError):
                pooled_returns.extend(daily_returns_from_equity(equities))
        segments.append(
            PortfolioSegmentResult(
                index=w.index,
                start=w.oos_start,
                end=w.oos_end,
                n_sessions=len(equities),
                strategy_return_pct=result.total_return_pct,
                benchmark_return_pct=result.benchmark_total_return_pct,
                strategy_sharpe=result.sharpe_ratio,
                benchmark_sharpe=result.benchmark_sharpe_ratio,
                strategy_maxdd_pct=result.max_drawdown_pct,
                benchmark_maxdd_pct=result.benchmark_max_drawdown_pct,
            )
        )
        strat_sharpes.append(result.sharpe_ratio)
        bench_sharpes.append(result.benchmark_sharpe_ratio)

    wins = sum(1 for s in segments if s.strategy_beats_benchmark)

    # Pooled out-of-sample significance, deflated by the number of configs tried.
    pooled_sharpe_annual: Decimal | None = None
    psr: Decimal | None = None
    dsr: Decimal | None = None
    if len(pooled_returns) >= 2:
        summary = significance_summary(pooled_returns)
        if summary is not None:
            pooled_sharpe_annual = summary.sharpe_annual
            psr = summary.psr
        if trial_sharpes_annual is not None and len(trial_sharpes_annual) >= 2:
            dsr = deflated_sharpe_ratio_from_trial_sharpes(pooled_returns, trial_sharpes_annual)
        elif num_trials >= 2 and strat_sharpes:
            # Derive trial dispersion from this run's per-segment sharpes if no
            # explicit cross-config list was supplied (conservative fallback).
            dsr = deflated_sharpe_ratio_from_trial_sharpes(
                pooled_returns, strat_sharpes + bench_sharpes
            )
        else:
            # Genuinely a single trial (num_trials==1): DSR reduces to PSR — no
            # multiple-testing deflation to apply. Report it rather than None so the
            # verdict isn't falsely flagged as "DSR missing".
            dsr = deflated_sharpe_ratio(
                pooled_returns, num_trials=1, trial_sharpe_std_annual=Decimal("0")
            )

    mean_strat = _mean(strat_sharpes)
    mean_bench = _mean(bench_sharpes)
    verdict = _verdict(
        n_segments=len(segments),
        wins=wins,
        mean_strat=mean_strat,
        mean_bench=mean_bench,
        psr=psr,
        dsr=dsr,
    )

    return PortfolioWalkForwardReport(
        segments=segments,
        n_segments=len(segments),
        segments_strategy_wins=wins,
        mean_strategy_sharpe=mean_strat,
        mean_benchmark_sharpe=mean_bench,
        pooled_strategy_sharpe_annual=pooled_sharpe_annual,
        pooled_obs=len(pooled_returns),
        num_trials=(
            len(trial_sharpes_annual) if trial_sharpes_annual is not None else num_trials
        ),
        strategy_psr=psr,
        strategy_dsr=dsr,
        verdict=verdict,
    )


def _verdict(
    *,
    n_segments: int,
    wins: int,
    mean_strat: Decimal | None,
    mean_bench: Decimal | None,
    psr: Decimal | None,
    dsr: Decimal | None,
) -> str:
    """Honest one-line judgment. A robust edge needs ALL of: risk-adjusted win in
    a majority of OOS segments, higher mean Sharpe than the benchmark, AND a
    deflated Sharpe that survives multiple-testing correction (DSR ≥ 0.95)."""
    if n_segments == 0:
        return "구간 없음 — 평가 기간이 너무 짧습니다."
    majority = wins * 2 > n_segments
    beats_mean = mean_strat is not None and mean_bench is not None and mean_strat > mean_bench
    dsr_ok = dsr is not None and dsr >= Decimal("0.95")
    if majority and beats_mean and dsr_ok:
        return (
            f"강건한 엣지 신호: {n_segments}개 구간 중 {wins}개에서 위험조정 우위 + "
            f"평균 샤프 우위 + 디플레이티드 샤프 {dsr} (다중검정 통과). 단, 더 많은 국면·"
            "유니버스로 재확인 필요."
        )
    reasons = []
    if not majority:
        reasons.append(f"구간 과반 실패({wins}/{n_segments})")
    if not beats_mean:
        reasons.append("평균 샤프가 단순 보유 이하")
    if not dsr_ok:
        reasons.append(
            f"디플레이티드 샤프 미달(DSR={dsr if dsr is not None else 'N/A'} < 0.95) "
            "— 시도 횟수 보정 후 우연과 구별 안 됨"
        )
    return "강건한 엣지 없음: " + "; ".join(reasons) + ". 라이브 배포 정당화 안 됨."
