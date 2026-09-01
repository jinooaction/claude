#!/usr/bin/env python3
"""Independently verify spec 177 evidence and its immutable simulation ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from auto_invest.analytics.intraday_paper_challenger import (
    PreregistrationContractError,
    load_preregistration,
)
from auto_invest.analytics.intraday_paper_challenger_evidence import (
    assess_intraday_evidence,
)

DEFAULT_PREREGISTRATION = Path(
    "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    try:
        preregistration_bytes = args.preregistration.read_bytes()
        preregistration = load_preregistration(args.preregistration)
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
        ledger = args.ledger.read_bytes()
    except (OSError, json.JSONDecodeError, PreregistrationContractError) as exc:
        print(f"intraday evidence read failed: {exc}", file=sys.stderr)
        return 2
    assessment = assess_intraday_evidence(
        payload,
        preregistration,
        preregistration_bytes=preregistration_bytes,
        ledger_bytes=ledger,
    )
    rendered = json.dumps(assessment.as_dict(), ensure_ascii=False, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.json_out is not None:
        try:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"intraday assessment write failed: {exc}", file=sys.stderr)
            return 2
    return 0 if assessment.valid else 3


if __name__ == "__main__":
    raise SystemExit(main())
