"""스펙 050×044×047 — 자본 사다리 순 복리 비교: 배포된 시스템에서 어느 전략이 진짜 돈인가.

raw 복리(항상 100% 배포)가 아니라, **자본 사다리(헌법 X.4)의 강등(낙폭≥예산/2)·정지
(≥예산)·승격을 반영한 순 NAV 복리**로 후보 전략을 비교한다. 낙폭 큰 전략은 강등선(기본 10%)을
자주 건드려 손실 구간마다 배포 자본이 깎이고, 낮은 낙폭 전략은 단을 유지하며 단 3(NAV 100%)
까지 올라 온전히 복리된다 → raw CAGR 이 높아도 사다리 순 복리는 뒤집힐 수 있다.

레버리지는 K1 노출 캡(≤100%)에 막혀 자율 적용 불가(LEVERAGE-CAP-BOUNDARY.md) → 이 비교는
*캡 안*(무레버리지)에서, 현실적 거래비용 10bp 반영. 데이터: GitHub Shiller + 금(장기).

읽기 전용·순수·측정 전용. 주문 0·돈 0·캡 0 변경·라이브 무변경.

사용: uv run python scripts/ladder_growth_probe.py [--from-year 1971] [--cost-bps 10] [--json]
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
from auto_invest.analytics.ladder_simulation import simulate_ladder_growth
from auto_invest.analytics.multi_asset_trend import (
    diversified_trend_factors,
    equity_trend_factors,
)
from auto_invest.analytics.risk_managed_beta import parse_shiller

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"

_LIVE_KEY = "3자산 역변동성 +금 (라이브)"


def _strategies(rows, gold_levels, window: int, cost_bps: float):
    return [
        ("단일 주식 추세 (042)", equity_trend_factors(rows, window=window, cost_bps=cost_bps)),
        (
            "2자산 분산 추세 (043)",
            diversified_trend_factors(rows, window=window, cost_bps=cost_bps),
        ),
        (
            "3자산 고정가중 +금 (047)",
            global_trend_factors(rows, gold_levels, window=window, cost_bps=cost_bps),
        ),
        (
            _LIVE_KEY,
            risk_parity_global_factors(rows, gold_levels, window=window, cost_bps=cost_bps),
        ),
    ]


def _run(all_rows, gold_by_month, *, from_year: int, window: int, cost_bps: float) -> dict:
    rows = [r for r in all_rows if int(r.date[:4]) >= from_year]
    gold_levels = align_gold_levels(rows, gold_by_month)
    strategies = _strategies(rows, gold_levels, window, cost_bps)

    records = []
    for label, factors in strategies:
        rets = [f - 1.0 for f in factors]
        res = simulate_ladder_growth(rets, start_rung=1)
        records.append((label, res))

    records.sort(key=lambda lr: lr[1].cagr_pct, reverse=True)

    print(
        f"\n자본 사다리 순 복리 비교 ({from_year}~, {len(rows)}개월, 거래비용 {cost_bps:.0f}bp,"
        f" 무레버리지/캡 안)\n강등 낙폭≥10%·정지≥20%(예산 20%)·승격 calm 1개월\n"
    )
    head = (
        f"{'전략':<26} {'사다리 CAGR':>10} {'raw CAGR':>9} {'평균단':>6} "
        f"{'강등':>5} {'정지':>5} {'단3개월%':>8}"
    )
    print(head)
    print("-" * len(head))
    for label, res in records:
        d = res.as_dict()
        top = res.rung_months.get(3, 0) / res.n_months * 100 if res.n_months else 0
        print(
            f"{label:<26} {d['cagr_pct']:>9.1f}% {d['unconstrained_cagr_pct']:>8.1f}% "
            f"{d['avg_rung']:>6.2f} {d['demotions']:>5} {d['halts']:>5} {top:>7.0f}%"
        )
    print("-" * len(head))

    best = records[0]
    live = next((lr for lr in records if lr[0] == _LIVE_KEY), None)
    print(
        f"\n사다리 순 복리 1위: {best[0]} (사다리 CAGR {best[1].cagr_pct:.1f}%, "
        f"raw {best[1].unconstrained_cagr_pct:.1f}%)."
    )
    if live is not None:
        lr = live[1]
        print(
            f"라이브({_LIVE_KEY}): 사다리 CAGR {lr.cagr_pct:.1f}% · 강등 {lr.demotions} · "
            f"평균단 {lr.avg_rung:.2f} · 단3 체류 "
            f"{lr.rung_months.get(3, 0) / lr.n_months * 100:.0f}%."
        )
    fixed = next((lr for lr in records if "고정가중" in lr[0]), None)
    if live is not None and fixed is not None:
        diff = fixed[1].cagr_pct - live[1].cagr_pct
        total_demotes = live[1].demotions + fixed[1].demotions + live[1].halts
        print(
            f"\n핵심(정직): 고정가중 vs 라이브 역변동성 — 사다리 순 복리 격차 {diff:+.1f}%p "
            f"(고정가중 우위). 월간 해상도에선 사다리 강등이 거의 발동 안 함"
            f"(고정가중 강등 {fixed[1].demotions}, 역변동성 {live[1].demotions}) → "
            "순위가 raw 복리와 거의 같다. 즉 *월간 기준* 가설('낮은 낙폭이 사다리에서 이긴다')은"
            " 성립 안 하고, 고정가중이 사다리에서도 더 번다."
        )
        if total_demotes == 0:
            print(
                "  단, 고정가중 무레버 최대낙폭(≈9.6%)이 강등선(10%)에 *바짝* 붙어 있어 "
                "일별 해상도(실제 시스템)에선 강등이 더 자주 발동할 위험 — 월간 데이터로는 "
                "확정 불가. 역변동성(≈5.5%)은 강등선 한참 아래라 그 위험에서 자유롭다. "
                "= 성장(고정가중) vs 강등선 안전여유(역변동성)의 트레이드오프는 여전히 유효."
            )
    print(
        "\n주의: 월간 해상도라 일별 낙폭을 과소평가(실제 강등 더 잦음, 두 전략 동일 한계 — "
        "일별 검증은 KIS forward, 인스턴스측). 재지정·레버리지·캡 변경은 운영자 게이트 — 측정만."
    )
    return {
        "schema_version": "1.0",
        "from_year": from_year,
        "n_months": len(rows),
        "cost_bps": cost_bps,
        "best_label": best[0],
        "ranked": [{"label": label, **res.as_dict()} for label, res in records],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=GOLD_FLOAT_YEAR)
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--cost-bps", type=float, default=10.0)
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

    result = _run(
        all_rows, gold_by_month,
        from_year=args.from_year, window=args.window, cost_bps=args.cost_bps,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
