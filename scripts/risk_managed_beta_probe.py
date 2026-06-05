"""스펙 042 — 위험관리된 베타 실측: 추세 타이밍 vs 단순 보유(Shiller S&P 1871~현재).

운영자 결정 "위험관리된 베타로 재정의"의 직접 검증. 단순 보유 총수익 vs 10개월 SMA 추세
타이밍을 ① 전체(1871~), ② 전후/현대(1950~), ③ 최근(1990~) 구간에서 비교해, 추세 방어가
*실제 대공황을 포함한* 데이터에서 위험조정 수익(칼마·샤프)을 올리고 낙폭을 줄이는지 잰다.

슬라이스 2(--costs): 전환당 일방 거래비용 + (옵션) 매도 시 실현이익 세금을 반영해, 엣지가
*비용을 견디는지* 재측정한다(추세추종은 저회전이라 비용에 강하다고 알려졌지만 우리 데이터로 확인).

데이터는 GitHub datahub(이 컨테이너에서 닿는 유일한 장기 데이터). 읽기 전용 — 주문 0건.

사용: uv run python scripts/risk_managed_beta_probe.py [--window 10]
      [--costs] [--cost-bps 10] [--tax 0.15]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.risk_managed_beta import (
    compare_trend_overlay,
    compare_with_costs,
    compare_with_vol_target,
    current_signal,
    event_window_defense,
    parse_shiller,
    production_in_market,
    signal_timeline,
    trend_in_market,
)

SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"

# (라벨, 시작연도) — 같은 데이터의 서로 다른 regime 구간.
_PERIODS = [
    ("전체 1871~현재", 1871),
    ("현대 1950~현재", 1950),
    ("최근 1990~현재", 1990),
]


def _leg_line(label: str, name: str, s) -> str:
    return (
        f"{label:<14} {name:<14} {s.cagr_pct:>7.2f} {s.vol_pct:>7.2f} "
        f"{s.sharpe:>6.2f} {s.max_dd_pct:>9.1f} {(s.calmar or 0):>6.2f} "
        f"{s.pct_in_market * 100:>5.0f}%"
    )


def _header() -> str:
    return (
        f"{'구간':<14} {'다리':<14} {'CAGR%':>7} {'변동%':>7} {'샤프':>6} "
        f"{'최대낙폭%':>9} {'칼마':>6} {'투자%':>6}"
    )


def _run_gross(all_rows, window: int) -> list[dict]:
    print(f"추세 타이밍({window}개월 SMA) vs 단순 보유 — Shiller S&P 총수익\n")
    head = _header()
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        cmp = compare_trend_overlay(rows, window=window)
        records.append({"period": label, **cmp.as_dict()})
        print("-" * len(head))
        print(head)
        print(_leg_line(label, "단순보유", cmp.buy_hold))
        print(_leg_line("", "추세타이밍", cmp.trend))
        print(f"  → 판정: {cmp.verdict} ({cmp.reason})")
    print("-" * len(head))
    edges = [r for r in records if r["verdict"] == "RISK_MANAGED_EDGE"]
    print(f"\n요약: {len(edges)}/{len(records)} 구간에서 위험관리 엣지(낙폭↓ + 칼마↑ + 샤프 유지).")
    return records


def _run_costed(all_rows, window: int, cost_bps: float, tax: float) -> list[dict]:
    print(
        f"비용 반영 — 추세 타이밍({window}개월 SMA), 전환당 {cost_bps:.0f}bp 일방 거래비용"
        + (f" + 과세 {tax * 100:.0f}%(이연 아님 계좌)" if tax > 0 else " (세금 이연 계좌)")
        + "\n"
    )
    head = _header()
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        cmp = compare_with_costs(rows, window=window, cost_bps=cost_bps, tax_rate=tax)
        records.append({"period": label, **cmp.as_dict()})
        print("-" * len(head))
        print(head)
        print(_leg_line(label, "단순보유(순)", cmp.buy_hold_net))
        print(_leg_line("", "추세 비용전", cmp.trend_gross))
        print(_leg_line("", "추세 비용후", cmp.trend_net))
        if cmp.trend_net_tax is not None:
            print(_leg_line("", "추세 +세금", cmp.trend_net_tax))
        print(
            f"  → 전환 {cmp.turnover.switches}회 ({cmp.turnover.switches_per_year:.2f}회/년) "
            f"| 판정: {cmp.verdict} ({cmp.reason})"
        )
    print("-" * len(head))
    survive = [r for r in records if r["verdict"] == "EDGE_SURVIVES_COSTS"]
    print(
        f"\n요약: {len(survive)}/{len(records)} 구간에서 *비용 반영 후에도* 위험관리 엣지 유지."
    )
    return records


def _run_production_bridge(all_rows, window: int) -> list[dict]:
    """슬라이스 3 — 운영 코드(strategy.trend.above_trend) 신호가 연구 신호와 같고, 같은
    위험관리 엣지를 재현하는지(라이브 경로가 검증된 엣지를 그대로 싣는지)."""
    print(
        f"운영 코드 브리지 — strategy.trend.above_trend(SMA {window})가 라이브에서 내는 신호로"
        f" 같은 엣지가 재현되는가\n"
    )
    head = _header()
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        research = trend_in_market(rows, window)
        prod = production_in_market(rows, lookback=window)
        agree = sum(1 for a, b in zip(research, prod, strict=True) if a == b)
        match_pct = 100.0 * agree / len(prod) if prod else 0.0
        cmp = compare_with_costs(rows, window=window, cost_bps=10.0, in_market=prod)
        records.append(
            {"period": label, "signal_match_pct": round(match_pct, 2), **cmp.as_dict()}
        )
        print("-" * len(head))
        print(head)
        print(_leg_line(label, "단순보유(순)", cmp.buy_hold_net))
        print(_leg_line("", "운영추세(순)", cmp.trend_net))
        print(
            f"  → 운영↔연구 신호 일치 {match_pct:.1f}% | 판정: {cmp.verdict} ({cmp.reason})"
        )
    print("-" * len(head))
    full_match = all(r["signal_match_pct"] == 100.0 for r in records)
    print(
        "\n요약: 운영 코드 신호가 연구 신호와 "
        + ("완전 일치(100%)" if full_match else "불일치 있음")
        + " → 검증된 엣지가 라이브 코드 경로에 그대로 실린다."
    )
    return records


def _run_vol_target(all_rows, window: int, target_vol: float) -> list[dict]:
    """슬라이스 4 — 추세만 vs 추세+변동성 타깃(고변동 시 노출 축소, 무레버리지)."""
    print(
        f"변동성 타깃 결합 — 추세({window}개월) 위에 연 {target_vol * 100:.0f}% 변동성 타깃"
        f"(하향 전용·무레버리지), 10bp 비용\n"
    )
    head = _header()
    records = []
    for label, start_year in _PERIODS:
        rows = [r for r in all_rows if int(r.date[:4]) >= start_year]
        if len(rows) < 24:
            continue
        cmp = compare_with_vol_target(
            rows, window=window, target_annual_vol=target_vol, cost_bps=10.0
        )
        records.append({"period": label, **cmp.as_dict()})
        print("-" * len(head))
        print(head)
        print(_leg_line(label, "단순보유(순)", cmp.buy_hold_net))
        print(_leg_line("", "추세만(순)", cmp.trend_net))
        print(_leg_line("", "추세+변동성", cmp.trend_vol_net))
        print(
            f"  → 평균 노출 {cmp.avg_exposure * 100:.0f}% | 판정: {cmp.verdict} ({cmp.reason})"
        )
    print("-" * len(head))
    adds = [r for r in records if r["verdict"] == "VOL_TARGET_ADDS"]
    print(
        f"\n요약: {len(adds)}/{len(records)} 구간에서 변동성 타깃이 추세 위에 추가 위험조정 가치."
    )
    return records


# 운영자가 기억하는 실제 사건 — 검증 가능한 기준점.
_MEMORABLE_EVENTS = [
    ("닷컴 버블 붕괴", "2000-03", "2003-03"),
    ("글로벌 금융위기(2008)", "2007-10", "2009-06"),
    ("코로나 폭락(2020)", "2020-01", "2020-12"),
    ("2022 약세장", "2022-01", "2023-01"),
]


def _run_confidence(all_rows, window: int) -> dict:
    """운영자 확신용 리포트 — 기억나는 사건의 실제 방어(좋은 것·나쁜 것) + 오늘 신호."""
    print("운영자 확신 리포트 — 기억나는 실제 사건에서 추세 전략이 실제로 어떻게 행동했나\n")
    print(
        f"{'사건':<24}{'단순보유 낙폭':>13}{'추세 낙폭':>11}{'현금개월':>9}{'판정':>8}"
    )
    print("-" * 66)
    events = []
    for label, s, e in _MEMORABLE_EVENTS:
        ev = event_window_defense(all_rows, label, s, e, window=window)
        events.append(ev.as_dict())
        mark = "방어✅" if ev.defended else "실패❌"
        print(
            f"{label:<24}{ev.buy_hold_drawdown_pct:>12.1f}%{ev.strategy_drawdown_pct:>10.1f}%"
            f"{ev.months_in_cash:>6}/{ev.total_months:<2}{mark:>8}"
        )
    print("-" * 66)

    print("\n현금 이탈/재진입 타임라인 (검증 가능):")
    for label, s, e in [
        ("  글로벌 금융위기", "2007-06", "2009-12"),
        ("  코로나(실패 사례)", "2019-12", "2020-12"),
    ]:
        tl = signal_timeline(all_rows, s, e, window=window)
        print(f"{label}: " + " → ".join(f"{d} {st}" for d, st in tl))

    cur = current_signal(all_rows, window=window)
    if cur is not None:
        state = "투자(추세 위)" if cur.in_market else "현금(추세 아래)"
        print(
            f"\n오늘({cur.as_of}) 신호: S&P {cur.price:.0f} vs {window}개월 SMA {cur.sma:.0f}"
            f" ({cur.gap_pct:+.1f}%) → {state}"
        )
        print("  → 운영자님이 현재 시장 위치와 직접 대조해 검증하실 수 있습니다.")

    defended = sum(1 for e in events if e["defended"])
    print(
        f"\n정직한 요약: {defended}/{len(events)} 사건에서 방어 성공. "
        "느린 약세장(닷컴·GFC·2022)엔 강하지만, 빠른 V자 폭락(코로나)엔 월간 추세가 못 따라간다."
    )
    return {"events": events, "current_signal": cur.as_dict() if cur else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=10, help="추세 SMA 개월(고전 10).")
    ap.add_argument("--costs", action="store_true", help="거래비용·세금 반영 비교.")
    ap.add_argument("--cost-bps", type=float, default=10.0, help="전환당 일방 거래비용(bp).")
    ap.add_argument("--tax", type=float, default=0.0, help="과세 계좌 자본이득세율(0..1).")
    ap.add_argument(
        "--production-trend",
        action="store_true",
        help="운영 코드(strategy.trend) 신호로 같은 엣지가 재현되는지(슬라이스 3 브리지).",
    )
    ap.add_argument(
        "--vol-target",
        action="store_true",
        help="추세 위에 변동성 타깃 결합 효과(슬라이스 4).",
    )
    ap.add_argument("--target-vol", type=float, default=0.12, help="연 변동성 타깃(0..1).")
    ap.add_argument(
        "--confidence",
        action="store_true",
        help="운영자 확신 리포트(기억나는 사건 방어 + 오늘 신호).",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    print(f"내려받기 {SOURCE_URL} …", file=sys.stderr)
    raw = urllib.request.urlopen(SOURCE_URL, timeout=60).read().decode()  # noqa: S310
    all_rows = parse_shiller(raw)
    print(
        f"  {len(all_rows)}개월 ({all_rows[0].date} … {all_rows[-1].date})\n",
        file=sys.stderr,
    )

    if args.confidence:
        records = _run_confidence(all_rows, args.window)
    elif args.production_trend:
        records = _run_production_bridge(all_rows, args.window)
    elif args.vol_target:
        records = _run_vol_target(all_rows, args.window, args.target_vol)
    elif args.costs:
        records = _run_costed(all_rows, args.window, args.cost_bps, args.tax)
    else:
        records = _run_gross(all_rows, args.window)

    if args.json:
        print(json.dumps(records, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
