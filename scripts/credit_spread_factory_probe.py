#!/usr/bin/env python3
"""Run the no-order spec-154 investment-grade credit spread factory."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.credit_spread_factory import (
    load_credit_curve_bundle,
    render_credit_factory_markdown,
    run_credit_spread_factory,
)
from auto_invest.analytics.global_trend import align_gold_levels, parse_gold
from auto_invest.analytics.risk_managed_beta import parse_shiller

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
    parser.add_argument("--macro-data-dir", type=Path, required=True)
    parser.add_argument("--prior-factory-json", type=Path, required=True)
    parser.add_argument("--macro-factory-json", type=Path, required=True)
    parser.add_argument("--prior-ledger", type=Path, required=True)
    parser.add_argument("--calibration-json", type=Path, required=True)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    timestamp = args.timestamp_utc or datetime.now(UTC).isoformat()
    try:
        rows = [
            row
            for row in parse_shiller(_read(args.shiller_file, SHILLER_URL))
            if row.date >= "1990-01-01"
        ]
        gold = align_gold_levels(rows, parse_gold(_read(args.gold_file, GOLD_URL)))
        current_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
        snapshots, quality = load_credit_curve_bundle(
            args.macro_data_dir, [row.date for row in rows] + [current_date]
        )
        prior_payload = json.loads(args.prior_factory_json.read_text(encoding="utf-8"))
        macro_payload = json.loads(args.macro_factory_json.read_text(encoding="utf-8"))
        calibration_payload = json.loads(args.calibration_json.read_text(encoding="utf-8"))
        prior_records = [
            json.loads(line)
            for line in args.prior_ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        payload = run_credit_spread_factory(
            rows,
            gold,
            snapshots[:-1],
            live_snapshot=snapshots[-1],
            credit_data_quality=quality,
            prior_trial_records=prior_records,
            prior_factory_payload=prior_payload,
            macro_factory_payload=macro_payload,
            calibration_evidence=calibration_payload,
            code_commit=args.code_commit,
            timestamp_utc=timestamp,
        )
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Credit spread factory input error: {exc}", file=sys.stderr)
        return 2

    summary = render_credit_factory_markdown(payload)
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
