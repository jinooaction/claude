"""스펙 043 — 멀티에셋 분산 추세추종 실측: 단일 주식 추세 vs 주식추세+채권추세 분산.

검증된 단일 자산 엣지(스펙 042)를 *세계 최고 수준* 차원으로 확장한다. Shiller GitHub CSV
(이 컨테이너에서 닿는 유일한 장기 데이터)의 S&P 총수익 + 10년 국채 수익률로, 두 비상관
자산(주식 베타 + 채권 듀레이션)에 각각 추세 타이밍을 얹어 합친 분산 포트폴리오가 단일 주식
추세보다 위험조정 수익(샤프·칼마)을 더 올리는지를 ① 전체(1871~) ② 현대(1950~) ③ 최근
(1990~) 구간에서 잰다.

읽기 전용 — 주문 0건, 돈 0 이동. 미래 누출 없음(결정론).

사용: uv run python scripts/multi_asset_trend_probe.py [--window 10]
      [--equity-weight 0.5] [--bond-weight 0.5] [--corr] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.multi_asset_trend import (
    bond_total_return_factors,
    compare_diversified_trend,
    correlation,
)
from auto_invest.analytics.risk_managed_beta import (
    market_total_return_factors,
    parse_shiller,
)

SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"

_PERIODS = [
    ("전체 1871~현재", 1871),
    ("현대 1950~현재", 1950),
    ("최근 1990~현재", 1990),
]


def _header() -> str:
    return (
        f"{'구간':<14} {'다리':<16} {'CAGR%':>7} {'변동%':>7} {'샤프':>6} "
        f"{'최대낙폭%':>9} {'칼마':>6}"
    )


def _leg_line(label: str, name: str, s) -> str:
    return (
        f"{label:<14} {name:<16} {s.cagr_pct:>7.2f} {s.vol_pct:>7.2f} "
        f"{s.sharpe:>6.2f} {s.max_dd_pct:>9.1f} {(s.calmar or 0):>6.2f}"
    )


def _run(all_rows, window: int, ew: float, bw: float) -> list[dict]:
    print(
        f"멀티에셋 분산 추세({window}개월 SMA) — 주식 {ew:.0%} / 채권 {bw:.0%} 매월 재조정,"
        f" 각 자산 추세 아래면 현금\n"
    )
    head = _header()
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        cmp = compare_diversified_trend(
            rows, window=window, equity_weight=ew, bond_weight=bw
        )
        records.append({"period": label, **cmp.as_dict()})
        print("-" * len(head))
        print(head)
        print(_leg_line(label, "단순보유 주식", cmp.bh_equity))
        print(_leg_line("", "단순보유 60/40", cmp.bh_6040))
        print(_leg_line("", "추세 주식만", cmp.trend_equity))
        print(_leg_line("", "추세 채권만", cmp.trend_bond))
        print(_leg_line("", "분산 추세(주+채)", cmp.diversified_trend))
        print(f"  → 판정: {cmp.verdict} ({cmp.reason})")
    print("-" * len(head))
    edges = [r for r in records if r["verdict"] == "DIVERSIFICATION_EDGE"]
    print(
        f"\n요약: {len(edges)}/{len(records)} 구간에서 분산 추세 엣지"
        "(단일 주식 추세 대비 샤프↑ + 칼마↑ + 낙폭 비악화)."
    )
    return records


def _run_corr(all_rows) -> dict:
    """주식·채권 총수익의 상관 — 분산 효과의 근거를 정직히 드러낸다."""
    print("주식 vs 채권 총수익 상관 (분산 효과의 근거)\n")
    out = {}
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        eq = market_total_return_factors(rows)
        bond = bond_total_return_factors(rows)
        corr = correlation(eq, bond)
        out[label] = round(corr, 4) if corr is not None else None
        print(f"  {label:<16} 상관 {corr:+.3f}" if corr is not None else f"  {label}: N/A")
    print(
        "\n해석: 상관이 낮을수록(0 근처·음수일수록) 두 추세 흐름을 합쳤을 때 분산 이득이 크다."
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=10, help="추세 SMA 개월(고전 10).")
    ap.add_argument("--equity-weight", type=float, default=0.5, help="주식 슬리브 비중.")
    ap.add_argument("--bond-weight", type=float, default=0.5, help="채권 슬리브 비중.")
    ap.add_argument("--corr", action="store_true", help="주식·채권 상관만 출력.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    print(f"내려받기 {SOURCE_URL} …", file=sys.stderr)
    raw = urllib.request.urlopen(SOURCE_URL, timeout=60).read().decode()  # noqa: S310
    all_rows = parse_shiller(raw)
    print(
        f"  {len(all_rows)}개월 ({all_rows[0].date} … {all_rows[-1].date})\n",
        file=sys.stderr,
    )

    if args.corr:
        result = _run_corr(all_rows)
    else:
        result = _run(all_rows, args.window, args.equity_weight, args.bond_weight)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
