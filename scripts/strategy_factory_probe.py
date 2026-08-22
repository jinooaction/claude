#!/usr/bin/env python3
"""Run the no-live 64-trial autonomous strategy factory."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from auto_invest.analytics.global_trend import align_gold_levels, parse_gold
from auto_invest.analytics.risk_managed_beta import parse_shiller
from auto_invest.analytics.strategy_factory import (
    render_factory_markdown,
    run_strategy_factory,
)

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"


def _read(path: Path | None, url: str) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        return response.read().decode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shiller-file", type=Path)
    parser.add_argument("--gold-file", type=Path)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--batch-sequence", type=int, default=0)
    parser.add_argument("--prior-ledger", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = [
            row
            for row in parse_shiller(_read(args.shiller_file, SHILLER_URL))
            if int(row.date[:4]) >= 1971
        ]
        gold = align_gold_levels(rows, parse_gold(_read(args.gold_file, GOLD_URL)))
        prior_records = []
        if args.prior_ledger is not None and args.prior_ledger.exists():
            for line in args.prior_ledger.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    prior_records.append(json.loads(line))
        payload = run_strategy_factory(
            rows,
            gold,
            code_commit=args.code_commit,
            timestamp_utc=args.timestamp_utc,
            batch_sequence=args.batch_sequence,
            prior_trial_records=prior_records,
        )
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"strategy factory input error: {exc}", file=sys.stderr)
        return 2
    summary = render_factory_markdown(payload)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False) if args.json else summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
