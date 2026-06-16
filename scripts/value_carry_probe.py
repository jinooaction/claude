"""스펙 054 — 비상관 수익원(밸류·캐리) 분산 이득 실측 probe.

추세추종과 밸류(CAPE)·캐리(E/P vs 금리)의 상관·결합 샤프를 구간별로 잰다 — 비상관 수익원
트랙을 추가할 가치가 있는지 *측정한 것만 배선* 원칙으로 답한다. 결과·해석은
specs/054-uncorrelated-alpha/FINDINGS.md.

데이터: Shiller 월간(1871~, GitHub — 컨테이너에서 닿는 장기 소스). 읽기 전용 — 주문 0건,
돈 0 이동. 미래 누출 0(결정론).

사용: uv run python scripts/value_carry_probe.py [--window 10] [--blend-weight 0.5] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.risk_managed_beta import parse_shiller
from auto_invest.analytics.value_carry import (
    measure_carry_diversification,
    measure_value_diversification,
)

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
# 정직한 구간: 전체(1881~)·현대(1950~)·자유변동(1971~)·최근(1990~).
SEGMENTS = (1881, 1950, 1971, 1990)
_MIN_MONTHS = 121  # CAPE 평활(120) + 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=10, help="추세 SMA 개월(고전 10).")
    ap.add_argument(
        "--blend-weight", type=float, default=0.5, help="결합 시 추세 비중(0.5=50/50)."
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    print(f"내려받기 {SHILLER_URL} …", file=sys.stderr)
    rows = parse_shiller(
        urllib.request.urlopen(SHILLER_URL, timeout=60).read().decode()  # noqa: S310
    )

    results: list[dict] = []
    for fy in SEGMENTS:
        sub = [r for r in rows if int(r.date[:4]) >= fy]
        if len(sub) < _MIN_MONTHS:
            continue
        for fn in (measure_value_diversification, measure_carry_diversification):
            stats = fn(sub, window=args.window, blend_weight=args.blend_weight)
            results.append({"from_year": fy, **stats.as_dict()})

    if args.json:
        print(json.dumps(results, ensure_ascii=False))
        return 0

    print(
        f"\n비상관 수익원 분산 이득 — 추세 SMA {args.window}개월 · 결합 {args.blend_weight}\n"
    )
    hdr = (
        f"{'구간':>6} {'후보':<14} {'판정':<26} {'상관':>6} "
        f"{'추세샤':>6} {'후보샤':>6} {'결합샤':>6}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        corr = r["correlation"]
        cs = f"{corr:.2f}" if corr is not None else "—"
        print(
            f"{r['from_year']}~ {r['candidate_label']:<14} {r['verdict']:<28} {cs:>6} "
            f"{r['trend']['sharpe']:>6.2f} {r['candidate']['sharpe']:>6.2f} "
            f"{r['combined']['sharpe']:>6.2f}"
        )
    print(
        "\n결론: 밸류·캐리 단순 형태는 추세와 상관 0.5~0.6(비상관 아님) — long-only 베타 공유."
        "\n진짜 비상관은 롱숏(베타 중립)/조건부 결합 필요(specs/054 FINDINGS)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
