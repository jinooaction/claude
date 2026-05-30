"""Walk-forward (out-of-sample) validation harness — spec 016 슬라이스 3.

과적합(overfitting)을 탐지하는 표본 외(out-of-sample, OOS) 검증 하니스다. 같은
룰셋을 롤링 표본 내(in-sample, IS) / 표본 외 날짜 윈도우에 걸쳐 돌리고, IS 대비 OOS
성과를 **슬라이스 2의 단일 잣대**(`backtest/metrics.py` → `build_summary`)로 비교한다.

헌법 원칙 X.2(단일 잣대)·원칙 VI(백테스트 과대평가 경고)의 직접적 귀결이다. 슬라이스
1·2가 백테스트를 정직(비용)·완전·통일된 잣대로 만들었지만, **단일 기간 백테스트는
여전히 그 한 기간에 과적합될 수 있다** — 좋아 보이는 룰셋이 한 시기의 잡음을 외운
것뿐일 수 있다. 워크포워드는 "표본 밖에서도 같은 우위가 재현되는가?"를 묻는다.

핵심 산출물 두 가지:
  1. **표본 외 집계 성과**(pooled OOS) — 과적합에 강한 정직한 헤드라인 숫자.
  2. **워크포워드 효율(WFE = OOS 샤프 / IS 샤프)** — 윈도우별·평균. WFE 가 낮으면
     (기본 임계 0.5) IS 에서만 좋고 OOS 에서 무너진 것 → 과적합 의심.

안전 경계: 오프라인·읽기 전용. 기존 `replay` 를 날짜 부분구간에 재실행할 뿐이다.
새 감사 스키마 없음, Kernel 터치 없음(`backtest/` 는 비커널). 결정론: 모든 Decimal 은
6자리 정규화(`canonicalise_decimal`).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from auto_invest.config.caps import SizingCaps
from auto_invest.config.rules import TradingRule
from auto_invest.config.whitelist import Whitelist
from auto_invest.persistence import db

from .broker_mock import BacktestBroker
from .clock import ReplayClock, wall_clock_guard
from .costs import BacktestCostModel
from .data_model import BacktestSummary, canonicalise_decimal
from .data_source import HistoricalDataSource
from .judgment_stub import BACKTEST_MODE_ENV
from .metrics import daily_returns_from_equity, sharpe_ratio
from .replay import DEFAULT_TOTAL_CAPITAL_USD, replay
from .report import build_per_rule_results, build_summary
from .significance import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    minimum_track_record_length,
    probabilistic_sharpe_ratio,
    sample_kurtosis,
    sample_skewness,
)

DEFAULT_WFE_THRESHOLD = Decimal("0.5")


class WalkForwardError(ValueError):
    """Raised when window parameters cannot produce at least one IS/OOS pair."""


@dataclass(frozen=True)
class WalkForwardWindow:
    """One in-sample / out-of-sample split (inclusive calendar-date bounds)."""

    index: int
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date


@dataclass(frozen=True)
class WalkForwardWindowResult:
    """IS + OOS summaries for one window, plus the IS→OOS efficiency ratios."""

    window: WalkForwardWindow
    is_summary: BacktestSummary
    oos_summary: BacktestSummary
    # WFE = OOS / IS. None when the IS metric is non-positive (ratio undefined /
    # meaningless — you cannot "keep half of" a zero or negative in-sample edge).
    wfe_sharpe: Decimal | None
    wfe_sortino: Decimal | None
    wfe_return: Decimal | None


@dataclass(frozen=True)
class WalkForwardReport:
    """Aggregate verdict across all windows. The honest headline is the OOS block."""

    mode: str
    in_sample_days: int
    out_of_sample_days: int
    step_days: int
    wfe_threshold: Decimal
    windows: list[WalkForwardWindowResult] = field(default_factory=list)

    # Equal-weight mean of per-window OOS metrics (same averaging convention as
    # build_summary's aggregate_sharpe across rules). This is the overfitting-
    # resistant headline: performance the ruleset earned OUTSIDE its fit window.
    oos_mean_return_pct: Decimal = Decimal("0")
    oos_mean_sharpe: Decimal = Decimal("0")
    oos_mean_sortino: Decimal = Decimal("0")
    oos_worst_drawdown_pct: Decimal = Decimal("0")
    # IS counterpart, for the side-by-side comparison.
    is_mean_sharpe: Decimal = Decimal("0")

    # Headline overfitting measures.
    mean_wfe_sharpe: Decimal | None = None
    median_wfe_sharpe: Decimal | None = None
    windows_oos_profitable: int = 0
    overfit_suspected: bool = False
    overfit_reasons: list[str] = field(default_factory=list)

    # 스펙 027 — 표본 외 풀(pooled OOS) 트랙의 다중검정/유의성 통계. 윈도우별 표본 외
    # 일별 수익률을 이어 붙인 하나의 연속 트랙에 대해 잰다. num_trials/trial std 가
    # 기본값이면 DSR·SR_0 은 None(디플레이션 미적용 — 기존 동작 byte 동일).
    num_trials: int = 1
    oos_n_obs: int = 0
    oos_sharpe_annual: Decimal | None = None
    oos_skew: Decimal | None = None
    oos_kurtosis: Decimal | None = None
    oos_psr: Decimal | None = None
    oos_min_track_record_obs: Decimal | None = None
    oos_expected_max_sharpe_annual: Decimal | None = None
    oos_dsr: Decimal | None = None


# ---------- window generation ---------------------------------------------


def generate_windows(
    date_start: date,
    date_end: date,
    *,
    in_sample_days: int,
    out_of_sample_days: int,
    step_days: int | None = None,
    mode: str = "rolling",
) -> list[WalkForwardWindow]:
    """Tile [date_start, date_end] into IS/OOS windows (inclusive bounds).

    * ``rolling``  — IS slides forward with the OOS window (fixed IS length).
    * ``anchored`` — IS always starts at ``date_start`` and expands each step.

    ``step_days`` defaults to ``out_of_sample_days`` so OOS segments tile the
    timeline contiguously without overlap. The k-th OOS window begins at
    ``date_start + in_sample_days + k*step``; windows whose OOS end would exceed
    ``date_end`` are dropped (no partial windows).
    """
    if in_sample_days < 1:
        raise WalkForwardError(f"in_sample_days must be >= 1, got {in_sample_days}")
    if out_of_sample_days < 1:
        raise WalkForwardError(f"out_of_sample_days must be >= 1, got {out_of_sample_days}")
    if mode not in ("rolling", "anchored"):
        raise WalkForwardError(f"mode must be 'rolling' or 'anchored', got {mode!r}")
    step = out_of_sample_days if step_days is None else step_days
    if step < 1:
        raise WalkForwardError(f"step_days must be >= 1, got {step}")
    if date_end < date_start:
        raise WalkForwardError(f"date_end {date_end} is before date_start {date_start}")

    windows: list[WalkForwardWindow] = []
    k = 0
    while True:
        oos_start = date_start + timedelta(days=in_sample_days + k * step)
        oos_end = oos_start + timedelta(days=out_of_sample_days - 1)
        if oos_end > date_end:
            break
        is_start = date_start if mode == "anchored" else oos_start - timedelta(days=in_sample_days)
        is_end = oos_start - timedelta(days=1)
        windows.append(
            WalkForwardWindow(
                index=k,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
            )
        )
        k += 1

    if not windows:
        raise WalkForwardError(
            "date range too short for even one IS+OOS window "
            f"({in_sample_days}d IS + {out_of_sample_days}d OOS needs "
            f"{in_sample_days + out_of_sample_days} days, have "
            f"{(date_end - date_start).days + 1})"
        )
    return windows


# ---------- per-segment replay --------------------------------------------


def _portfolio_daily_returns(result) -> list[Decimal]:
    """Sum per-rule mark-to-market equity per session date → portfolio daily returns.

    스펙 027 의 PSR/DSR 입력. 룰별 자산곡선을 같은 세션 날짜에서 합쳐 포트폴리오
    자산곡선을 만든 뒤 일별 단순 수익률로 변환한다(수익률은 척도 무관이라 윈도우
    사이를 이어 붙여도 안전). 자산이 2 점 미만이거나 0 을 포함하면 [](fail-safe).
    """
    by_date: dict[date, Decimal] = {}
    for curve in result.per_rule_equity_curve.values():
        for d, eq in curve:
            by_date[d] = by_date.get(d, Decimal("0")) + eq
    if len(by_date) < 2:
        return []
    equity = [by_date[d] for d in sorted(by_date)]
    try:
        return daily_returns_from_equity(equity)
    except ValueError:
        return []


def _run_segment(
    seg_start: date,
    seg_end: date,
    *,
    rules: Sequence[TradingRule],
    data_source: HistoricalDataSource,
    caps: SizingCaps,
    whitelist: Whitelist,
    halt_path: Path,
    conn,
    run_id: str,
    total_capital_usd: Decimal,
    cost_model: BacktestCostModel,
) -> tuple[BacktestSummary, list[Decimal]]:
    """Replay one date sub-range → (single-yardstick summary, portfolio daily returns).

    Each segment gets a fresh broker + clock so IS and OOS are independent
    runs (no position bleed across the IS/OOS boundary — OOS must be a clean
    out-of-sample test, not a continuation of the IS book). The returns series
    is the portfolio (all-rules) daily return, used by spec 027's pooled-OOS
    significance statistics; the IS caller ignores it.
    """
    broker = BacktestBroker()
    clock = ReplayClock(datetime.combine(seg_start, datetime.min.time(), UTC))
    result = replay(
        rules=list(rules),
        data_source=data_source,
        date_start=seg_start,
        date_end=seg_end,
        caps=caps,
        whitelist=whitelist,
        halt_path=halt_path,
        conn=conn,
        clock=clock,
        broker=broker,
        run_id=run_id,
        total_capital_usd=total_capital_usd,
        cost_model=cost_model,
    )
    per_rule = build_per_rule_results(result)
    return build_summary(result, per_rule), _portfolio_daily_returns(result)


# ---------- aggregation helpers -------------------------------------------


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    return Decimal(canonicalise_decimal(sum(values, start=Decimal("0")) / Decimal(len(values))))


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return Decimal(canonicalise_decimal(ordered[mid]))
    return Decimal(canonicalise_decimal((ordered[mid - 1] + ordered[mid]) / Decimal("2")))


def _ratio_or_none(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """OOS/IS efficiency. Undefined when the IS metric is non-positive."""
    if denominator <= 0:
        return None
    return Decimal(canonicalise_decimal(numerator / denominator))


# ---------- main entrypoint -----------------------------------------------


def run_walk_forward(
    *,
    rules: Sequence[TradingRule],
    data_source: HistoricalDataSource,
    date_start: date,
    date_end: date,
    caps: SizingCaps,
    whitelist: Whitelist,
    halt_path: Path,
    conn=None,
    in_sample_days: int,
    out_of_sample_days: int,
    step_days: int | None = None,
    mode: str = "rolling",
    total_capital_usd: Decimal = DEFAULT_TOTAL_CAPITAL_USD,
    cost_model: BacktestCostModel | None = None,
    wfe_threshold: Decimal = DEFAULT_WFE_THRESHOLD,
    num_trials: int = 1,
    trial_sharpe_std_annual: Decimal | None = None,
    min_psr: Decimal | None = None,
    min_dsr: Decimal | None = None,
) -> WalkForwardReport:
    """Run rolling/anchored walk-forward validation and return the verdict.

    ``conn`` is the audit DB the underlying replay writes to (ORDER_*/FILL rows,
    same vocabulary as a normal backtest). If ``None``, an in-memory audit DB is
    created — convenient for ad-hoc analysis where the per-segment audit trail
    is not needed. Pass an explicit connection to retain it.

    스펙 027: ``num_trials`` 는 운영자가 시도한 설정 개수(다중검정 디플레이션용),
    ``trial_sharpe_std_annual`` 은 그 시도들의 (연율) 샤프 표준편차. 둘 다 주어지면
    표본 외 풀 트랙의 DSR 을 계산한다. ``min_psr``/``min_dsr`` 은 옵트인 하드 게이트 —
    표본 외 PSR/DSR 이 임계 미만이면 과적합 사유 추가. 기본값(None)이면 기존 동작과
    byte 동일(새 사유 0 건).
    """
    if cost_model is None:
        cost_model = BacktestCostModel.kis_default()

    windows = generate_windows(
        date_start,
        date_end,
        in_sample_days=in_sample_days,
        out_of_sample_days=out_of_sample_days,
        step_days=step_days,
        mode=mode,
    )
    step = out_of_sample_days if step_days is None else step_days

    owns_conn = conn is None
    if owns_conn:
        conn = db.get_connection(":memory:")
        db.migrate(conn)

    window_results: list[WalkForwardWindowResult] = []
    oos_pooled_returns: list[Decimal] = []
    prior_env = os.environ.get(BACKTEST_MODE_ENV)
    os.environ[BACKTEST_MODE_ENV] = "1"
    try:
        with wall_clock_guard():
            for w in windows:
                run_id = f"wf-{w.index}"
                is_summary, _is_returns = _run_segment(
                    w.is_start,
                    w.is_end,
                    rules=rules,
                    data_source=data_source,
                    caps=caps,
                    whitelist=whitelist,
                    halt_path=halt_path,
                    conn=conn,
                    run_id=f"{run_id}-is",
                    total_capital_usd=total_capital_usd,
                    cost_model=cost_model,
                )
                oos_summary, oos_returns = _run_segment(
                    w.oos_start,
                    w.oos_end,
                    rules=rules,
                    data_source=data_source,
                    caps=caps,
                    whitelist=whitelist,
                    halt_path=halt_path,
                    conn=conn,
                    run_id=f"{run_id}-oos",
                    total_capital_usd=total_capital_usd,
                    cost_model=cost_model,
                )
                oos_pooled_returns.extend(oos_returns)
                window_results.append(
                    WalkForwardWindowResult(
                        window=w,
                        is_summary=is_summary,
                        oos_summary=oos_summary,
                        wfe_sharpe=_ratio_or_none(
                            oos_summary.aggregate_sharpe, is_summary.aggregate_sharpe
                        ),
                        wfe_sortino=_ratio_or_none(
                            oos_summary.aggregate_sortino, is_summary.aggregate_sortino
                        ),
                        wfe_return=_ratio_or_none(
                            oos_summary.aggregate_return_pct,
                            is_summary.aggregate_return_pct,
                        ),
                    )
                )
    finally:
        if prior_env is None:
            os.environ.pop(BACKTEST_MODE_ENV, None)
        else:
            os.environ[BACKTEST_MODE_ENV] = prior_env
        if owns_conn:
            conn.close()

    return _build_report(
        window_results,
        mode=mode,
        in_sample_days=in_sample_days,
        out_of_sample_days=out_of_sample_days,
        step_days=step,
        wfe_threshold=wfe_threshold,
        oos_pooled_returns=oos_pooled_returns,
        num_trials=num_trials,
        trial_sharpe_std_annual=trial_sharpe_std_annual,
        min_psr=min_psr,
        min_dsr=min_dsr,
    )


def _build_report(
    window_results: list[WalkForwardWindowResult],
    *,
    mode: str,
    in_sample_days: int,
    out_of_sample_days: int,
    step_days: int,
    wfe_threshold: Decimal,
    oos_pooled_returns: list[Decimal] | None = None,
    num_trials: int = 1,
    trial_sharpe_std_annual: Decimal | None = None,
    min_psr: Decimal | None = None,
    min_dsr: Decimal | None = None,
) -> WalkForwardReport:
    oos_returns = [r.oos_summary.aggregate_return_pct for r in window_results]
    oos_sharpes = [r.oos_summary.aggregate_sharpe for r in window_results]
    oos_sortinos = [r.oos_summary.aggregate_sortino for r in window_results]
    oos_drawdowns = [r.oos_summary.aggregate_max_drawdown_pct for r in window_results]
    is_sharpes = [r.is_summary.aggregate_sharpe for r in window_results]
    wfe_sharpe_values = [r.wfe_sharpe for r in window_results if r.wfe_sharpe is not None]

    oos_mean_sharpe = _mean(oos_sharpes) or Decimal("0")
    is_mean_sharpe = _mean(is_sharpes) or Decimal("0")
    mean_wfe = _mean(wfe_sharpe_values)
    windows_oos_profitable = sum(1 for r in oos_returns if r > 0)

    reasons: list[str] = []
    if mean_wfe is not None and mean_wfe < wfe_threshold:
        reasons.append(
            f"평균 WFE {mean_wfe} < 임계 {wfe_threshold} (표본 외 우위가 표본 내의 절반 미만)"
        )
    if is_mean_sharpe > 0 and oos_mean_sharpe <= 0:
        reasons.append(
            f"표본 내 샤프 평균 {is_mean_sharpe}(+)인데 표본 외 {oos_mean_sharpe}(≤0) "
            "— 표본 외에서 우위 소멸"
        )
    if window_results and windows_oos_profitable * 2 < len(window_results):
        reasons.append(
            f"표본 외 수익 윈도우 {windows_oos_profitable}/{len(window_results)} (과반 미만)"
        )

    # 스펙 027 — 표본 외 풀 트랙의 다중검정/유의성 통계.
    pooled = oos_pooled_returns or []
    oos_n_obs = len(pooled)
    oos_sharpe_annual = sharpe_ratio(pooled) if oos_n_obs >= 2 else None
    oos_skew = sample_skewness(pooled)
    oos_kurtosis = sample_kurtosis(pooled)
    oos_psr = probabilistic_sharpe_ratio(pooled) if oos_n_obs >= 2 else None
    oos_min_trl = minimum_track_record_length(pooled) if oos_n_obs >= 2 else None
    oos_sr0: Decimal | None = None
    oos_dsr: Decimal | None = None
    if num_trials > 1 and trial_sharpe_std_annual is not None:
        oos_sr0 = expected_max_sharpe(num_trials, trial_sharpe_std_annual)
        if oos_n_obs >= 2:
            oos_dsr = deflated_sharpe_ratio(
                pooled,
                num_trials=num_trials,
                trial_sharpe_std_annual=trial_sharpe_std_annual,
            )

    if min_psr is not None and oos_psr is not None and oos_psr < min_psr:
        reasons.append(
            f"표본 외 PSR {oos_psr} < 임계 {min_psr} "
            "(표본 외 샤프가 통계적으로 0 과 구별되지 않음)"
        )
    if min_dsr is not None and oos_dsr is not None and oos_dsr < min_dsr:
        reasons.append(
            f"표본 외 DSR {oos_dsr} < 임계 {min_dsr} "
            f"({num_trials}개 시도 다중검정 보정 후 우위 소멸)"
        )

    return WalkForwardReport(
        mode=mode,
        in_sample_days=in_sample_days,
        out_of_sample_days=out_of_sample_days,
        step_days=step_days,
        wfe_threshold=wfe_threshold,
        windows=window_results,
        oos_mean_return_pct=_mean(oos_returns) or Decimal("0"),
        oos_mean_sharpe=oos_mean_sharpe,
        oos_mean_sortino=_mean(oos_sortinos) or Decimal("0"),
        oos_worst_drawdown_pct=(
            Decimal(canonicalise_decimal(max(oos_drawdowns))) if oos_drawdowns else Decimal("0")
        ),
        is_mean_sharpe=is_mean_sharpe,
        mean_wfe_sharpe=mean_wfe,
        median_wfe_sharpe=_median(wfe_sharpe_values),
        windows_oos_profitable=windows_oos_profitable,
        overfit_suspected=bool(reasons),
        overfit_reasons=reasons,
        num_trials=num_trials,
        oos_n_obs=oos_n_obs,
        oos_sharpe_annual=oos_sharpe_annual,
        oos_skew=oos_skew,
        oos_kurtosis=oos_kurtosis,
        oos_psr=oos_psr,
        oos_min_track_record_obs=oos_min_trl,
        oos_expected_max_sharpe_annual=oos_sr0,
        oos_dsr=oos_dsr,
    )


# ---------- markdown rendering --------------------------------------------


def _fmt(value: Decimal | None) -> str:
    return "N/A" if value is None else canonicalise_decimal(value)


def render_walk_forward_report(report: WalkForwardReport) -> str:
    """Operator-facing markdown — same numbers as the dataclass, human-readable."""
    verdict = "⚠ 과적합 의심" if report.overfit_suspected else "✓ 표본 외 안정"
    lines = [
        "# 워크포워드 검증 (표본 외 과적합 탐지)",
        "",
        f"- 모드: {report.mode} (IS {report.in_sample_days}일 / OOS "
        f"{report.out_of_sample_days}일 / step {report.step_days}일)",
        f"- 윈도우 수: {len(report.windows)}",
        f"- WFE 임계: {canonicalise_decimal(report.wfe_threshold)}",
        f"- **판정: {verdict}**",
        "",
        "## 표본 외 집계 (정직한 헤드라인)",
        "",
        f"- 평균 수익률: {_fmt(report.oos_mean_return_pct)}%",
        f"- 평균 샤프: {_fmt(report.oos_mean_sharpe)}"
        f"  (표본 내 평균 {_fmt(report.is_mean_sharpe)})",
        f"- 평균 Sortino: {_fmt(report.oos_mean_sortino)}",
        f"- 최악 낙폭: {_fmt(report.oos_worst_drawdown_pct)}%",
        f"- 평균 WFE(샤프): {_fmt(report.mean_wfe_sharpe)}"
        f"  / 중앙값 {_fmt(report.median_wfe_sharpe)}",
        f"- 표본 외 수익 윈도우: {report.windows_oos_profitable}/{len(report.windows)}",
        "",
        "## 통계적 유의성 (다중검정 보정, 스펙 027)",
        "",
        f"- 표본 외 풀 관측 수: {report.oos_n_obs} (연율 샤프 {_fmt(report.oos_sharpe_annual)})",
        f"- 왜도: {_fmt(report.oos_skew)} / 첨도: {_fmt(report.oos_kurtosis)} (정규=3)",
        f"- 확률적 샤프(PSR, 참 샤프>0 확률): {_fmt(report.oos_psr)}",
        f"- 최소 트랙레코드 길이(95%): {_fmt(report.oos_min_track_record_obs)} 관측",
        f"- 시도 수(num_trials): {report.num_trials}"
        f"  / 기대 최대 샤프(SR_0): {_fmt(report.oos_expected_max_sharpe_annual)}",
        f"- **디플레이티드 샤프(DSR, 다중검정 보정): {_fmt(report.oos_dsr)}**",
        "",
    ]
    if report.overfit_reasons:
        lines.append("### 과적합 신호")
        lines.append("")
        lines.extend(f"- {r}" for r in report.overfit_reasons)
        lines.append("")
    lines.append("## 윈도우별")
    lines.append("")
    lines.append("| # | IS 기간 | OOS 기간 | IS 샤프 | OOS 샤프 | WFE | OOS 수익% |")
    lines.append("|---|---------|----------|---------|----------|-----|-----------|")
    for r in report.windows:
        w = r.window
        lines.append(
            f"| {w.index} | {w.is_start}~{w.is_end} | {w.oos_start}~{w.oos_end} "
            f"| {_fmt(r.is_summary.aggregate_sharpe)} | {_fmt(r.oos_summary.aggregate_sharpe)} "
            f"| {_fmt(r.wfe_sharpe)} | {_fmt(r.oos_summary.aggregate_return_pct)} |"
        )
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "DEFAULT_WFE_THRESHOLD",
    "WalkForwardError",
    "WalkForwardReport",
    "WalkForwardWindow",
    "WalkForwardWindowResult",
    "generate_windows",
    "render_walk_forward_report",
    "run_walk_forward",
]
