"""스펙 032 — 최근(2026년까지) 다자산 월봉 데이터셋 빌더.

운영자 원칙: "최근 5개년 같은 명확한 기준으로 백테스트". 이 컨테이너는 라이브 시세
API(KIS·Yahoo·Stooq)가 네트워크 허용목록에 없어 차단되지만, GitHub raw 는 허용된다.
`datasets` 조직의 시계열은 FRED/공개 소스로 *최근까지* 갱신된다:

  - s-and-p-500 : S&P500 지수 월봉 (~2026-05)
  - gold-prices : 금 월봉 (~2026-03)
  - oil-prices  : WTI 유가 일봉 (~2026-05) → 월말로 리샘플

최근 일봉 *다종목 주식* 은 github 에 깔끔히 없다(그건 라이브 인스턴스에서만). 대신 위
3개 자산군(주식·금·유가)으로 **최근 월봉 횡단면**을 만든다 — 자산군 모멘텀 로테이션은
정당한 전략이고, recency 게이트가 "fresh" 로 통과해 "최근 데이터" 원칙을 충족한다.

전체 공통 히스토리를 적재 형식(session_date,open,high,low,close,volume,
session_schedule_tag)으로 쓴다(월초 날짜). 평가창은 `--trailing-years 5` 로 컷한다
(데이터는 풀로 두고 룩백 확보, 평가만 최근 N년).

가격만 있는 시리즈는 OHLC = close 로 둔다(월봉 종가 기준 모멘텀; 척도 무관 랭킹).
read-only 공개 데이터. 돈 안 움직임.

사용:
    python scripts/fetch_recent_macro.py --out data/history_csv_macro
    auto-invest ingest-history --from-dir data/history_csv_macro
    auto-invest portfolio-walk-forward --portfolio specs/032-portfolio-rebalancing/macro-portfolio.toml \
        --trailing-years 5 --segment-days 365 --num-trials 1
"""

from __future__ import annotations

import argparse
import csv
import urllib.request
from datetime import date
from pathlib import Path

from auto_invest.backtest.data_source import trading_days_between

RAW = "https://raw.githubusercontent.com/datasets/"
SOURCES = {
    "SP500": (RAW + "s-and-p-500/main/data/data.csv", "month1", 1),   # YYYY-MM-01, col1=SP500
    "GOLD": (RAW + "gold-prices/main/data/monthly.csv", "month", 1),  # YYYY-MM, col1=Price
    "WTI": (RAW + "oil-prices/main/data/wti-daily.csv", "daily", 1),  # YYYY-MM-DD, col1=Price
}
UA = {"User-Agent": "Mozilla/5.0"}


def _fetch_rows(url: str) -> list[list[str]]:
    req = urllib.request.Request(url, headers=UA)
    text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    rows = list(csv.reader(text.splitlines()))
    return rows[1:]  # drop header


def _month_close(rows: list[list[str]], date_kind: str, col: int) -> dict[str, float]:
    """{YYYY-MM: close} — 일봉은 월말 관측을 취한다(날짜 오름차순 가정, 마지막이 이김)."""
    out: dict[str, float] = {}
    for r in rows:
        if len(r) <= col or not r[0].strip():
            continue
        raw_date = r[0].strip()
        month = raw_date[:7] if date_kind in ("month1", "daily") else raw_date
        if len(month) != 7:
            continue
        try:
            val = float(r[col])
        except (ValueError, IndexError):
            continue
        if val <= 0:
            continue
        out[month] = val  # daily: later rows overwrite -> month-end-ish
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/history_csv_macro")
    ap.add_argument(
        "--start-month",
        default="2007-01",
        help="Floor month YYYY-MM. Default 2007-01 (XNYS calendar starts 2006-06, "
        "and the trailing-5y eval window only needs recent data + lookback).",
    )
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    by_symbol: dict[str, dict[str, float]] = {}
    for sym, (url, kind, col) in SOURCES.items():
        print(f"fetching {sym} <- {url}")
        by_symbol[sym] = _month_close(_fetch_rows(url), kind, col)
        print(f"  {sym}: {len(by_symbol[sym])} months")

    common = set.intersection(*(set(m) for m in by_symbol.values()))
    months = sorted(m for m in common if m >= args.start_month)
    print(f"common months: {len(months)} ({months[0]} .. {months[-1]})")

    # Snap each month to its LAST real XNYS trading day so every bar's session_date
    # is a valid exchange session (replay computes session-close on the XNYS calendar;
    # a month-start like 2022-01-01 is a holiday and would fail).
    y0, m0 = int(months[0][:4]), int(months[0][5:7])
    sessions = trading_days_between(date(y0, m0, 1), date(2026, 12, 31))
    last_td: dict[str, date] = {}
    for d in sessions:
        last_td[f"{d.year:04d}-{d.month:02d}"] = d  # ascending -> last wins
    months = [m for m in months if m in last_td]
    print(f"snapped to trading days: {len(months)} ({months[0]} .. {months[-1]})")

    for sym, series in by_symbol.items():
        path = out_dir / f"{sym}.csv"
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["session_date", "open", "high", "low", "close", "volume", "session_schedule_tag"]
            )
            for m in months:
                c = f"{series[m]:.4f}"
                # Large synthetic volume so the backtest broker's volume gate
                # (fills only when bar.volume >= order qty) never blocks a fill.
                w.writerow([last_td[m].isoformat(), c, c, c, c, "1000000000", "regular"])
        print(f"  wrote {path} ({len(months)} monthly bars)")
    print(f"done -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
