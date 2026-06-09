"""스펙 048 — 다중 추세 속도 앙상블 실측: 단일 속도 vs 6/10/12개월 앙상블 (3자산 역변동성).

검증된 3자산 위험관리 추세(스펙 047)의 추세 게이트를 단일 10개월 SMA → *여러 속도 합의 분수
노출*로 바꿨을 때 위험조정 수익(샤프·칼마·낙폭)이 개선되는지 ① 전체(1871~) ② 현대(1950~)
③ 자유변동 금(1971~) ④ 최근(1990~) 구간에서 잰다. 추가 데이터 0.

데이터(둘 다 GitHub): datasets/s-and-p-500(Shiller) + datasets/gold-prices.
읽기 전용 — 주문 0건, 돈 0 이동. 미래 누출 없음(결정론).

사용: uv run python scripts/trend_ensemble_probe.py [--single 10] [--ensemble 6,10,12] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.global_trend import GOLD_FLOAT_YEAR, parse_gold
from auto_invest.analytics.risk_managed_beta import parse_shiller
from auto_invest.analytics.trend_ensemble import (
    align_gold_levels,
    compare_trend_ensemble,
)

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"

_PERIODS = [
    ("전체 1871~현재", 1871),
    ("현대 1950~현재", 1950),
    (f"자유변동 금 {GOLD_FLOAT_YEAR}~", GOLD_FLOAT_YEAR),
    ("최근 1990~현재", 1990),
]


def _header() -> str:
    return (
        f"{'구간':<16} {'전략':<22} {'CAGR%':>7} {'변동%':>7} {'샤프':>6} "
        f"{'최대낙폭%':>9} {'칼마':>6}"
    )


def _leg_line(label: str, name: str, s) -> str:
    return (
        f"{label:<16} {name:<22} {s.cagr_pct:>7.2f} {s.vol_pct:>7.2f} "
        f"{s.sharpe:>6.2f} {s.max_dd_pct:>9.1f} {(s.calmar or 0):>6.2f}"
    )


def _run(all_rows, gold_by_month, single, ensemble) -> list[dict]:
    ens_str = "/".join(str(w) for w in ensemble)
    print(
        f"다중 추세 속도 앙상블 — 단일 {single}개월 vs 앙상블 {ens_str}개월 "
        f"(3자산 주식·채권·금 역변동성)\n"
    )
    head = _header()
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        gold_levels = align_gold_levels(rows, gold_by_month)
        cmp = compare_trend_ensemble(
            rows, gold_levels, single_window=single, ensemble_windows=ensemble
        )
        records.append({"period": label, **cmp.as_dict()})
        print("-" * len(head))
        print(head)
        print(_leg_line(label, f"단일 {single}개월", cmp.single_speed))
        print(_leg_line("", f"앙상블 {ens_str}", cmp.ensemble))
        print(f"  → 판정: {cmp.verdict} ({cmp.reason})")
    print("-" * len(head))
    edges = [r for r in records if r["verdict"] == "TREND_ENSEMBLE_EDGE"]
    print(
        f"\n요약: {len(edges)}/{len(records)} 구간에서 앙상블 엣지(단일 속도 대비 샤프↑ + 칼마↑"
        " + 낙폭 비악화). 개선 없으면 단일 속도가 이미 충분하다는 정직한 결론."
    )
    return records


def _parse_windows(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in s.split(",") if x.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", type=int, default=10, help="단일 속도 SMA 개월.")
    ap.add_argument("--ensemble", type=str, default="6,10,12", help="앙상블 속도(쉼표).")
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
        f"  주식·채권 {len(all_rows)}개월, 금 {len(gold_by_month)}개월\n", file=sys.stderr
    )

    result = _run(all_rows, gold_by_month, args.single, _parse_windows(args.ensemble))
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
