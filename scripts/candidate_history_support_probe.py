#!/usr/bin/env python3
"""Emit the candidate history support manifest."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from auto_invest.analytics.candidate_history_support import (
    manifest_document,
    manifest_lines,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--manifest",
        action="store_true",
        help="Emit TSV rows: key, portfolio_path, db_path, history_root.",
    )
    group.add_argument("--json", action="store_true", help="Emit JSON document.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.json:
        print(json.dumps(manifest_document(), ensure_ascii=False, indent=2))
        return 0
    print("\n".join(manifest_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
