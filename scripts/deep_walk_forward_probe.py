"""스펙 047 후속 — 깊은 OOS walk-forward 실측: 추세추종이 단순 보유를 *정말* 이기는가.

라이브 forward 판정은 2022~2026 KIS 일봉(강세장 4년)에서 GLOBAL-TREND 가 "강건한 엣지
없음(단순 보유에 −28%p)"이라 했다. 이 probe 는 같은 질문을 **약세장을 포함한 깊은 월간
데이터(1871~/1971~)**에서 walk-forward 구간별로 다시 던진다 — 추세추종의 진짜 엣지(자본
방어)가 강세장 단일 창에서만 안 보이는 것인지, 정말 없는 것인지 가른다.

데이터(둘 다 GitHub — 이 컨테이너에서 닿는 유일한 장기 소스, 스펙 047 과 동일):
  - 주식·채권: datasets/s-and-p-500 (Shiller, S&P 총수익 + 10년 국채, 1871~)
  - 금: datasets/gold-prices (런던 금 월간, 1833~)

읽기 전용 — 주문 0건, 돈 0 이동. 미래 누출 없음(결정론).

사용: uv run python scripts/deep_walk_forward_probe.py
      [--from-year 1971] [--window 10] [--segment-months 60] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.deep_walk_forward import (
    DeepWalkForwardReport,
    deep_walk_forward_compare,
)
from auto_invest.analytics.global_trend import (
    GOLD_FLOAT_YEAR,
    align_gold_levels,
    parse_gold,
)
from auto_invest.analytics.risk_managed_beta import parse_shiller

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"

_VERDICT_MARK = {
    "RETURN_EDGE": "🏆 수익 엣지",
    "ROBUST_DEFENSE_EDGE": "🛡 방어 엣지",
    "NO_ROBUST_EDGE": "— 엣지 없음",
}


def _fmt_report(report: DeepWalkForwardReport) -> str:
    lines: list[str] = []
    lines.append(
        f"깊은 OOS walk-forward — 추세 후보 vs {report.benchmark_label}\n"
        f"  추세 SMA {report.window}개월 · 구간 {report.segment_months}개월 ·"
        f" 총 {report.n_months_total}개월 · {report.n_windows}개 구간\n"
    )
    head = (
        f"{'후보':<34} {'판정':<12} {'전체샤프':>7} {'전체칼마':>7} "
        f"{'전체낙폭%':>8} {'구간샤프승':>9} {'구간방어승':>9} {'최악구간%':>8}"
    )
    lines.append(head)
    lines.append("-" * len(head))
    # 벤치마크 한 줄(맥락).
    b = report.candidates[0].full_benchmark
    lines.append(
        f"{'(벤치마크) 등가중 단순보유':<34} {'기준':<12} "
        f"{b.sharpe:>7.2f} {(b.calmar or 0):>7.2f} {b.max_dd_pct:>8.1f} "
        f"{'—':>9} {'—':>9} "
        f"{(report.candidates[0].worst_window_cagr_pct_bench or 0):>8.1f}"
    )
    for c in report.candidates:
        f = c.full_period
        lines.append(
            f"{c.label:<34} {_VERDICT_MARK.get(c.verdict, c.verdict):<12} "
            f"{f.sharpe:>7.2f} {(f.calmar or 0):>7.2f} {f.max_dd_pct:>8.1f} "
            f"{c.sharpe_wins:>4}/{c.n_windows:<4} {c.defense_edge_wins:>4}/{c.n_windows:<4} "
            f"{(c.worst_window_cagr_pct or 0):>8.1f}"
        )
    lines.append("-" * len(head))
    champ = report.champion
    if champ is not None:
        lines.append(
            f"\n챔피언: {champ.label} — {_VERDICT_MARK.get(champ.verdict, champ.verdict)}"
            f"\n  {champ.reason}"
        )
    else:
        lines.append(
            "\n챔피언 없음: 어느 추세 후보도 깊은 OOS 에서 단순 보유 대비 강건한 엣지(방어"
            " 포함)를 못 냄. → 전략 연구가 진짜 과제(추세추종 외 비상관 차원)."
        )
    lines.append(
        "\n해석: '구간 샤프 승'이 낮아도(강세장 구간엔 보험료) '전체 낙폭↓ + 칼마↑'면"
        " 방어 엣지다 — 추세추종의 가치는 폭락 구간에 몰려 있어 단일 강세장 창에선 안 보인다."
        " '최악 구간%'(최악 5년 연환산)에서 후보가 벤치마크보다 덜 빠지는 정도가 방어의 실측."
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--from-year",
        type=int,
        default=GOLD_FLOAT_YEAR,
        help=f"시작 연도(기본 {GOLD_FLOAT_YEAR}=금 자유변동 — 정직한 핵심).",
    )
    ap.add_argument("--window", type=int, default=10, help="추세 SMA 개월(고전 10).")
    ap.add_argument(
        "--segment-months", type=int, default=60, help="walk-forward 구간 길이(개월)."
    )
    ap.add_argument(
        "--min-window-months", type=int, default=24, help="구간 최소 길이(통계 정의)."
    )
    ap.add_argument(
        "--include-windows",
        action="store_true",
        help="JSON 에 구간별 상세 포함.",
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

    rows = [r for r in all_rows if int(r.date[:4]) >= args.from_year]
    if len(rows) < args.min_window_months + 1:
        print(
            f"데이터 부족: {args.from_year}~ 행 {len(rows)}개 < 최소"
            f" {args.min_window_months + 1}",
            file=sys.stderr,
        )
        return 1
    gold_levels = align_gold_levels(rows, gold_by_month)
    print(
        f"  {args.from_year}~: 주식·채권 {len(rows)}개월"
        f" ({rows[0].date} … {rows[-1].date})\n",
        file=sys.stderr,
    )

    report = deep_walk_forward_compare(
        rows,
        gold_levels,
        window=args.window,
        segment_months=args.segment_months,
        min_window_months=args.min_window_months,
    )

    if args.json:
        print(
            json.dumps(
                report.as_dict(include_windows=args.include_windows),
                ensure_ascii=False,
            )
        )
    else:
        print(_fmt_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
