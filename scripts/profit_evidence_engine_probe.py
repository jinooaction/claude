#!/usr/bin/env python3
"""스펙 138 - 공개 데이터와 forward 증거를 결합하는 no-live probe."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

from auto_invest.analytics.global_trend import align_gold_levels, parse_gold
from auto_invest.analytics.profit_evidence_engine import build_profit_evidence_report
from auto_invest.analytics.risk_managed_beta import parse_shiller

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_text(path: Path | None, url: str) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        return response.read().decode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shiller-file", type=Path)
    parser.add_argument("--gold-file", type=Path)
    parser.add_argument("--leaderboard", type=Path)
    parser.add_argument("--annual-cost-bps", type=int, default=50)
    parser.add_argument("--holdout-year", type=int, default=2007)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        shiller_text = _read_text(args.shiller_file, SHILLER_URL)
        gold_text = _read_text(args.gold_file, GOLD_URL)
        rows = [row for row in parse_shiller(shiller_text) if int(row.date[:4]) >= 1971]
        gold_levels = align_gold_levels(rows, parse_gold(gold_text))
        report = build_profit_evidence_report(
            rows,
            gold_levels,
            leaderboard=_read_json(args.leaderboard),
            annual_cost_bps=args.annual_cost_bps,
            holdout_year=args.holdout_year,
        )
    except (OSError, ValueError) as exc:
        print(f"profit evidence input error: {exc}", file=sys.stderr)
        return 2

    payload = report.as_dict()
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(report.as_markdown() + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(report.as_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
