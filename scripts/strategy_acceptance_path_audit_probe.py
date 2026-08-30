#!/usr/bin/env python3
"""Combine historical and calibration evidence into a no-order acceptance audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_invest.analytics.strategy_acceptance_path_audit import (
    audit_strategy_acceptance_path,
    report_markdown,
)


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regime-result", type=Path, required=True)
    parser.add_argument("--edge-calibration", type=Path, required=True)
    parser.add_argument("--forward-calibration", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        payload = audit_strategy_acceptance_path(
            _read(args.regime_result),
            _read(args.edge_calibration),
            _read(args.forward_calibration),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = report_markdown(payload) + "\n"
    args.markdown_out.write_text(markdown, encoding="utf-8")
    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
