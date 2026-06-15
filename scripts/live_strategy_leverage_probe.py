"""스펙 044×047 — 라이브 전략(3자산 역변동성 추세)의 낙폭 예산 내 성장 최적 레버리지.

스펙 047 후속 깊은 OOS 검사가 라이브 GLOBAL-TREND(SPY·IEF·GLD 역변동성 추세)의 강건한
엣지를 입증했다(1971~ 샤프 1.81·최대낙폭 5.3%). 그 발견의 직접적인 "진짜 돈" 귀결:
**낙폭이 낮은 전략은 같은 낙폭 예산에서 더 큰 레버리지를 안전하게 얹어 복리 성장을 키울 수
있다**(스펙 044). 이 probe 는 라이브 전략을 운영자 낙폭 예산(헌법 X.4 기본 20%)으로 레버리지
최적화하고, 2자산·단일 주식과 *같은 예산에서* 비교한다 — 낮은 낙폭의 3자산이 레버리지 여유가
가장 커서 같은 위험에서 가장 높은 복리를 낸다는 것을 정량화.

기존 `growth_optimal_probe.py`(스펙 044)는 2자산까지만·30% 예산이었다. 이 probe 는 **금을
포함한 라이브 3자산**을 **운영자 실제 예산**으로 처음 정량화한다.

데이터: GitHub Shiller(주식·채권 1871~) + gold-prices(금 1833~). 읽기 전용 — 주문 0·돈 0
이동. **레버리지는 연구/페이퍼 측정 전용**(라이브 K1 포지션 캡 불변, 헌법 I-VII). 라이브
레버리지·자본 사이징은 별도 운영자 게이트(헌법 X.4).

사용: uv run python scripts/live_strategy_leverage_probe.py
      [--from-year 1971] [--window 10] [--dd-budget 20] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.global_trend import (
    GOLD_FLOAT_YEAR,
    align_gold_levels,
    global_trend_factors,
    parse_gold,
    risk_parity_global_factors,
)
from auto_invest.analytics.growth_optimal import (
    drawdown_constrained_optimal,
    growth_curve,
    growth_optimal,
    leverage_headroom,
    rank_leverage_headroom,
    risk_free_monthly,
)
from auto_invest.analytics.multi_asset_trend import (
    diversified_trend_factors,
    equity_trend_factors,
)
from auto_invest.analytics.risk_managed_beta import parse_shiller

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"

# 0.25 간격의 촘촘한 격자(낮은 낙폭 전략은 최적 레버리지가 높을 수 있어 6배까지).
_LEVERAGES = [round(0.5 + 0.25 * i, 2) for i in range(23)]  # 0.5 … 6.0

_LIVE_KEY = "3자산 역변동성 +금 (라이브)"


def _strategies(rows, gold_levels, window: int) -> list[tuple[str, list[float]]]:
    """레버리지 비교 대상 전략들의 월간 팩터 스트림(낮은 낙폭 순으로 의미 부여)."""
    return [
        ("단일 주식 추세 (042)", equity_trend_factors(rows, window=window)),
        ("2자산 분산 추세 (043)", diversified_trend_factors(rows, window=window)),
        (
            "3자산 고정가중 +금 (047)",
            global_trend_factors(rows, gold_levels, window=window),
        ),
        (_LIVE_KEY, risk_parity_global_factors(rows, gold_levels, window=window)),
    ]


def _print_live_curve(label: str, curve, dd_budget: float) -> None:
    opt = growth_optimal(curve)
    print(f"\n{'=' * 72}\n[{label}] 레버리지별 복리 성장 (CAGR hump)")
    print(f"{'레버':>5} {'CAGR%':>8} {'변동%':>7} {'샤프':>6} {'최대낙폭%':>9} {'칼마':>6}")
    print("-" * 52)
    dd_opt = drawdown_constrained_optimal(curve, max_dd_pct=dd_budget)
    for p in curve:
        mark = ""
        if dd_opt and p.leverage == dd_opt.leverage:
            mark += f"  ← 낙폭≤{dd_budget:.0f}% 최적"
        if p.leverage == opt.leverage:
            mark += "  ← CAGR 최대(풀켈리, 과격)"
        # 격자가 촘촘하니 핵심 배수만 출력.
        if abs((p.leverage * 4) - round(p.leverage * 4)) < 1e-9 and (
            p.leverage in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0)
            or mark
        ):
            print(
                f"{p.leverage:>5.2f} {p.cagr_pct:>8.2f} {p.vol_pct:>7.2f} "
                f"{p.sharpe:>6.2f} {p.max_dd_pct:>9.1f} {(p.calmar or 0):>6.2f}{mark}"
            )


def _run(all_rows, gold_by_month, *, from_year: int, window: int, dd_budget: float) -> dict:
    rows = [r for r in all_rows if int(r.date[:4]) >= from_year]
    gold_levels = align_gold_levels(rows, gold_by_month)
    rf = risk_free_monthly(rows)

    strategies = _strategies(rows, gold_levels, window)
    headrooms = [
        leverage_headroom(
            label, factors, rf, leverages=_LEVERAGES, max_dd_budget_pct=dd_budget
        )
        for label, factors in strategies
    ]

    # 라이브 전략 곡선 상세(hump + 두 최적점).
    live_factors = dict(strategies)[_LIVE_KEY]
    live_curve = growth_curve(live_factors, rf, leverages=_LEVERAGES)
    _print_live_curve(_LIVE_KEY, live_curve, dd_budget)

    # 같은 낙폭 예산에서 전 전략 비교(낮은 낙폭이 레버리지 여유↑ → 복리↑).
    print(
        f"\n{'=' * 72}\n같은 낙폭 예산({dd_budget:.0f}%)에서 전략별 레버리지 최적 "
        f"({from_year}~, {len(rows)}개월)"
    )
    print(
        f"{'전략':<26} {'무레버 낙폭':>9} {'무레버 CAGR':>10} "
        f"{'최적 레버':>8} {'레버 후 CAGR':>11} {'레버 후 낙폭':>11} {'복리 상승':>9}"
    )
    print("-" * 92)
    ranked = rank_leverage_headroom(headrooms)
    for h in ranked:
        u = h.unlevered
        if h.dd_optimal is None:
            print(
                f"{h.label:<26} {u.max_dd_pct:>8.1f}% {u.cagr_pct:>9.1f}% "
                f"{'없음(L=1 초과)':>8}"
            )
            continue
        d = h.dd_optimal
        print(
            f"{h.label:<26} {u.max_dd_pct:>8.1f}% {u.cagr_pct:>9.1f}% "
            f"{d.leverage:>7.2f}x {d.cagr_pct:>10.1f}% {d.max_dd_pct:>10.1f}% "
            f"{h.cagr_uplift_pct:>+8.1f}p"
        )
    print("-" * 92)
    best = ranked[0]
    live = next((h for h in ranked if h.label == _LIVE_KEY), None)
    if best.dd_optimal is not None:
        print(
            f"\n결론: 같은 {dd_budget:.0f}% 낙폭 예산에서 *레버리지 후 복리* 1위는 '{best.label}'"
            f" — L={best.dd_optimal.leverage:.2f}배, CAGR {best.dd_optimal.cagr_pct:.1f}%"
            f"(무레버리지 {best.unlevered.cagr_pct:.1f}% 대비 +{best.cagr_uplift_pct:.1f}%p)."
        )
        if live is not None and live.dd_optimal is not None and live.label != best.label:
            print(
                f"  ※ 미묘함(정직): 라이브 '{_LIVE_KEY}'는 무레버리지 낙폭이 가장 낮아"
                f"(L={live.dd_optimal.leverage:.2f}로 레버리지 *여유*는 가장 크지만), 변동성을"
                f" 너무 낮춰 기저 수익이 낮고 레버리지 시 낙폭이 초선형으로 커져 *레버리지 후"
                f" 복리*는 {live.dd_optimal.cagr_pct:.1f}%로 더 낮다. = 낮은 낙폭이 곧 높은"
                " 레버리지 후 복리는 아니다(레버리지 여유 ≠ 돈). 무레버리지 안전성과 레버리지 후"
                " 복리는 다른 축 — 어느 변이를 라이브로 둘지는 운영자 판단(헌법 X.4)."
            )
    print(
        "\n주의: 레버리지는 연구/페이퍼 측정 전용. 라이브 K1 포지션 캡 불변(헌법 I-VII)."
        " 실제 라이브 레버리지·자본 사이징은 운영자 게이트(헌법 X.4) — 이 수치는 '안전 여유가"
        " 얼마인가'를 보일 뿐 자동 적용하지 않는다."
    )
    return {
        "schema_version": "1.0",
        "from_year": from_year,
        "n_months": len(rows),
        "window": window,
        "max_dd_budget_pct": dd_budget,
        "best_label": best.label,
        "ranked": [h.as_dict() for h in ranked],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--from-year", type=int, default=GOLD_FLOAT_YEAR,
        help=f"시작 연도(기본 {GOLD_FLOAT_YEAR}=금 자유변동 — 정직한 핵심).",
    )
    ap.add_argument("--window", type=int, default=10, help="추세 SMA 개월(고전 10).")
    ap.add_argument(
        "--dd-budget", type=float, default=20.0,
        help="감내 최대낙폭(%) 예산(기본 20=헌법 X.4 운영자 소유).",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    print(f"내려받기 {SHILLER_URL} …", file=sys.stderr)
    all_rows = parse_shiller(
        urllib.request.urlopen(SHILLER_URL, timeout=60).read().decode()  # noqa: S310
    )
    print(f"내려받기 {GOLD_URL} …", file=sys.stderr)
    gold_by_month = parse_gold(
        urllib.request.urlopen(GOLD_URL, timeout=60).read().decode()  # noqa: S310
    )
    print(
        f"  주식·채권 {len(all_rows)}개월 ({all_rows[0].date} … {all_rows[-1].date})",
        file=sys.stderr,
    )

    result = _run(
        all_rows, gold_by_month,
        from_year=args.from_year, window=args.window, dd_budget=args.dd_budget,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
