#!/usr/bin/env python3
"""Publish no-order calibration evidence for the paired forward edge gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_invest.analytics.forward_gate_calibration import (
    CALIBRATED,
    run_forward_gate_calibration,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=159_001)
    parser.add_argument("--repetitions", type=int, default=5_000)
    parser.add_argument("--code-commit", default="unknown")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = run_forward_gate_calibration(
            seed=args.seed,
            repetitions=args.repetitions,
            code_commit=args.code_commit,
        )
    except ValueError as exc:
        parser.error(str(exc))

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False) if args.json else rendered)
    return 0 if payload["verdict"] == CALIBRATED else 1


if __name__ == "__main__":
    raise SystemExit(main())
