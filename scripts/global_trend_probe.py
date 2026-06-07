"""스펙 047 — 글로벌 분산 추세추종 실측: 2자산(주식+채권) vs 3자산(+금).

검증된 분산 추세(스펙 043)에 *세 번째 비상관 자산(금)*을 더하면 위험조정 수익(샤프·칼마)이
더 오르는가를 ① 전체(1871~) ② 현대(1950~) ③ **자유변동 금(1971~)** ④ 최근(1990~) 구간에서
잰다. 금은 1971 브레튼우즈 붕괴 전엔 고정환(페그)이라 추세가 없으므로 1971~ 구간이 정직한
핵심 답이다(전체·현대엔 페그 잡음 명시).

데이터(둘 다 GitHub — 이 컨테이너에서 닿는 유일한 장기 소스):
  - 주식·채권: datasets/s-and-p-500 (Shiller, S&P 총수익 + 10년 국채 수익률, 1871~)
  - 금: datasets/gold-prices (런던 금 월간, 1833~)

읽기 전용 — 주문 0건, 돈 0 이동. 미래 누출 없음(결정론).

사용: uv run python scripts/global_trend_probe.py [--window 10]
      [--equity-weight 1] [--bond-weight 1] [--gold-weight 1] [--corr] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.global_trend import (
    GOLD_FLOAT_YEAR,
    align_gold_levels,
    compare_global_trend,
    gold_total_return_factors,
    parse_gold,
)
from auto_invest.analytics.multi_asset_trend import (
    bond_total_return_factors,
    correlation,
)
from auto_invest.analytics.risk_managed_beta import (
    market_total_return_factors,
    parse_shiller,
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
        f"{'구간':<16} {'다리':<18} {'CAGR%':>7} {'변동%':>7} {'샤프':>6} "
        f"{'최대낙폭%':>9} {'칼마':>6}"
    )


def _leg_line(label: str, name: str, s) -> str:
    return (
        f"{label:<16} {name:<18} {s.cagr_pct:>7.2f} {s.vol_pct:>7.2f} "
        f"{s.sharpe:>6.2f} {s.max_dd_pct:>9.1f} {(s.calmar or 0):>6.2f}"
    )


def _run(all_rows, gold_by_month, window, ew, bw, gw) -> list[dict]:
    print(
        f"글로벌 분산 추세({window}개월 SMA) — 주식·채권·금 각자 추세 위면 보유/아래면 현금,"
        f" 매월 재조정\n"
    )
    head = _header()
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        gold_levels = align_gold_levels(rows, gold_by_month)
        cmp = compare_global_trend(
            rows,
            gold_levels,
            window=window,
            equity_weight=ew,
            bond_weight=bw,
            gold_weight=gw,
        )
        records.append({"period": label, **cmp.as_dict()})
        print("-" * len(head))
        print(head)
        print(_leg_line(label, "추세 주식만", cmp.trend_equity))
        print(_leg_line("", "추세 채권만", cmp.trend_bond))
        print(_leg_line("", "추세 금만", cmp.trend_gold))
        print(_leg_line("", "2자산(주+채)", cmp.diversified_2asset))
        print(_leg_line("", "3자산 고정가중", cmp.diversified_3asset))
        print(_leg_line("", "3자산 역변동성", cmp.risk_parity_3asset))
        gce = cmp.gold_corr_equity
        gcb = cmp.gold_corr_bond
        print(
            f"  금 상관: 주식 {gce:+.3f} / 채권 {gcb:+.3f}"
            if gce is not None and gcb is not None
            else "  금 상관: N/A"
        )
        print(f"  → 판정(고정가중): {cmp.verdict} ({cmp.reason})")
        print(f"  → 판정(역변동성): {cmp.verdict_rp} ({cmp.reason_rp})")
    print("-" * len(head))
    edges = [r for r in records if r["verdict"] == "GOLD_DIVERSIFICATION_EDGE"]
    edges_rp = [r for r in records if r["verdict_rp"] == "GOLD_DIVERSIFICATION_EDGE"]
    print(
        f"\n요약: 고정가중 {len(edges)}/{len(records)} · 역변동성 {len(edges_rp)}/{len(records)}"
        " 구간에서 금 분산 엣지(2자산 대비 샤프↑ + 칼마↑ + 낙폭 비악화)."
        " 1971~ 자유변동 구간이 정직한 핵심."
    )
    return records


def _run_corr(all_rows, gold_by_month) -> dict:
    """금↔주식·금↔채권 상관 — 금 분산 효과의 근거를 정직히 드러낸다."""
    print("금 vs 주식 / 금 vs 채권 총수익 상관 (분산 효과의 근거)\n")
    out = {}
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        gold_levels = align_gold_levels(rows, gold_by_month)
        eq = market_total_return_factors(rows)
        bond = bond_total_return_factors(rows)
        gold = gold_total_return_factors(gold_levels)
        ce = correlation(gold, eq)
        cb = correlation(gold, bond)
        out[label] = {
            "gold_equity": round(ce, 4) if ce is not None else None,
            "gold_bond": round(cb, 4) if cb is not None else None,
        }
        if ce is not None and cb is not None:
            print(f"  {label:<16} 금↔주식 {ce:+.3f} | 금↔채권 {cb:+.3f}")
        else:
            print(f"  {label}: N/A")
    print(
        "\n해석: 금이 주식·채권 *둘 다와* 비상관(0 근처·음수)일수록 세 추세 흐름을 합쳤을 때"
        " 분산 이득이 크다. 특히 주식·채권 상관이 양수로 가는 인플레 regime 의 구조적 보완."
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=10, help="추세 SMA 개월(고전 10).")
    ap.add_argument("--equity-weight", type=float, default=1.0, help="주식 슬리브 상대 비중.")
    ap.add_argument("--bond-weight", type=float, default=1.0, help="채권 슬리브 상대 비중.")
    ap.add_argument("--gold-weight", type=float, default=1.0, help="금 슬리브 상대 비중.")
    ap.add_argument("--corr", action="store_true", help="금 상관만 출력.")
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
        f"  주식·채권 {len(all_rows)}개월 ({all_rows[0].date} … {all_rows[-1].date}),"
        f" 금 {len(gold_by_month)}개월\n",
        file=sys.stderr,
    )

    if args.corr:
        result = _run_corr(all_rows, gold_by_month)
    else:
        result = _run(
            all_rows,
            gold_by_month,
            args.window,
            args.equity_weight,
            args.bond_weight,
            args.gold_weight,
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
