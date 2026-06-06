"""스펙 045 — 최근 regime / 시점 강건성 감사 실측.

운영자 지적: "너무 먼 과거(1871~) 데이터 기준 분석 아닌가? 이 기준 자체를 점검하라."

세 가지를 정직하게 보여준다(Shiller 1871~현재, 읽기 전용·돈 0 이동):
  ① 최근 추적창(5·10·15·20·30년)·연대별 엣지 — 쇠퇴 여부.
  ② 주식·채권 롤링 상관 regime — *현재* 상관, 2022 양수 전환(분산 가정의 핵심 위험).
  ③ 2022(주식·채권 동반 폭락)·2020(코로나) 스트레스 — 추세 오버레이가 방어했나.

사용: uv run python scripts/regime_audit_probe.py [--window 10] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.regime_audit import (
    correlation_regime,
    stress_year,
    window_stats,
)
from auto_invest.analytics.risk_managed_beta import parse_shiller

SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"


def _leg(s) -> str:
    return (f"CAGR {s.cagr_pct:>6.1f}%  샤프 {s.sharpe:>5.2f}  "
            f"낙폭 {s.max_dd_pct:>5.1f}%  칼마 {(s.calmar or 0):>5.2f}")


def _run(all_rows, window: int) -> dict:
    last_year = int(all_rows[-1].date[:4])

    # ── ① 최근 추적창 + 연대별 ──────────────────────────────────────────
    print("① 시점 강건성 — 최근 추적창에서 엣지가 유지되는가 (단일 주식 추세 vs 분산 추세)\n")
    windows = []
    for yrs in (30, 20, 15, 10, 5):
        windows.append((f"최근 {yrs}년", last_year - yrs + 1, None))
    decades = [
        ("1990년대", 1990, 1999), ("2000년대", 2000, 2009),
        ("2010년대", 2010, 2019), ("2020년대", 2020, last_year),
    ]
    win_records = []
    for label, sy, ey in windows + decades:
        ws = window_stats(all_rows, label, sy, ey, window=window)
        win_records.append(ws.as_dict())
        print(f"[{label}]  ({ws.n_months}개월)")
        print(f"   60/40 단순보유 : {_leg(ws.bh_6040)}")
        print(f"   단일 주식 추세 : {_leg(ws.trend_equity)}")
        print(f"   분산 추세      : {_leg(ws.diversified)}")
        d, t = ws.diversified, ws.trend_equity
        better = "분산 우위" if (d.sharpe > t.sharpe) else "분산 열위"
        print(f"   → 샤프 {t.sharpe:.2f}(단일) vs {d.sharpe:.2f}(분산): {better}\n")

    # ── ② 주식·채권 상관 regime ────────────────────────────────────────
    print("② 주식·채권 롤링 상관 regime — 분산 가정이 *지금도* 유효한가 (36개월 창)\n")
    reg = correlation_regime(all_rows, window=36)
    cur = f"{reg.current:+.3f}" if reg.current is not None else "N/A"
    r5 = f"{reg.recent_5y_avg:+.3f}" if reg.recent_5y_avg is not None else "N/A"
    fa = f"{reg.full_avg:+.3f}" if reg.full_avg is not None else "N/A"
    pos = (reg.recent_5y_pos_fraction or 0) * 100
    print(f"   현재(최근 36개월) 상관 : {cur}")
    print(f"   최근 5년 평균 상관     : {r5}")
    print(f"   최근 5년 중 상관>0 비중: {pos:.0f}% (분산이 약해지는 구간)")
    print(f"   전체(1871~) 평균 상관  : {fa}")
    print(
        "   해석: 상관이 음수면 분산 강함. 2022 인플레 regime 처럼 양수로 뒤집히면 주식·채권이"
        " 같이 떨어져 *단순 분산이 실패* — 이때는 추세 오버레이(둘 다 추세 아래면 현금)가 방어선.\n"
    )

    # ── ③ 스트레스 연도 ────────────────────────────────────────────────
    print("③ 스트레스 연도 실측 — 추세 오버레이가 동반 폭락을 방어했나 (달력연도 수익률)\n")
    stress_records = []
    for yr in (2008, 2020, 2022):
        if yr > last_year:
            continue
        sy = stress_year(all_rows, yr, window=window)
        stress_records.append(sy.as_dict())
        print(f"[{yr}]  단순보유주식 {sy.bh_equity_pct:>6.1f}%  60/40 {sy.bh_6040_pct:>6.1f}%  "
              f"|  단일추세 {sy.trend_equity_pct:>6.1f}%  분산추세 {sy.diversified_pct:>6.1f}%")
    print(
        "\n   핵심: 2022 는 60/40(단순 분산)이 크게 깨진 해다. 추세 전략이 현금으로 빠져 더"
        " 방어했으면, 분산의 *진짜* 가치는 정적 분산이 아니라 *추세로 게이트한 분산*임을 보인다."
    )
    return {
        "as_of": all_rows[-1].date,
        "windows": win_records,
        "correlation_regime": reg.as_dict(),
        "stress_years": stress_records,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    print(f"내려받기 {SOURCE_URL} …", file=sys.stderr)
    raw = urllib.request.urlopen(SOURCE_URL, timeout=60).read().decode()  # noqa: S310
    all_rows = parse_shiller(raw)
    print(f"  {len(all_rows)}개월 ({all_rows[0].date} … {all_rows[-1].date})\n", file=sys.stderr)

    result = _run(all_rows, args.window)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
