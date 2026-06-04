"""Spec 035 — forward 페이퍼 트랙의 엣지 자동 판정 (순수·결정론·읽기 전용).

이 프로젝트의 반복 결론은 "도구는 많은데 *실제로 돈을 버는지* 판정하는 폐회로가
끊겨 있다"는 것이다. 구체적으로:

  - 스펙 029 `compute_nav`(시가평가 순자산)와 `read_nav_points`(순자산 시계열)은
    만들어졌지만 어떤 실행 경로에도 안 꽂혀, NAV 시계열이 기록되지 않았다.
  - 스펙 027 디플레이티드 샤프(다중검정 보정)는 백테스트에만 연결돼, 현재 데이터
    forward 페이퍼 트랙에는 적용되지 않았다.

이 모듈은 그 둘을 잇는 마지막 조각이다 — 쌓인 NAV 시계열을 받아 **위험조정 성과를
단순 보유(buy-and-hold) 벤치마크와 비교**하고, **디플레이티드 샤프로 과적합/우연을
처벌**한 뒤, `EDGE_CONFIRMED / NO_EDGE / INSUFFICIENT_DATA` 한 줄 판정을 낸다.

설계 원칙 (스펙 011/027/029 와 동일):
  - 순수 함수. DB 를 직접 만지지 않는다 — CLI 계층이 NAV 점열·가격 바를 읽어 주입한다.
  - 단일 잣대(헌법 X.2): 총수익률·최대낙폭은 스펙 008 `backtest/metrics.py`, 샤프·PSR·
    DSR·MinTRL 은 스펙 027 `backtest/significance.py` 를 그대로 재사용한다. 백테스트·
    워크포워드·forward 트랙이 한 자로 잰다.
  - 보수적 fail-safe: 관측이 적거나(데이터 부족) 분산 0 이면 절대 EDGE 를 선언하지 않고
    INSUFFICIENT_DATA 로 강등한다. "모르면 엣지 없음으로 취급" = 돈을 잃지 않게 막는다.

이 판정은 **측정/분석 전용**이다. 주문 0건, 돈 0 이동, 라이브 자동 승격 0건. EDGE_CONFIRMED
는 운영자의 라이브 게이트(헌법 X.4)에 올릴 *증거*일 뿐, 자동 배포가 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from auto_invest.backtest.metrics import max_drawdown_pct, total_return_pct
from auto_invest.backtest.significance import significance_summary

# 판정 라벨 — 이 세 값만 난다.
EDGE_CONFIRMED = "EDGE_CONFIRMED"  # 단순 보유를 통계적으로(과적합 보정 후) 이긴다
NO_EDGE = "NO_EDGE"  # 충분히 쟀으나 우위가 우연과 구별되지 않는다
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # 아직 판정할 만큼 관측이 안 쌓였다

# 기본 임계치 — 운영자/CLI 가 덮어쓸 수 있다.
DEFAULT_MIN_OBS = 20  # NAV 점이 이보다 적으면 판정 보류(샤프가 통계적으로 무의미)
DEFAULT_DSR_THRESHOLD = Decimal("0.95")  # 디플레이티드/확률적 샤프 합격선
DEFAULT_CONFIDENCE = Decimal("0.95")  # MinTRL 신뢰수준


def daily_returns_from_curve(curve: list[Decimal]) -> list[Decimal]:
    """자산곡선(시점별 순자산) → 기간별 단순 수익률 r_t = v_t/v_{t-1} − 1.

    점이 2개 미만이거나 직전 값이 0 이하인 구간은 건너뛴다(0 나눗셈/비양수 방지).
    """
    rets: list[Decimal] = []
    for prev, cur in zip(curve, curve[1:], strict=False):
        if prev > 0:
            rets.append(cur / prev - Decimal("1"))
    return rets


_TRADING_DAYS_PER_YEAR = 252


def calmar_ratio(
    total_return_pct: Decimal | None,
    max_drawdown_pct: Decimal | None,
    *,
    n_obs: int,
    periods_per_year: int = _TRADING_DAYS_PER_YEAR,
) -> Decimal | None:
    """칼마 비율 = 연환산수익률(CAGR%) / 최대낙폭(%). 추세추종의 *자본 방어*를 포착한다.

    샤프는 변동성 대비 수익을 재지만, 추세추종의 핵심 가치는 *낙폭을 줄이는 것*이다. 같은
    샤프라도 낙폭이 작으면(현금으로 빠져 폭락 회피) 칼마가 높다 — "돈을 잃지 않는" 능력을
    직접 잰다(헌법 X). 낙폭 0(방어 완벽/무거래)·전손·기간 0 이면 None(정의 불가).
    """
    if total_return_pct is None or max_drawdown_pct is None or n_obs < 1:
        return None
    dd = abs(float(max_drawdown_pct))
    if dd <= 0.0:
        return None  # 낙폭 0 → 칼마 무한대(정의 불가). None 으로 정직히.
    tr = float(total_return_pct) / 100.0
    if tr <= -1.0:
        return None  # 전손(자본 ≤ 0) → CAGR 정의 불가.
    years = n_obs / periods_per_year
    if years <= 0.0:
        return None
    cagr = (1.0 + tr) ** (1.0 / years) - 1.0  # 비율
    return Decimal(str(round(cagr * 100.0 / dd, 6)))


def _bar_close_on_or_before(
    bars: list[tuple[date, Decimal]], target: date
) -> Decimal | None:
    """target 일자 이하의 가장 최근 종가. bars 는 (일자, 종가) 오름차순."""
    chosen: Decimal | None = None
    for d, close in bars:
        if d <= target and close > 0:
            chosen = close
        elif d > target:
            break
    return chosen


def equal_weight_buy_hold_curve(
    nav_dates: list[date],
    bars_by_symbol: dict[str, list[tuple[date, Decimal]]],
    *,
    capital: Decimal = Decimal("100000"),
) -> list[Decimal] | None:
    """같은 일자 격자에서 유니버스 전체를 균등가중으로 사서 들고 있는 벤치마크 곡선.

    스펙 032 `_benchmark_equity_curve` 와 같은 잣대 — 첫 일자에 각 종목을 동일 금액으로
    사서(정수 주 floor) 끝까지 보유(재조정·비용 0), 매 일자 시가평가한다. "능동 선택·
    재조정이 그냥 바스켓을 든 것보다 나았나?"의 대조군이다.

    한 종목이라도 첫 일자에 가격이 없으면 그 종목은 빠진다. 가격 있는 종목이 0이면 None
    (벤치마크 구성 불가 — 판정은 strategy-only 로 강등된다).
    """
    if len(nav_dates) < 2:
        return None
    first = nav_dates[0]
    first_prices: dict[str, Decimal] = {}
    for sym, bars in bars_by_symbol.items():
        px = _bar_close_on_or_before(bars, first)
        if px is not None and px > 0:
            first_prices[sym] = px
    if not first_prices:
        return None
    per_name = capital / Decimal(len(first_prices))
    qty: dict[str, int] = {
        s: int(per_name / p) for s, p in first_prices.items() if per_name >= p
    }
    qty = {s: q for s, q in qty.items() if q > 0}
    if not qty:
        return None
    spent = sum((Decimal(q) * first_prices[s] for s, q in qty.items()), Decimal("0"))
    cash = capital - spent
    last_price = {s: first_prices[s] for s in qty}
    curve: list[Decimal] = []
    for d in nav_dates:
        for s in qty:
            px = _bar_close_on_or_before(bars_by_symbol.get(s, []), d)
            if px is not None and px > 0:
                last_price[s] = px
        mv = sum((Decimal(qty[s]) * last_price[s] for s in qty), Decimal("0"))
        curve.append(cash + mv)
    return curve


@dataclass(frozen=True)
class EdgeVerdict:
    """forward 트랙의 엣지 판정 — 운영자 라이브 게이트(헌법 X.4)에 올릴 증거."""

    verdict: str  # EDGE_CONFIRMED | NO_EDGE | INSUFFICIENT_DATA
    reason: str
    n_obs: int  # 수익률 관측 수 (NAV 점 − 1)
    min_obs_required: int
    strategy_sharpe_annual: Decimal | None
    strategy_total_return_pct: Decimal | None
    strategy_max_drawdown_pct: Decimal | None
    benchmark_sharpe_annual: Decimal | None
    benchmark_total_return_pct: Decimal | None
    benchmark_max_drawdown_pct: Decimal | None
    excess_return_pct: Decimal | None  # 전략 − 벤치마크 총수익률
    psr_vs_benchmark: Decimal | None  # 참 샤프가 벤치마크 샤프보다 클 확률(PSR)
    dsr: Decimal | None  # 다중검정 보정 디플레이티드 샤프(과적합 처벌)
    num_trials: int
    min_track_record_obs: Decimal | None
    dsr_threshold: Decimal
    has_benchmark: bool
    # 스펙 038 — 칼마(연수익/최대낙폭): 추세추종의 자본 방어를 포착하는 지표.
    strategy_calmar: Decimal | None = None
    benchmark_calmar: Decimal | None = None
    beats_benchmark_calmar: bool = False

    SCHEMA_VERSION = "1.1"

    def to_json_dict(self) -> dict:
        def _s(v: Decimal | None) -> str | None:
            return None if v is None else str(v)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "verdict": self.verdict,
            "reason": self.reason,
            "n_obs": self.n_obs,
            "min_obs_required": self.min_obs_required,
            "strategy_sharpe_annual": _s(self.strategy_sharpe_annual),
            "strategy_total_return_pct": _s(self.strategy_total_return_pct),
            "strategy_max_drawdown_pct": _s(self.strategy_max_drawdown_pct),
            "strategy_calmar": _s(self.strategy_calmar),
            "benchmark_sharpe_annual": _s(self.benchmark_sharpe_annual),
            "benchmark_total_return_pct": _s(self.benchmark_total_return_pct),
            "benchmark_max_drawdown_pct": _s(self.benchmark_max_drawdown_pct),
            "benchmark_calmar": _s(self.benchmark_calmar),
            "excess_return_pct": _s(self.excess_return_pct),
            "beats_benchmark_calmar": self.beats_benchmark_calmar,
            "psr_vs_benchmark": _s(self.psr_vs_benchmark),
            "dsr": _s(self.dsr),
            "num_trials": self.num_trials,
            "min_track_record_obs": _s(self.min_track_record_obs),
            "dsr_threshold": str(self.dsr_threshold),
            "has_benchmark": self.has_benchmark,
        }


def _insufficient(
    reason: str,
    *,
    n_obs: int,
    min_obs: int,
    num_trials: int,
    dsr_threshold: Decimal,
    strat_return: Decimal | None = None,
    strat_dd: Decimal | None = None,
) -> EdgeVerdict:
    return EdgeVerdict(
        verdict=INSUFFICIENT_DATA,
        reason=reason,
        n_obs=n_obs,
        min_obs_required=min_obs,
        strategy_sharpe_annual=None,
        strategy_total_return_pct=strat_return,
        strategy_max_drawdown_pct=strat_dd,
        benchmark_sharpe_annual=None,
        benchmark_total_return_pct=None,
        benchmark_max_drawdown_pct=None,
        excess_return_pct=None,
        psr_vs_benchmark=None,
        dsr=None,
        num_trials=num_trials,
        min_track_record_obs=None,
        dsr_threshold=dsr_threshold,
        has_benchmark=False,
    )


def forward_edge_verdict(
    nav_curve: list[Decimal],
    benchmark_curve: list[Decimal] | None,
    *,
    num_trials: int = 1,
    trial_sharpe_std_annual: Decimal | float | int | None = None,
    min_obs: int = DEFAULT_MIN_OBS,
    dsr_threshold: Decimal = DEFAULT_DSR_THRESHOLD,
    confidence: Decimal = DEFAULT_CONFIDENCE,
) -> EdgeVerdict:
    """NAV 자산곡선(+옵션 벤치마크) → 엣지 판정. 결정론·순수.

    판정 규칙 (전부 만족해야 EDGE_CONFIRMED):
      1. 관측 충분: n_obs ≥ min_obs (아니면 INSUFFICIENT_DATA).
      2. 단순 보유를 이긴다: 초과수익 > 0 **그리고** 전략 샤프 > 벤치마크 샤프.
      3. 우연이 아니다: PSR(벤치마크 샤프 기준) ≥ 임계치.
      4. 과적합이 아니다: num_trials>1 이면 DSR ≥ 임계치(다중검정 보정).
    벤치마크가 없으면(가격 바 부족) 2의 '벤치마크 이김' 대신 PSR(0 기준)으로 강등하되,
    그래도 통계가 안 서면 INSUFFICIENT_DATA. 보수적으로 — 모르면 EDGE 선언 금지.
    """
    strat_rets = daily_returns_from_curve(nav_curve)
    n_obs = len(strat_rets)
    has_benchmark = benchmark_curve is not None and len(benchmark_curve) >= 2

    # 전략 곡선의 총수익·낙폭 (양수 곡선일 때만 — metrics 계약과 동일).
    strat_return = (
        total_return_pct(nav_curve) if len(nav_curve) >= 2 and nav_curve[0] > 0 else None
    )
    strat_dd = (
        max_drawdown_pct(nav_curve) if nav_curve and all(v > 0 for v in nav_curve) else None
    )

    if n_obs < min_obs:
        return _insufficient(
            f"관측 {n_obs}개 < 최소 {min_obs}개 — 샤프가 통계적으로 무의미",
            n_obs=n_obs,
            min_obs=min_obs,
            num_trials=num_trials,
            dsr_threshold=dsr_threshold,
            strat_return=strat_return,
            strat_dd=strat_dd,
        )

    # 벤치마크 샤프·수익 — 같은 잣대(significance/metrics)로.
    bench_sharpe: Decimal | None = None
    bench_return: Decimal | None = None
    bench_dd: Decimal | None = None
    if has_benchmark:
        bench_rets = daily_returns_from_curve(benchmark_curve)  # type: ignore[arg-type]
        bench_sig = significance_summary(bench_rets) if bench_rets else None
        if bench_sig is not None:
            bench_sharpe = bench_sig.sharpe_annual
        if benchmark_curve and benchmark_curve[0] > 0:  # type: ignore[index]
            bench_return = total_return_pct(benchmark_curve)  # type: ignore[arg-type]
        if benchmark_curve and all(v > 0 for v in benchmark_curve):  # type: ignore[union-attr]
            bench_dd = max_drawdown_pct(benchmark_curve)  # type: ignore[arg-type]

    benchmark_sharpe_for_psr = bench_sharpe if bench_sharpe is not None else Decimal("0")

    sig = significance_summary(
        strat_rets,
        num_trials=num_trials,
        trial_sharpe_std_annual=trial_sharpe_std_annual,
        benchmark_sharpe_annual=benchmark_sharpe_for_psr,
        confidence=confidence,
    )
    if sig is None:
        # 분산 0 등 — 통계 불가. 보수적으로 데이터 부족 취급.
        return _insufficient(
            "수익률 분산이 0이거나 통계 계산 불가 — 판정 보류",
            n_obs=n_obs,
            min_obs=min_obs,
            num_trials=num_trials,
            dsr_threshold=dsr_threshold,
            strat_return=strat_return,
            strat_dd=strat_dd,
        )

    strat_sharpe = sig.sharpe_annual
    psr = sig.psr  # significance_summary 가 benchmark_sharpe_annual 기준으로 이미 계산
    dsr = sig.dsr  # num_trials>1 일 때만 채워짐
    excess = (
        (strat_return - bench_return)
        if (strat_return is not None and bench_return is not None)
        else None
    )

    # ---- 판정 ----
    beats_benchmark = (
        has_benchmark
        and bench_sharpe is not None
        and strat_sharpe > bench_sharpe
        and (excess is None or excess > 0)
    )
    psr_ok = psr is not None and psr >= dsr_threshold
    dsr_ok = num_trials <= 1 or (dsr is not None and dsr >= dsr_threshold)

    # 스펙 038 — 칼마(자본 방어). 추세추종은 낙폭을 줄여 가치를 더하므로, 샤프가
    # 비등해도 칼마가 높을 수 있다. 게이트는 통계적으로 엄격한 샤프 기준을 유지하되,
    # 칼마 우위는 *보고*해 운영자가 드로다운 방어를 직접 보게 한다(게이트 약화 없음).
    strat_calmar = calmar_ratio(strat_return, strat_dd, n_obs=n_obs)
    bench_calmar = (
        calmar_ratio(bench_return, bench_dd, n_obs=n_obs) if has_benchmark else None
    )
    beats_calmar = (
        strat_calmar is not None
        and bench_calmar is not None
        and strat_calmar > bench_calmar
    )

    if has_benchmark:
        if beats_benchmark and psr_ok and dsr_ok:
            verdict = EDGE_CONFIRMED
            reason = (
                f"단순 보유 대비 위험조정 우위(전략 샤프 {strat_sharpe} > 벤치 "
                f"{bench_sharpe}, 초과수익 {excess}%)이며 우연/과적합과 구별됨"
                f"(PSR {psr} ≥ {dsr_threshold}"
                + (f", DSR {dsr} ≥ {dsr_threshold}" if num_trials > 1 else "")
                + ")"
            )
        else:
            verdict = NO_EDGE
            bits = []
            if not beats_benchmark:
                bits.append("단순 보유를 위험조정으로 못 이김")
            if not psr_ok:
                bits.append(f"PSR {psr} < {dsr_threshold}(우연과 구별 안 됨)")
            if not dsr_ok:
                bits.append(f"DSR {dsr} < {dsr_threshold}(과적합 보정 후 붕괴)")
            reason = "; ".join(bits) or "우위 없음"
        # 칼마(자본 방어) 정보 — 게이트와 별개로 운영자에게 가시화.
        if beats_calmar:
            reason += (
                f" [단, 칼마 우위: 전략 {strat_calmar} > 벤치 {bench_calmar}"
                " — 드로다운 방어는 더 나음]"
            )
    else:
        # 벤치마크 없음 — PSR(0 기준)으로 "양의 위험조정 수익"만 약하게 판정.
        if psr_ok and dsr_ok and strat_sharpe > 0:
            verdict = EDGE_CONFIRMED
            reason = (
                f"양의 위험조정 수익(전략 샤프 {strat_sharpe})이 우연과 구별됨"
                f"(PSR {psr} ≥ {dsr_threshold}) — 단, 벤치마크 비교 없음(가격 바 부족)"
            )
        else:
            verdict = NO_EDGE
            reason = (
                f"벤치마크 비교 불가 + PSR {psr} < {dsr_threshold} 또는 샤프≤0 — "
                "양의 위험조정 우위 미확인"
            )

    return EdgeVerdict(
        verdict=verdict,
        reason=reason,
        n_obs=n_obs,
        min_obs_required=min_obs,
        strategy_sharpe_annual=strat_sharpe,
        strategy_total_return_pct=strat_return,
        strategy_max_drawdown_pct=strat_dd,
        benchmark_sharpe_annual=bench_sharpe,
        benchmark_total_return_pct=bench_return,
        benchmark_max_drawdown_pct=bench_dd,
        excess_return_pct=excess,
        psr_vs_benchmark=psr,
        dsr=dsr,
        num_trials=num_trials,
        min_track_record_obs=sig.min_track_record_obs,
        dsr_threshold=dsr_threshold,
        has_benchmark=has_benchmark,
        strategy_calmar=strat_calmar,
        benchmark_calmar=bench_calmar,
        beats_benchmark_calmar=beats_calmar,
    )


def render_text(v: EdgeVerdict) -> str:
    """사람용 판정 요약 — CLI text 모드."""

    def _p(x: Decimal | None) -> str:
        return "N/A" if x is None else f"{x}"

    icon = {EDGE_CONFIRMED: "✅", NO_EDGE: "❌", INSUFFICIENT_DATA: "⏳"}.get(
        v.verdict, "?"
    )
    lines = [
        "=" * 60,
        f"forward 엣지 판정: {icon} {v.verdict}",
        "=" * 60,
        f"사유          : {v.reason}",
        f"관측 수       : {v.n_obs} (최소 {v.min_obs_required})",
        f"전략 샤프(연) : {_p(v.strategy_sharpe_annual)}",
        f"전략 총수익%  : {_p(v.strategy_total_return_pct)}",
        f"전략 최대낙폭%: {_p(v.strategy_max_drawdown_pct)}",
        f"전략 칼마     : {_p(v.strategy_calmar)} (연수익/최대낙폭 — 자본 방어)",
    ]
    if v.has_benchmark:
        lines += [
            f"벤치 샤프(연) : {_p(v.benchmark_sharpe_annual)}",
            f"벤치 총수익%  : {_p(v.benchmark_total_return_pct)}",
            f"벤치 칼마     : {_p(v.benchmark_calmar)}",
            f"초과수익%     : {_p(v.excess_return_pct)}",
            f"칼마 우위     : {'예 ✅' if v.beats_benchmark_calmar else '아니오'}",
        ]
    else:
        lines.append("벤치마크      : (가격 바 부족 — 비교 없음)")
    lines += [
        f"PSR(벤치 기준): {_p(v.psr_vs_benchmark)}",
        f"DSR(시도 {v.num_trials}): {_p(v.dsr)}",
        f"MinTRL(관측)  : {_p(v.min_track_record_obs)}",
        "",
        "측정/분석 전용 — 주문 0건, 돈 0 이동. EDGE_CONFIRMED 는 운영자 라이브",
        "게이트(헌법 X.4)에 올릴 증거이지 자동 배포가 아니다.",
    ]
    return "\n".join(lines)
