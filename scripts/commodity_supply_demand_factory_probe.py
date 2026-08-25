#!/usr/bin/env python3
"""Run the no-order spec-158 commodity supply-demand and full-gate audit."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.commodity_supply_demand_factory import (
    BLACKROCK_URL,
    EIA_URLS,
    load_supply_demand_bundle,
    render_supply_demand_factory_markdown,
    run_commodity_supply_demand_factory,
)
from auto_invest.analytics.global_trend import (
    align_gold_levels,
    gold_total_return_factors,
    parse_gold,
)
from auto_invest.analytics.multi_asset_trend import bond_total_return_factors
from auto_invest.analytics.real_world_gate_controls import (
    AQR_TSMOM_URL,
    FAMA_FRENCH_URL,
    parse_aqr_tsmom_monthly,
    run_full_gate_control_audit,
    run_real_world_gate_audit,
)
from auto_invest.analytics.risk_managed_beta import market_total_return_factors, parse_shiller
from auto_invest.market_data.public_data import parse_fred_csv

SHILLER_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
GOLD_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"


def _read_bytes(path: Path | None, url: str) -> bytes:
    if path is not None:
        return path.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fama-french-file", type=Path)
    parser.add_argument("--aqr-tsmom-file", type=Path)
    parser.add_argument("--blackrock-file", type=Path)
    parser.add_argument("--eia-data-dir", type=Path)
    parser.add_argument("--shiller-file", type=Path)
    parser.add_argument("--gold-file", type=Path)
    parser.add_argument("--macro-data-dir", type=Path, required=True)
    parser.add_argument("--prior-factory-json", type=Path, required=True)
    parser.add_argument("--calibration-json", type=Path, required=True)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--controls-json-out", type=Path)
    parser.add_argument("--psr-controls-json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    timestamp = args.timestamp_utc or datetime.now(UTC).isoformat()
    try:
        current_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
        fama_raw = _read_bytes(args.fama_french_file, FAMA_FRENCH_URL)
        aqr_raw = _read_bytes(args.aqr_tsmom_file, AQR_TSMOM_URL)
        psr_controls = run_real_world_gate_audit(
            fama_raw,
            aqr_raw,
            current_date=current_date,
            code_commit=args.code_commit,
            timestamp_utc=timestamp,
        )
        blackrock_raw = _read_bytes(args.blackrock_file, BLACKROCK_URL)
        eia_raw = {
            series_id: _read_bytes(
                args.eia_data_dir / f"{series_id}w.xls" if args.eia_data_dir else None,
                url,
            )
            for series_id, url in EIA_URLS.items()
        }
        cash_text = (args.macro_data_dir / "fred" / "DGS3MO.csv").read_text(encoding="utf-8")
        bundle = load_supply_demand_bundle(
            blackrock_raw,
            eia_raw,
            parse_fred_csv(cash_text),
            current_date=current_date,
        )
        shiller_text = _read_bytes(args.shiller_file, SHILLER_URL).decode()
        shiller_by_month = {row.date[:7]: row for row in parse_shiller(shiller_text)}
        rows = [shiller_by_month[month[:7]] for month in bundle.dates]
        gold_text = _read_bytes(args.gold_file, GOLD_URL).decode()
        gold = align_gold_levels(rows, parse_gold(gold_text))
        incumbent_assets = [
            market_total_return_factors(rows),
            bond_total_return_factors(rows),
            gold_total_return_factors(gold),
        ]
        incumbent = [sum(values) / 3.0 for values in zip(*incumbent_assets, strict=True)]
        cash = [1.0 + rate / 1200.0 for rate in bundle.cash_rates[:-1]]
        factor_months = [month[:7] for month in bundle.dates[1:]]
        aqr = parse_aqr_tsmom_monthly(aqr_raw)["all"]
        common_indices = [
            index
            for index, month in enumerate(factor_months)
            if month >= "2007-01" and month in aqr
        ]
        controls = run_full_gate_control_audit(
            aqr,
            months=[factor_months[index] for index in common_indices],
            cash_factors=[cash[index] for index in common_indices],
            incumbent_factors=[incumbent[index] for index in common_indices],
            psr_controls=psr_controls,
            code_commit=args.code_commit,
            timestamp_utc=timestamp,
        )
        prior = json.loads(args.prior_factory_json.read_text(encoding="utf-8"))
        calibration = json.loads(args.calibration_json.read_text(encoding="utf-8"))
        payload = run_commodity_supply_demand_factory(
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
        print(f"Commodity supply-demand factory input error: {exc}", file=sys.stderr)
        return 2

    summary = render_supply_demand_factory_markdown(payload)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.controls_json_out is not None:
        args.controls_json_out.parent.mkdir(parents=True, exist_ok=True)
        args.controls_json_out.write_text(
            json.dumps(controls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.psr_controls_json_out is not None:
        args.psr_controls_json_out.parent.mkdir(parents=True, exist_ok=True)
        args.psr_controls_json_out.write_text(
            json.dumps(psr_controls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(summary + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False) if args.json else summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
