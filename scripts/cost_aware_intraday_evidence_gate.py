#!/usr/bin/env python3
"""Independently reconstruct spec 190 evidence from original bar inputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from cost_aware_intraday_probe import ROOT, read_bundle, verified_development_inputs

from auto_invest.analytics.cost_aware_intraday import (
    load_contract,
    verify_confirmation,
    verify_development,
)
from auto_invest.analytics.intraday_paper_challenger import load_intraday_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("develop", "confirm"))
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--bars-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, default=ROOT /
                        "specs/190-cost-aware-intraday/contracts/preregistration.json")
    parser.add_argument("--development", type=Path)
    parser.add_argument("--development-bars-dir", type=Path)
    parser.add_argument("--development-manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        contract, prior = load_contract(args.preregistration, ROOT /
                                       "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
        if args.stage == "confirm":
            verified, development = verified_development_inputs(
                args, contract, prior, require_selected=True,
            )
            payload, ledger = read_bundle(args.evidence, "confirmation")
            dataset = load_intraday_dataset(args.bars_dir, args.manifest, prior)
            verify_confirmation(payload, ledger, dataset, development, verified, contract, prior)
        else:
            payload, ledger = read_bundle(args.evidence, "development")
            dataset = load_intraday_dataset(args.bars_dir, args.manifest, prior)
            verify_development(payload, ledger, dataset, contract, prior)
        print(json.dumps({"valid": True, "verdict": payload["verdict"],
                          "capital_eligible": False,
                          "ledger_row_count": payload["ledger_row_count"]}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"valid": False, "reasons": [str(exc)], "capital_eligible": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
