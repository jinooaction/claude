#!/usr/bin/env python3
"""Run the no-order spec-163 independent energy cross-market factory."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

from auto_invest.analytics.energy_cross_market_factory import (
    EIA_SERIES,
    FRENCH_URL,
    load_energy_cross_market_bundle,
    render_energy_cross_market_markdown,
    run_energy_cross_market_factory,
    validate_energy_cross_market_bundle,
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
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read()


def _eia_inputs(directory: Path | None) -> dict[str, bytes]:
    return {
        series_id: _read_bytes(
            None if directory is None else directory / Path(urlparse(spec.url).path).name,
            spec.url,
        )
        for series_id, spec in EIA_SERIES.items()
    }


def _previous_month(value: str) -> str:
    current = date.fromisoformat(value)
    if current.month == 1:
        return date(current.year - 1, 12, 1).isoformat()
    return date(current.year, current.month - 1, 1).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eia-data-dir", type=Path)
    parser.add_argument("--french-industry-file", type=Path)
    parser.add_argument("--shiller-file", type=Path)
    parser.add_argument("--gold-file", type=Path)
    parser.add_argument("--macro-data-dir", type=Path, required=True)
    parser.add_argument("--prior-factory-json", type=Path, required=True)
    parser.add_argument("--calibration-json", type=Path, required=True)
    parser.add_argument("--controls-json", type=Path, required=True)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    timestamp = args.timestamp_utc or datetime.now(UTC).isoformat()
    try:
        current_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
        cash_text = (args.macro_data_dir / "fred" / "DGS3MO.csv").read_text(
            encoding="utf-8"
        )
        bundle = load_energy_cross_market_bundle(
            _eia_inputs(args.eia_data_dir),
            _read_bytes(args.french_industry_file, FRENCH_URL),
            parse_fred_csv(cash_text),
            current_date=current_date,
        )
        validate_energy_cross_market_bundle(bundle)
        shiller_text = _read_bytes(args.shiller_file, SHILLER_URL).decode()
        shiller_by_month = {row.date[:7]: row for row in parse_shiller(shiller_text)}
        row_months = [_previous_month(bundle.factor_months[0]), *bundle.factor_months]
        rows = [shiller_by_month[month[:7]] for month in row_months]
        gold_text = _read_bytes(args.gold_file, GOLD_URL).decode()
        gold = align_gold_levels(rows, parse_gold(gold_text))
        prior = json.loads(args.prior_factory_json.read_text(encoding="utf-8"))
        calibration = json.loads(args.calibration_json.read_text(encoding="utf-8"))
        controls = json.loads(args.controls_json.read_text(encoding="utf-8"))
        payload = run_energy_cross_market_factory(
            rows,
            gold,
            bundle,
            prior_factory_payload=prior,
            calibration_evidence=calibration,
            full_gate_controls=controls,
            code_commit=args.code_commit,
            timestamp_utc=timestamp,
        )
    except (KeyError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Energy cross-market factory input error: {exc}", file=sys.stderr)
        return 2

    summary = render_energy_cross_market_markdown(payload)
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
