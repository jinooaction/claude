#!/usr/bin/env python3
"""Run the no-order preregistered turn-of-month research factory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.options_variance_risk_premium_factory import (
    FRENCH_DAILY_URL,
    parse_fama_french_daily,
)
from auto_invest.analytics.turn_of_month_equity_factory import (
    build_french_daily_bundle,
    render_turn_of_month_markdown,
    run_turn_of_month_equity_factory,
)


def _read_bytes(path: Path | None) -> bytes:
    if path is not None:
        return path.read_bytes()
    request = urllib.request.Request(  # noqa: S310
        FRENCH_DAILY_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read()


def _object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--french-daily-file", type=Path)
    parser.add_argument("--prior-factory-json", type=Path, required=True)
    parser.add_argument("--released-regime-json", type=Path, required=True)
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
        raw = _read_bytes(args.french_daily_file)
        bundle = build_french_daily_bundle(
            parse_fama_french_daily(raw),
            content_digest="sha256:" + hashlib.sha256(raw).hexdigest(),
            current_date=current_date,
        )
        prior = _object(args.prior_factory_json)
        prior_rows = prior.get("audit_records")
        if not isinstance(prior_rows, list):
            raise ValueError("prior factory audit_records are missing")
        payload = run_turn_of_month_equity_factory(
            bundle=bundle,
            prior_audit_records=prior_rows,
            released_regime_result=_object(args.released_regime_json),
            calibration=_object(args.calibration_json),
            code_commit=args.code_commit,
            generated_at=timestamp,
        )
    except (KeyError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Turn-of-month factory input error: {exc}", file=sys.stderr)
        return 2

    summary = render_turn_of_month_markdown(payload)
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
