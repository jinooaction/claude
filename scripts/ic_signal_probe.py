"""스펙 041 — 1순위 신호 탐색: 12-1 모멘텀 + 단기(1주) 반전 IC 실측.

운영자 1순위 지시(2026-06-05): 가격 신호 중 학술 근거가 가장 강한 두 가지를 정직하게 재고
멈춤 규칙을 적용한다.

  1) 12-1 모멘텀 — 최근 1개월(반전 구간)을 빼고 그 이전 11개월 수익률(Jegadeesh-Titman).
     우리가 그동안 잰 건 최근 끝까지 포함한 6/12개월 모멘텀이라, "제대로 된 모멘텀"을 안 쟀다.
  2) 단기 반전 — 최근 1주 하락폭이 큰 종목이 되튀는 효과(신호 = -최근수익률).

엔진은 검증된 `analytics.signal_ic.cross_sectional_ic`(= 운영 `strategy.factors.composite_scores`)
를 그대로 재사용한다. 이 스크립트는 여러 신호를 한 번에 돌려 비교표만 찍는 얇은 드라이버다.
미래 누출 0(매 시점 그 시점까지의 바로만 점수 계산), 비겹침 표본(step=horizon)으로 t-통계
과대평가를 막는다. 읽기 전용 — 주문 0건, 돈 0 이동.

멈춤 규칙(운영자 합의): 표본 시점 N≥30 에서 두 신호 모두 평균 IC>0 & t≥2 를 못 넘으면
가격 신호 탐색은 종료한다(무한 튜닝 금지 = 잡음 쫓기 금지).

사용:
    uv run python scripts/load_historical_bars.py --db data/ic_research.db
    uv run python scripts/ic_signal_probe.py --db data/ic_research.db
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from auto_invest.analytics.signal_ic import cross_sectional_ic
from auto_invest.market_data.store import get_bars
from auto_invest.persistence import db

# (라벨, 가중치, momentum_period, momentum_gap_lag, [측정 수평선들])
_SIGNALS: list[tuple[str, dict[str, Decimal], int, int, list[int]]] = [
    # 베이스라인(이미 측정된 6개월 모멘텀, 재확인용 — IC≈0 일 것으로 예상).
    ("모멘텀 6개월(120, 끝까지)", {"momentum": Decimal("1")}, 120, 0, [21, 63]),
    # 1순위 신호 A — 12-1 모멘텀(231바 ≈ 11개월, 최근 21바 ≈ 1개월 제외).
    ("12-1 모멘텀(231, 최근21 제외)", {"momentum_gap": Decimal("1")}, 231, 21, [21, 63]),
    # 1순위 신호 B — 단기 반전(최근 5바 ≈ 1주 음의 수익률 = 되튐).
    ("단기 반전(1주, -5바 수익률)", {"short_reversal": Decimal("1")}, 5, 0, [5, 21]),
]

_N_MIN = 30  # 멈춤 규칙: 이 시점 수 이상에서 판정해야 잡음/소표본 환상 배제.


def _load_symbol_bars(conn, *, timeframe: str) -> dict[str, list]:
    rows = conn.execute(
        "SELECT DISTINCT symbol FROM price_bars WHERE timeframe = ? ORDER BY symbol",
        (timeframe,),
    ).fetchall()
    symbols = [r[0] for r in rows]
    return {s: get_bars(conn, symbol=s, timeframe=timeframe) for s in symbols}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/ic_research.db")
    ap.add_argument("--timeframe", default="1d")
    ap.add_argument("--min-symbols", type=int, default=5)
    ap.add_argument("--json", action="store_true", help="JSON 도 함께 출력.")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(
            f"DB 없음: {db_path}. 먼저 scripts/load_historical_bars.py 로 적재하세요.",
            file=sys.stderr,
        )
        return 2

    conn = db.get_connection(db_path)
    db.migrate(conn)
    try:
        symbol_bars = _load_symbol_bars(conn, timeframe=args.timeframe)
    finally:
        conn.close()

    n_syms = sum(1 for b in symbol_bars.values() if b)
    depth = max((len(b) for b in symbol_bars.values()), default=0)
    print(f"유니버스 {n_syms}종목, 최대 바 깊이 {depth} (DB={db_path})\n", file=sys.stderr)

    print(f"{'신호':<28} {'H':>4} {'평균IC':>9} {'t':>7} {'적중':>6} {'N':>4}  판정")
    print("-" * 92)

    records: list[dict] = []
    passed_any = False
    for label, weights, mom_period, gap_lag, horizons in _SIGNALS:
        for h in horizons:
            res = cross_sectional_ic(
                symbol_bars,
                weights=weights,
                lookback_bars=max(mom_period, 60),
                momentum_period=mom_period,
                momentum_gap_lag=gap_lag,
                forward_horizon=h,
                step=h,  # 비겹침
                min_symbols=args.min_symbols,
            )
            d = res.as_dict()
            d["signal"] = label
            records.append(d)
            # 멈춤 규칙: 충분 표본(N≥_N_MIN) + 양의 IC + 유의(t≥2).
            cleared = res.n_dates >= _N_MIN and res.mean_ic > 0 and res.t_stat >= 2.0
            passed_any = passed_any or cleared
            flag = "  ✅엣지" if cleared else ""
            print(
                f"{label:<28} {h:>4} {res.mean_ic:>+9.4f} {res.t_stat:>+7.2f} "
                f"{res.hit_rate:>5.0%} {res.n_dates:>4}  {res.verdict}{flag}"
            )

    print("-" * 92)
    print(
        f"멈춤 규칙(N≥{_N_MIN} & IC>0 & t≥2): "
        + ("엣지 발견 → 전략 재설계 검토" if passed_any else "엣지 없음 → 가격 신호 탐색 종료 권고")
    )

    if args.json:
        print(json.dumps(records, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
