#!/usr/bin/env python3
"""Run the no-order spec-156 commodity term-structure factory."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.commodity_term_structure_factory import (
    BLACKROCK_URL,
    WORLD_BANK_URL,
    load_commodity_bundle,
    render_commodity_factory_markdown,
    run_commodity_term_structure_factory,
)
from auto_invest.analytics.global_trend import align_gold_levels, parse_gold
from auto_invest.analytics.risk_managed_beta import parse_shiller
from auto_invest.market_data.public_data import parse_fred_csv

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"


def _read_bytes(path: Path | None, url: str) -> bytes:
    if path is not None:
        return path.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310
        return response.read()


def _read_text(path: Path | None, url: str) -> str:
    return _read_bytes(path, url).decode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blackrock-file", type=Path)
    parser.add_argument("--world-bank-file", type=Path)
    parser.add_argument("--shiller-file", type=Path)
    parser.add_argument("--gold-file", type=Path)
    parser.add_argument("--macro-data-dir", type=Path, required=True)
    parser.add_argument("--prior-factory-json", type=Path, required=True)
    parser.add_argument("--calibration-json", type=Path, required=True)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    timestamp = args.timestamp_utc or datetime.now(UTC).isoformat()
    try:
        current_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
        blackrock_raw = _read_bytes(args.blackrock_file, BLACKROCK_URL)
        world_bank_raw = _read_bytes(args.world_bank_file, WORLD_BANK_URL)
        cash_text = (args.macro_data_dir / "fred" / "DGS3MO.csv").read_text(encoding="utf-8")
        bundle = load_commodity_bundle(
            blackrock_raw,
            world_bank_raw,
            parse_fred_csv(cash_text),
            current_date=current_date,
        )
        shiller_rows = parse_shiller(_read_text(args.shiller_file, SHILLER_URL))
        by_month = {row.date[:7]: row for row in shiller_rows}
        rows = [by_month[month[:7]] for month in bundle.dates]
        gold = align_gold_levels(rows, parse_gold(_read_text(args.gold_file, GOLD_URL)))
        prior = json.loads(args.prior_factory_json.read_text(encoding="utf-8"))
        calibration = json.loads(args.calibration_json.read_text(encoding="utf-8"))
        payload = run_commodity_term_structure_factory(
            rows,
            gold,
            bundle,
            prior_factory_payload=prior,
            calibration_evidence=calibration,
            code_commit=args.code_commit,
            timestamp_utc=timestamp,
        )
    except (KeyError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Commodity term-structure factory input error: {exc}", file=sys.stderr)
        return 2

    summary = render_commodity_factory_markdown(payload)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False) if args.json else summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
