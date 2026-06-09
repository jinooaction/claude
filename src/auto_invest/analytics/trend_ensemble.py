"""스펙 048 — 다중 추세 속도 앙상블: 단일 SMA 대신 여러 속도의 추세 신호를 합친다.

배경(우선순위 판단):
  - 검증된 엣지(스펙 042~047) = 추세추종의 자본 방어를 비상관 자산(주식·채권·금)에 분산하고
    위험으로 사이징(역변동성)한 것. 모든 구간 낙폭 ~5%·샤프 ~1.8.
  - 그러나 각 자산의 추세 게이트는 *단일 속도*(10개월 SMA)다. 단일 속도는 한 임계 근처에서
    가격이 오르내릴 때 잦은 진입/이탈(휩쏘)을 일으킨다 — 한 파라미터에 운명을 건다.

세계 최고 수준 managed futures(AQR "A Century of Evidence on Trend-Following"; Man-AHL)는
*여러 추세 속도*(빠름·중간·느림)를 합쳐 신호를 만든다. 신호 속도 자체를 분산하면 한 속도의
휩쏘가 다른 속도로 상쇄돼 더 매끄럽고 견고하다. 이 모듈은 그 다중 속도 앙상블을 우리 검증된
3자산 위험관리 추세에 얹어 *위험조정 수익(샤프·칼마·낙폭)*이 개선되는지 정직하게 잰다.

핵심 설계 — *분수 노출*:
  단일 속도는 이진(투자 1 / 현금 0)이다. 앙상블은 N개 속도 중 추세 위인 비율(0, 1/N, …, 1)
  만큼 자산에 노출하고 나머지는 현금. 예: 3속도 중 2개가 추세 위면 2/3 자산 + 1/3 현금. 이는
  "추세가 강하게 합의될수록 더 노출"하는 점진 게이트라 단일 속도의 절벽(0↔1)을 부드럽게 한다.

이 모듈은 순수·결정론·비커널이다. 주문 0건, 돈 0 이동(연구/측정 전용). 미래 누출 없음:
period t 의 분수는 t-1 까지의 가격만 쓴다(각 SMA 도 동일).
"""

from __future__ import annotations

from dataclasses import dataclass

from auto_invest.analytics.global_trend import (
    _cum_levels,
    _trailing_vol,
    align_gold_levels,  # re-export 편의(probe 에서 사용)
    gold_total_return_factors,
)
from auto_invest.analytics.multi_asset_trend import (
    DEFAULT_BOND_MATURITY_YEARS,
    bond_total_return_factors,
)
from auto_invest.analytics.risk_managed_beta import (
    LegStats,
    MonthlyRow,
    cash_factors,
    market_total_return_factors,
    summarize,
)

DEFAULT_ENSEMBLE_WINDOWS = (6, 10, 12)
DEFAULT_SINGLE_WINDOW = 10


# ─────────────────────────── 다중 속도 분수 신호 ───────────────────────────


def ensemble_in_fraction(levels: list[float], windows: tuple[int, ...]) -> list[float]:
    """레벨 시계열에 대해 각 기간(k-1→k)에서 *추세 위인 속도의 비율*(0..1), 길이 M-1.

    각 window w 에 대해 levels[k-1] > SMA(levels[k-w:k]) 이면 1(아직 SMA 부족하면 1=투자,
    단일 속도 규칙과 동일). 그 평균이 분수 노출이다. windows=(10,) 이면 단일 속도와 동일.
    미래 누출 없음: k 기간은 levels[:k] 만 본다.
    """
    if not windows or any(w < 1 for w in windows):
        raise ValueError("windows must be non-empty and >= 1")
    out: list[float] = []
    for k in range(1, len(levels)):
        hits = 0
        for w in windows:
            if k < w:
                hits += 1  # SMA 미정 → 투자(단일 속도와 동일 규칙)
                continue
            sma = sum(levels[k - w:k]) / w
            if levels[k - 1] > sma:
                hits += 1
        out.append(hits / len(windows))
    return out


