"""스펙 044 — 성장 최적 레버리지 실측: 고정 자본에서 복리 성장(CAGR) 극대화.

운영자 지시: "현재 자본에서 복리 효과로 수익을 극대화하라(자본 키우기는 누구나 함)."

세 가지를 정직하게 보여준다:
  ① 분산 추세(스펙 043)에 레버리지를 0.5~5배 얹으며 CAGR 이 *오르다 떨어지는 hump* 를 그린다
     — "최대 레버리지"가 답이 아니라 정확한 최적점이 있음을 드러낸다(변동성 드래그).
  ② 성장 최적 레버리지(CAGR 최대) + 낙폭 예산(30%)에서의 실무 최적을 함께 보고.
  ③ 단일 주식 추세 vs 분산 추세를 같은 낙폭 예산에서 레버리지 최적화해 비교 —
     샤프가 높은 분산 쪽이 같은 위험에서 더 높은 복리 성장을 낸다(고정 자본 극대화의 핵심).

데이터: Shiller GitHub CSV(1871~현재). 읽기 전용 — 주문 0건, 돈 0 이동. 레버리지는 연구/
페이퍼 측정 전용(라이브 K1 캡 불변). 사용: uv run python scripts/growth_optimal_probe.py
  [--window 10] [--equity-weight 0.5] [--bond-weight 0.5] [--dd-budget 30] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.growth_optimal import (
    compare_leverage,
    drawdown_constrained_optimal,
    growth_curve,
    growth_optimal,
    risk_free_monthly,
)
from auto_invest.analytics.multi_asset_trend import (
    diversified_trend_factors,
    equity_trend_factors,
)
from auto_invest.analytics.risk_managed_beta import parse_shiller

SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"

_PERIODS = [("전체 1871~현재", 1871), ("현대 1950~현재", 1950), ("최근 1990~현재", 1990)]
_LEVERAGES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]


def _run(all_rows, window: int, ew: float, bw: float, dd_budget: float) -> list[dict]:
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        rf = risk_free_monthly(rows)
        div = diversified_trend_factors(
            rows, window=window, equity_weight=ew, bond_weight=bw
        )
        curve = growth_curve(div, rf, leverages=_LEVERAGES)
        opt = growth_optimal(curve)
        dd_opt = drawdown_constrained_optimal(curve, max_dd_pct=dd_budget)

        print(f"\n{'=' * 72}\n[{label}] 분산 추세에 레버리지 — CAGR hump (복리 성장 곡선)")
        print(f"{'레버':>5} {'CAGR%':>8} {'변동%':>7} {'샤프':>6} {'최대낙폭%':>9} {'칼마':>6}")
        print("-" * 50)
        for p in curve:
            mark = ""
            if p.leverage == opt.leverage:
                mark += "  ← CAGR 최대(성장최적)"
            if dd_opt and p.leverage == dd_opt.leverage:
                mark += f"  ← 낙폭≤{dd_budget:.0f}% 최적"
            print(
                f"{p.leverage:>5.1f} {p.cagr_pct:>8.2f} {p.vol_pct:>7.2f} "
                f"{p.sharpe:>6.2f} {p.max_dd_pct:>9.1f} {(p.calmar or 0):>6.2f}{mark}"
            )
        print("-" * 50)
        print(
            f"  성장최적 L={opt.leverage:.1f}: CAGR {opt.cagr_pct:.1f}% "
            f"(낙폭 {opt.max_dd_pct:.0f}% — 풀켈리는 과격)."
        )
        if dd_opt:
            unlev = next(p for p in curve if p.leverage == 1.0)
            print(
                f"  낙폭예산 {dd_budget:.0f}% 최적 L={dd_opt.leverage:.1f}: "
                f"CAGR {unlev.cagr_pct:.1f}%→{dd_opt.cagr_pct:.1f}% "
                f"(샤프 {dd_opt.sharpe:.2f} 보존, 낙폭 {dd_opt.max_dd_pct:.0f}%) "
                "= 같은 위험 예산에서 복리 성장 극대화."
            )
        records.append({
            "period": label,
            "curve": [p.as_dict() for p in curve],
            "growth_optimal": opt.as_dict(),
            "drawdown_constrained_optimal": dd_opt.as_dict() if dd_opt else None,
        })
    return records


def _run_compare(all_rows, window: int, ew: float, bw: float, dd_budget: float) -> list[dict]:
    print(
        f"\n단일 주식 추세 vs 분산 추세 — 같은 낙폭 예산({dd_budget:.0f}%)에서 레버리지 최적화"
        " (샤프 높은 쪽이 복리 성장 이김)\n"
    )
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        rf = risk_free_monthly(rows)
        eq = equity_trend_factors(rows, window=window)
        div = diversified_trend_factors(rows, window=window, equity_weight=ew, bond_weight=bw)
        cmp = compare_leverage(
            "단일주식추세", eq, "분산추세", div, rf,
            leverages=_LEVERAGES, max_dd_budget_pct=dd_budget,
        )
        a, b = cmp.dd_opt_a, cmp.dd_opt_b
        print(f"[{label}]")
        if a:
            print(f"  단일주식추세  최적 L={a.leverage:.1f}  CAGR {a.cagr_pct:>6.1f}%  "
                  f"샤프 {a.sharpe:.2f}  낙폭 {a.max_dd_pct:.0f}%")
        if b:
            print(f"  분산추세      최적 L={b.leverage:.1f}  CAGR {b.cagr_pct:>6.1f}%  "
                  f"샤프 {b.sharpe:.2f}  낙폭 {b.max_dd_pct:.0f}%")
        if a and b:
            print(f"  → 같은 낙폭 예산에서 분산이 CAGR {b.cagr_pct - a.cagr_pct:+.1f}%p "
                  f"({'우위' if b.cagr_pct > a.cagr_pct else '열위'}).")
        records.append({"period": label, **cmp.as_dict()})
    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--equity-weight", type=float, default=0.5)
    ap.add_argument("--bond-weight", type=float, default=0.5)
    ap.add_argument("--dd-budget", type=float, default=30.0, help="감내 최대낙폭(%) 예산.")
    ap.add_argument("--compare", action="store_true", help="단일 주식 vs 분산 레버리지 비교.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    print(f"내려받기 {SOURCE_URL} …", file=sys.stderr)
    raw = urllib.request.urlopen(SOURCE_URL, timeout=60).read().decode()  # noqa: S310
    all_rows = parse_shiller(raw)
    print(f"  {len(all_rows)}개월 ({all_rows[0].date} … {all_rows[-1].date})", file=sys.stderr)

    if args.compare:
        result = _run_compare(all_rows, args.window, args.equity_weight, args.bond_weight,
                              args.dd_budget)
    else:
        result = _run(all_rows, args.window, args.equity_weight, args.bond_weight,
                      args.dd_budget)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
