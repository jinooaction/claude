"""스펙 046 — 일일 전략 모니터 드라이버: 검증된 스펙(042~045)을 합친 지속 감시 대시보드.

운영자 지시: "이어서 자율 수행해. 세계 최고 수준으로 돈 벌자." forward 페이퍼 트랙이 돌 때마다
(또는 수동) 운영자가 한눈에 확인할 일일 판정 — 엣지 최근 유효성 / 분산 가정 신뢰도 / 레버리지
복리 권고 / 오늘 추세 신호.

읽기 전용 — 주문 0건, 돈 0 이동. 사용:
  uv run python scripts/strategy_monitor_probe.py [--window 10] [--dd-budget 15] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

from auto_invest.analytics.risk_managed_beta import parse_shiller
from auto_invest.analytics.strategy_monitor import build_dashboard

SOURCE_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--dd-budget", type=float, default=15.0, help="감내 최대낙폭(%) 예산.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    print(f"내려받기 {SOURCE_URL} …", file=sys.stderr)
    raw = urllib.request.urlopen(SOURCE_URL, timeout=60).read().decode()  # noqa: S310
    rows = parse_shiller(raw)
    print(f"  {len(rows)}개월 ({rows[0].date} … {rows[-1].date})\n", file=sys.stderr)

    dash = build_dashboard(rows, window=args.window, dd_budget_pct=args.dd_budget)
    if args.json:
        print(json.dumps(dash.as_dict(), ensure_ascii=False))
    else:
        print(dash.as_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
