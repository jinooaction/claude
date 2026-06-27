#!/usr/bin/env python3
"""Evaluate whether rejected-order opportunity evidence blocks live micro GTAA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_invest.analytics.opportunity_monitor import (  # noqa: E402
    assess_opportunity_live_gate,
    render_opportunity_live_gate_text,
)


def _load_json(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return {}
    if not text or text.startswith("("):
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitor-json", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)

    decision = assess_opportunity_live_gate(_load_json(args.monitor_json))
    if args.out is not None:
        args.out.write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.format == "json":
        print(json.dumps(decision, ensure_ascii=False, indent=2))
    else:
        print(render_opportunity_live_gate_text(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
