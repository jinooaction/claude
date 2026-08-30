#!/usr/bin/env python3
"""Independently validate diagnostic PEAD evidence without opening capital."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from auto_invest.analytics.pead_factory_evidence import assess_pead_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PEAD evidence read failed: {exc}", file=sys.stderr)
        return 2
    assessment = assess_pead_evidence(payload)
    rendered = json.dumps(assessment.as_dict(), ensure_ascii=False, sort_keys=True)
    print(rendered)
    if args.json_out is not None:
        try:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"PEAD assessment write failed: {exc}", file=sys.stderr)
            return 2
    return 0 if assessment.valid else 3


if __name__ == "__main__":
    raise SystemExit(main())

