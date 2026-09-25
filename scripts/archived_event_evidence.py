"""Inspect linked archived event evidence offline without granting trading approval."""

import argparse
import sys
from pathlib import Path

from auto_invest.analytics.archived_event_evidence import write_inspection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--input", type=Path, required=True)
    inspect.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        write_inspection(args.input, args.output)
    except (ValueError, OSError) as exc:
        print(f"Input operation refused: {type(exc).__name__}", file=sys.stderr)
        return 2
    print("Evidence inspected; strategy and live trading eligibility remain false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
