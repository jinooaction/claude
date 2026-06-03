"""Fetch a real US-equity daily-OHLCV subset for spec 032 portfolio backtests.

The container's network policy blocks finance data hosts (Yahoo/Stooq → 403) but
allows GitHub raw + PyPI (git/uv work). So we pull a well-known *real* dataset
mirrored on GitHub — the S&P 500 5-year daily OHLCV set (`all_stocks_5yr.csv`,
2013-02-08 … 2018-02-07, ~500 tickers) — and split a chosen liquid large-cap
universe into per-symbol CSVs in the `ingest-history` format
(`session_date,open,high,low,close,volume,session_schedule_tag`).

Read-only public market data; no money, no secrets. Output feeds
`auto-invest ingest-history` → `auto-invest backtest-portfolio` so the
rebalancing engine is measured on REAL prices, not synthetic walks.

Usage:
    python scripts/fetch_sp500_subset.py --out data/history_csv_sp500
    auto-invest ingest-history --from-dir data/history_csv_sp500
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/all_stocks_5yr.csv"
)

# Liquid large caps present across the full 2013-2018 window (FB = pre-rename Meta).
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "FB",
    "JPM", "JNJ", "XOM", "PG", "HD",
    "KO", "WMT", "INTC", "CSCO", "DIS",
]


def _clean_rows(rows: list[tuple[str, str, str, str, str, str]]):
    """Sanitize raw (date,o,h,l,c,v) rows: drop NaN/empty/non-positive, clamp
    low/high so the ingest range-sanity rule (low<=min(o,c)<=max(o,c)<=high) holds."""
    out = []
    seen: set[str] = set()
    for d, o, h, lo, c, v in rows:
        if d in seen:
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
        out.append((d, f"{of:.4f}", f"{hi_adj:.4f}", f"{lo_adj:.4f}", f"{cf:.4f}", str(vol)))
        seen.add(d)
    out.sort(key=lambda r: r[0])  # ascending session_date (ingest rule 7)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/history_csv_sp500", help="Output dir.")
    ap.add_argument("--universe", nargs="*", default=DEFAULT_UNIVERSE)
    ap.add_argument(
        "--all",
        action="store_true",
        help="Extract EVERY ticker present in the dataset (the full ~500-name "
        "cross-section), ignoring --universe. World-class cross-sectional factor "
        "investing needs breadth, not a hand-picked handful (spec 034).",
    )
    args = ap.parse_args()
    universe = {s.upper() for s in args.universe}

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"downloading {SOURCE_URL} …", file=sys.stderr)
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")

    by_symbol: dict[str, list] = {} if args.all else {s: [] for s in universe}
    reader = csv.reader(io.StringIO(raw))
    next(reader, None)  # header: date,open,high,low,close,volume,Name
    for row in reader:
        if len(row) != 7:
            continue
        name = row[6].strip().upper()
        if args.all:
            by_symbol.setdefault(name, []).append(
                (row[0], row[1], row[2], row[3], row[4], row[5])
            )
        elif name in by_symbol:
            by_symbol[name].append((row[0], row[1], row[2], row[3], row[4], row[5]))

    if args.all:
        universe = set(by_symbol)

    written = 0
    for sym in sorted(universe):
        rows = _clean_rows(by_symbol.get(sym, []))
        if not rows:
            print(f"  WARN: no rows for {sym}", file=sys.stderr)
            continue
        path = out_dir / f"{sym}.csv"
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["session_date", "open", "high", "low", "close", "volume", "session_schedule_tag"]
            )
            for d, o, h, lo, c, v in rows:
                w.writerow([d, o, h, lo, c, v, "regular"])
        written += 1
        print(f"  {sym}: {len(rows)} bars -> {path}", file=sys.stderr)

    print(f"wrote {written} symbol files to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
