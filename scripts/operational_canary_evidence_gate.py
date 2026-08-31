#!/usr/bin/env python3
"""Independently validate the bounded operational-canary evidence artifact."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from auto_invest.config.rules import PortfolioRebalanceConfig
from auto_invest.portfolio.autoarm import strategy_fingerprint_digest
from auto_invest.portfolio.operational_canary_evidence import (
    assess_operational_canary_evidence,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-code-commit", required=True)
    parser.add_argument("--live-portfolio", type=Path, required=True)
    parser.add_argument("--validated-portfolio", type=Path, required=True)
    parser.add_argument("--evidence-age-hours", type=float, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        live_raw = tomllib.loads(args.live_portfolio.read_text(encoding="utf-8"))
        validated_raw = tomllib.loads(args.validated_portfolio.read_text(encoding="utf-8"))
        live = PortfolioRebalanceConfig.model_validate(live_raw["portfolio"])
        validated = PortfolioRebalanceConfig.model_validate(validated_raw["portfolio"])
        live_fingerprint = strategy_fingerprint_digest(live)
        validated_fingerprint = strategy_fingerprint_digest(validated)
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError):
        evidence = None
        live_fingerprint = None
        validated_fingerprint = None

    assessment = assess_operational_canary_evidence(
        evidence,
        expected_code_commit=args.expected_code_commit,
        expected_strategy_fingerprint=validated_fingerprint,
        live_strategy_fingerprint=live_fingerprint,
        evidence_age_hours=args.evidence_age_hours,
    )
    payload = assessment.as_dict()
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if assessment.eligible else 3


if __name__ == "__main__":
    raise SystemExit(main())
