#!/usr/bin/env python3
"""Run the no-order spec-164 options variance-risk-premium factory."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.options_variance_risk_premium_factory import (
    FRENCH_DAILY_URL,
    PUT_URL,
    VIX_URL,
    load_options_premium_bundle,
    render_options_variance_risk_premium_markdown,
    run_options_variance_risk_premium_factory,
    validate_options_premium_bundle,
)
from auto_invest.market_data.public_data import parse_fred_csv


def _read_bytes(path: Path | None, url: str) -> bytes:
    if path is not None:
        return path.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read()


def _named_payloads(values: list[str]) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not name.strip() or not raw_path.strip():
            raise ValueError("prior family JSON must use NAME=PATH")
        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("prior family JSON root must be an object")
        output[name.strip()] = payload
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--put-file", type=Path)
    parser.add_argument("--vix-file", type=Path)
    parser.add_argument("--french-daily-file", type=Path)
    parser.add_argument("--macro-data-dir", type=Path, required=True)
    parser.add_argument("--prior-factory-json", type=Path, required=True)
    parser.add_argument(
        "--prior-family-json",
        action="append",
        default=[],
        metavar="NAME=PATH",
    )
    parser.add_argument("--calibration-json", type=Path, required=True)
    parser.add_argument("--controls-json", type=Path, required=True)
    parser.add_argument("--calibration-repetitions", type=int, default=500)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    timestamp = args.timestamp_utc or datetime.now(UTC).isoformat()
    try:
        current_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
        cash_text = (args.macro_data_dir / "fred" / "DGS3MO.csv").read_text(encoding="utf-8")
        bundle = load_options_premium_bundle(
            _read_bytes(args.put_file, PUT_URL),
            _read_bytes(args.vix_file, VIX_URL),
            _read_bytes(args.french_daily_file, FRENCH_DAILY_URL),
            parse_fred_csv(cash_text),
            current_date=current_date,
        )
        validate_options_premium_bundle(bundle)
        prior = json.loads(args.prior_factory_json.read_text(encoding="utf-8"))
        calibration = json.loads(args.calibration_json.read_text(encoding="utf-8"))
        controls = json.loads(args.controls_json.read_text(encoding="utf-8"))
        payload = run_options_variance_risk_premium_factory(
            bundle,
            prior_factory_payload=prior,
            prior_family_payloads=_named_payloads(args.prior_family_json),
            calibration_evidence=calibration,
            full_gate_controls=controls,
            code_commit=args.code_commit,
            timestamp_utc=timestamp,
            calibration_repetitions=args.calibration_repetitions,
        )
    except (KeyError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Options variance-risk-premium factory input error: {exc}", file=sys.stderr)
        return 2

    summary = render_options_variance_risk_premium_markdown(payload)
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