def ensemble_sleeve_factors(
    asset: list[float], cash: list[float], fraction: list[float]
) -> list[float]:
    """분수 노출 슬리브 팩터: fraction 만큼 자산, 나머지는 현금(매월 재조정).

    factor_t = fraction_t * asset_t + (1 - fraction_t) * cash_t.
    fraction ∈ {0,1} 이면 이진 게이트(단일 속도)와 동일.
    """
    if not (len(asset) == len(cash) == len(fraction)):
        raise ValueError("length mismatch")
    return [
        fr * a + (1.0 - fr) * c
        for a, c, fr in zip(asset, cash, fraction, strict=True)
    ]


def _build_ensemble_sleeves(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    windows: tuple[int, ...],
    bond_maturity_years: int,
) -> tuple[list[float], list[float], list[float]]:
    """주식·채권·금 *앙상블* 추세 슬리브 팩터(각 길이 N-1)."""
    eq_market = market_total_return_factors(rows)
    cash = cash_factors(rows)
    bond = bond_total_return_factors(rows, maturity_years=bond_maturity_years)
    gold = gold_total_return_factors(gold_levels)

    eq_prices = [r.price for r in rows]
    bond_index = _cum_levels(bond)
    # 금 레벨은 그대로 추세 판단(gold_levels 길이 N).
    eq_frac = ensemble_in_fraction(eq_prices, windows)
    bond_frac = ensemble_in_fraction(bond_index, windows)
    gold_frac = ensemble_in_fraction(gold_levels, windows)

    return (
        ensemble_sleeve_factors(eq_market, cash, eq_frac),
        ensemble_sleeve_factors(bond, cash, bond_frac),
        ensemble_sleeve_factors(gold, cash, gold_frac),
    )


def _risk_parity_combine(
    sleeves: list[list[float]], *, vol_window: int = 12
) -> list[float]:
    """여러 슬리브를 매월 트레일링 역변동성으로 가중한 혼합 팩터(길이 = 슬리브 길이).

    스펙 047 risk_parity_global_factors 와 같은 원칙(변동성 큰 슬리브에 작은 비중). 이력
    부족이면 균등. 미래 누출 0: period t 가중치는 t 이전 수익의 트레일링 변동성만 쓴다.
    """
    n = len(sleeves[0])
    if any(len(s) != n for s in sleeves):
        raise ValueError("sleeve length mismatch")
    m = len(sleeves)
    rets = [[f - 1.0 for f in s] for s in sleeves]
    out: list[float] = []
    for t in range(n):
        vols = [_trailing_vol(r, t, vol_window) for r in rets]
        if any(v is None or v <= 0 for v in vols):
            w = [1.0 / m] * m
        else:
            inv = [1.0 / v for v in vols]  # type: ignore[arg-type]
            s = sum(inv)
            w = [i / s for i in inv]
        out.append(sum(w[i] * sleeves[i][t] for i in range(m)))
    return out


# ─────────────────────────── 단일 vs 앙상블 비교 ───────────────────────────


@dataclass(frozen=True)
class TrendEnsembleComparison:
    """단일 속도 vs 다중 속도 앙상블(둘 다 3자산 역변동성) — 앙상블이 가치를 더하는가."""

    single_window: int
    ensemble_windows: tuple[int, ...]
    single_speed: LegStats  # 3자산 역변동성, 단일 속도(스펙 047)
    ensemble: LegStats  # 3자산 역변동성, 다중 속도(스펙 048 후보)
    verdict: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "single_window": self.single_window,
            "ensemble_windows": list(self.ensemble_windows),
            "verdict": self.verdict,
            "reason": self.reason,
            "single_speed": self.single_speed.as_dict(),
            "ensemble": self.ensemble.as_dict(),
        }


