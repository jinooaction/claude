"""스펙 042 — 위험관리된 베타 실측: 추세 타이밍 vs 단순 보유(Shiller S&P 1871~현재).

운영자 결정 "위험관리된 베타로 재정의"의 직접 검증. 단순 보유 총수익 vs 10개월 SMA 추세
타이밍을 ① 전체(1871~), ② 전후/현대(1950~), ③ 최근(1990~) 구간에서 비교해, 추세 방어가
*실제 대공황을 포함한* 데이터에서 위험조정 수익(칼마·샤프)을 올리고 낙폭을 줄이는지 잰다.

데이터는 GitHub datahub(이 컨테이너에서 닿는 유일한 장기 데이터). 읽기 전용 — 주문 0건.

사용: uv run python scripts/risk_managed_beta_probe.py [--window 10]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.risk_managed_beta import compare_trend_overlay, parse_shiller

SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"

# (라벨, 시작연도) — 같은 데이터의 서로 다른 regime 구간.
_PERIODS = [
    ("전체 1871~현재", 1871),
    ("현대 1950~현재", 1950),
    ("최근 1990~현재", 1990),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=10, help="추세 SMA 개월(고전 10).")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    print(f"내려받기 {SOURCE_URL} …", file=sys.stderr)
    raw = urllib.request.urlopen(SOURCE_URL, timeout=60).read().decode()  # noqa: S310
    all_rows = parse_shiller(raw)
    print(
        f"  {len(all_rows)}개월 ({all_rows[0].date} … {all_rows[-1].date})\n",
        file=sys.stderr,
    )

    print(f"추세 타이밍({args.window}개월 SMA) vs 단순 보유 — Shiller S&P 총수익\n")
    header = (
        f"{'구간':<16} {'다리':<10} {'CAGR%':>7} {'변동%':>7} {'샤프':>6} "
        f"{'최대낙폭%':>9} {'칼마':>6} {'투자%':>6}"
    )
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        cmp = compare_trend_overlay(rows, window=args.window)
        records.append({"period": label, **cmp.as_dict()})
        print("-" * len(header))
        print(header)
        bh, tr = cmp.buy_hold, cmp.trend
        print(
            f"{label:<16} {'단순보유':<10} {bh.cagr_pct:>7.2f} {bh.vol_pct:>7.2f} "
            f"{bh.sharpe:>6.2f} {bh.max_dd_pct:>9.1f} "
            f"{(bh.calmar or 0):>6.2f} {bh.pct_in_market * 100:>5.0f}%"
        )
        print(
            f"{'':<16} {'추세타이밍':<10} {tr.cagr_pct:>7.2f} {tr.vol_pct:>7.2f} "
            f"{tr.sharpe:>6.2f} {tr.max_dd_pct:>9.1f} "
            f"{(tr.calmar or 0):>6.2f} {tr.pct_in_market * 100:>5.0f}%"
        )
        print(f"  → 판정: {cmp.verdict} ({cmp.reason})")
    print("-" * len(header))

    edges = [r for r in records if r["verdict"] == "RISK_MANAGED_EDGE"]
    print(
        f"\n요약: {len(edges)}/{len(records)} 구간에서 위험관리 엣지(낙폭↓ + 칼마↑ + 샤프 유지)."
    )
    if args.json:
        print(json.dumps(records, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
