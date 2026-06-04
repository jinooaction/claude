"""스펙 041 — 과거 실데이터로 합성 점수의 예측 성공률(IC)을 실측하기 위한 적재기.

이 컨테이너의 네트워크는 GitHub 만 허용한다(Stooq/Yahoo 차단). GitHub raw 에 있는 실제
일봉 데이터(plotly all_stocks_5yr: ~500 S&P 종목, 2013-02 … 2018-02)를 받아 로컬 price_bars
DB 에 적재하고, 그 시대 유니버스로 `auto-invest signal-ic` 를 돌릴 수 있게 한다.

읽기/측정 전용 — 주문 0건, 라이브 무관, 돈 0 이동. 데이터는 2013-2018 regime 이라 "지금
통한다"의 증명이 아니라 "이 합성 점수가 실제 다년 횡단면에서 예측력이 있었는가"의 측정이다.

사용:
    uv run python scripts/load_historical_bars.py --db data/ic_research.db \
        --portfolio-out deploy/ic-research-portfolio.toml
    uv run auto-invest signal-ic --portfolio deploy/ic-research-portfolio.toml \
        --db data/ic_research.db --forward-horizon 21
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

from auto_invest.market_data.store import _utcnow_iso_ms  # noqa: PLC2701
from auto_invest.persistence import db

SOURCE_URL = "https://raw.githubusercontent.com/plotly/datasets/master/all_stocks_5yr.csv"


def _fetch_rows() -> list[tuple[str, str, str, str, str, str, str]]:
    print(f"downloading {SOURCE_URL} …", file=sys.stderr)
    raw = urllib.request.urlopen(SOURCE_URL, timeout=60).read().decode()  # noqa: S310
    reader = csv.reader(io.StringIO(raw))
    next(reader, None)  # header: date,open,high,low,close,volume,Name
    rows = [tuple(r) for r in reader if len(r) == 7]
    print(f"  {len(rows)} raw rows", file=sys.stderr)
    return rows  # type: ignore[return-value]


def _sanitize(
    rows: list[tuple[str, str, str, str, str, str, str]],
) -> dict[str, list[tuple]]:
    """종목별 (bar_open_utc, o, h, l, c, volume) — 비정상행 제거, low/high 클램프."""
    by_sym: dict[str, list[tuple]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for d, o, h, lo, c, v, name in rows:
        key = (name, d)
        if key in seen:
            continue
        try:
            of, hf, lof, cf = float(o), float(h), float(lo), float(c)
            vol = int(float(v))
        except (ValueError, TypeError):
            continue
        if min(of, hf, lof, cf) <= 0 or vol < 0:
            continue
        lo_adj = min(lof, of, cf)
        hi_adj = max(hf, of, cf)
        by_sym[name].append(
            (
                f"{d}T00:00:00.000Z",
                f"{of:.4f}",
                f"{hi_adj:.4f}",
                f"{lo_adj:.4f}",
                f"{cf:.4f}",
                vol,
            )
        )
        seen.add(key)
    for name in by_sym:
        by_sym[name].sort(key=lambda r: r[0])
    return by_sym


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/ic_research.db")
    ap.add_argument("--portfolio-out", default="deploy/ic-research-portfolio.toml")
    ap.add_argument("--min-bars", type=int, default=400, help="이 미만 종목은 제외.")
    args = ap.parse_args()

    by_sym = _sanitize(_fetch_rows())
    # 화이트리스트 검증기 규칙: ^[A-Z][A-Z0-9]{0,9}$ (점 티커 BF.B/BRK.B 등 제외).
    eligible = re.compile(r"^[A-Z][A-Z0-9]{0,9}$")
    syms = sorted(
        s
        for s, bars in by_sym.items()
        if len(bars) >= args.min_bars and eligible.match(s)
    )
    print(f"적재 종목 {len(syms)}개 (각 ≥{args.min_bars} 바)", file=sys.stderr)

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    db.migrate(conn)
    now = _utcnow_iso_ms()
    total = 0
    for s in syms:
        payload = [
            (s, "1d", b[0], b[1], b[2], b[3], b[4], b[5], now) for b in by_sym[s]
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO price_bars "
            "(symbol, timeframe, bar_open_utc, o, h, l, c, volume, ingested_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            payload,
        )
        total += len(payload)
    conn.commit()
    conn.close()
    print(f"price_bars 적재 완료: {total} 바 / {len(syms)} 종목 → {db_path}", file=sys.stderr)

    arr = "[" + ", ".join(f'"{s}"' for s in syms) + "]"
    toml = f"""# 스펙 041 — IC 실측용 연구 포트폴리오 (2013-2018 plotly S&P 데이터, 측정 전용).
# auto-invest signal-ic 가 이 유니버스/가중치/룩백으로 합성 점수의 예측 성공률을 잰다.
# PAPER/측정 전용 — 주문 0건. forward 설정(canary-portfolio.toml)과 동일한 가중치·룩백.
[caps]
per_trade_pct                  = 10.0
per_symbol_pct                 = 25.0
global_exposure_pct            = 100.0
canary_capital_pct             = 5.0
canary_min_duration_days       = 10
canary_acceptance_drawdown_pct = 30.0

[whitelist]
symbols     = {arr}
accounts    = ["BACKTEST"]
order_types = ["LIMIT"]
sessions    = ["REGULAR"]

[portfolio]
id            = "ic-research"
universe      = {arr}
weights       = {{ momentum = "1.0", quality = "1.0", low_volatility = "0.5" }}
weight_scheme = "equal"
top_n         = 10
lookback_bars   = 60
momentum_period = 40
"""
    Path(args.portfolio_out).write_text(toml, encoding="utf-8")
    print(f"연구 포트폴리오 작성: {args.portfolio_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
