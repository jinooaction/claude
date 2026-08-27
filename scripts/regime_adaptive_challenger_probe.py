#!/usr/bin/env python3
"""Run the preregistered regime challenger with public monthly data and no broker calls."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from auto_invest.analytics.global_trend import align_gold_levels, parse_gold
from auto_invest.analytics.regime_adaptive_challenger import (
    evaluate_regime_challenger,
    report_markdown,
    validate_report_payload,
)
from auto_invest.analytics.risk_managed_beta import parse_shiller

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"


def _read_text(path: Path | None, url: str) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        return response.read().decode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--shiller-file", type=Path)
    parser.add_argument("--gold-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        rows = [
            row
            for row in parse_shiller(_read_text(args.shiller_file, SHILLER_URL))
            if int(row.date[:4]) >= 1971
        ]
        gold_levels = align_gold_levels(rows, parse_gold(_read_text(args.gold_file, GOLD_URL)))
        payload = evaluate_regime_challenger(rows, gold_levels, contract)
        validate_report_payload(payload, contract)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"regime challenger input error: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(report_markdown(payload) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(report_markdown(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
