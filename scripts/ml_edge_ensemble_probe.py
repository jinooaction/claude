#!/usr/bin/env python3
"""Run the spec-145 no-live ML edge experiment."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from auto_invest.analytics.global_trend import align_gold_levels, parse_gold
from auto_invest.analytics.ml_edge_ensemble import render_markdown, run_ml_edge_ensemble
from auto_invest.analytics.risk_managed_beta import parse_shiller

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"


def _read(source: str | None, url: str) -> str:
    if source:
        return Path(source).read_text(encoding="utf-8")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        return response.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shiller", help="optional local Shiller CSV")
    parser.add_argument("--gold", help="optional local monthly gold CSV")
    parser.add_argument("--from-year", type=int, default=1971)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    try:
        rows = [
            row
            for row in parse_shiller(_read(args.shiller, SHILLER_URL))
            if int(row.date[:4]) >= args.from_year
        ]
        gold_levels = align_gold_levels(rows, parse_gold(_read(args.gold, GOLD_URL)))
        report = run_ml_edge_ensemble(rows, gold_levels)
    except Exception as exc:
        print(f"ml-edge-ensemble blocked: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, indent=2)
    markdown = render_markdown(report)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(markdown, encoding="utf-8")
    print(payload if args.json else markdown, end="" if args.json else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
