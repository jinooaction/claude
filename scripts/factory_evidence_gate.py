#!/usr/bin/env python3
"""Validate versioned strategy-factory evidence for workflow consumers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from auto_invest.portfolio.factory_evidence import assess_factory_evidence


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    try:
        evidence = _load_json(args.evidence)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"factory evidence read failed: {exc}", file=sys.stderr)
        return 2

    assessment = assess_factory_evidence(evidence)
    rendered = json.dumps(assessment.as_dict(), ensure_ascii=False, sort_keys=True)
    print(rendered)
    if args.json_out is not None:
        try:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"factory assessment write failed: {exc}", file=sys.stderr)
            return 2
    return 0 if assessment.eligible else 3


if __name__ == "__main__":
    raise SystemExit(main())