def _classify_ensemble(single: LegStats, ensemble: LegStats) -> tuple[str, str]:
    """앙상블이 단일 속도 대비 *위험조정으로* 가치를 더하는가(사전 등록 기준).

    샤프↑ + 칼마↑ + 최대낙폭 비악화면 TREND_ENSEMBLE_EDGE. 스펙 043/047 과 같은 잣대.
    """
    if single.calmar is None or ensemble.calmar is None:
        return "INSUFFICIENT", "칼마 정의 불가(낙폭 0 또는 데이터 부족)"
    sharpe_up = ensemble.sharpe > single.sharpe
    calmar_up = ensemble.calmar > single.calmar
    dd_ok = ensemble.max_dd_pct <= single.max_dd_pct * 1.001
    detail = (
        f"샤프 {single.sharpe:.2f}→{ensemble.sharpe:.2f}, "
        f"칼마 {single.calmar:.2f}→{ensemble.calmar:.2f}, "
        f"낙폭 {single.max_dd_pct:.1f}%→{ensemble.max_dd_pct:.1f}%"
    )
    if sharpe_up and calmar_up and dd_ok:
        return "TREND_ENSEMBLE_EDGE", detail
    fails = []
    if not sharpe_up:
        fails.append("샤프 개선 없음")
    if not calmar_up:
        fails.append("칼마 개선 없음")
    if not dd_ok:
        fails.append("낙폭 악화")
    return "NO_ENSEMBLE_BENEFIT", "; ".join(fails) + f"; {detail}"


def compare_trend_ensemble(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    single_window: int = DEFAULT_SINGLE_WINDOW,
    ensemble_windows: tuple[int, ...] = DEFAULT_ENSEMBLE_WINDOWS,
    vol_window: int = 12,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
) -> TrendEnsembleComparison:
    """3자산 역변동성에서 단일 속도(single_window) vs 다중 속도(ensemble_windows) 비교.

    공정 비교를 위해 단일 속도도 같은 앙상블 경로로 만든다(windows=(single_window,)) → 같은
    역변동성 결합·같은 코드 경로, 차이는 *속도 다발*뿐.
    """
    single_sleeves = _build_ensemble_sleeves(
        rows, gold_levels, (single_window,), bond_maturity_years
    )
    ens_sleeves = _build_ensemble_sleeves(
        rows, gold_levels, ensemble_windows, bond_maturity_years
    )
    single_factors = _risk_parity_combine(single_sleeves, vol_window=vol_window)
    ens_factors = _risk_parity_combine(ens_sleeves, vol_window=vol_window)
    leg_single = summarize(single_factors, in_market=None)
    leg_ens = summarize(ens_factors, in_market=None)
    verdict, reason = _classify_ensemble(leg_single, leg_ens)
    return TrendEnsembleComparison(
        single_window=single_window,
        ensemble_windows=ensemble_windows,
        single_speed=leg_single,
        ensemble=leg_ens,
        verdict=verdict,
        reason=reason,
    )


def ensemble_global_factors(
    rows: list[MonthlyRow],
    gold_levels: list[float],
    *,
    ensemble_windows: tuple[int, ...] = DEFAULT_ENSEMBLE_WINDOWS,
    vol_window: int = 12,
    bond_maturity_years: int = DEFAULT_BOND_MATURITY_YEARS,
) -> list[float]:
    """다중 속도 앙상블 3자산 역변동성 월간 팩터 스트림(길이 N-1) — 레버리지 분석용."""
    sleeves = _build_ensemble_sleeves(
        rows, gold_levels, ensemble_windows, bond_maturity_years
    )
    return _risk_parity_combine(sleeves, vol_window=vol_window)


__all__ = [
    "DEFAULT_ENSEMBLE_WINDOWS",
    "DEFAULT_SINGLE_WINDOW",
    "TrendEnsembleComparison",
    "align_gold_levels",
    "compare_trend_ensemble",
    "ensemble_global_factors",
    "ensemble_in_fraction",
    "ensemble_sleeve_factors",
]
