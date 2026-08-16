#!/usr/bin/env python3
"""Spec 143: build sticky first-live-profit evidence from performance JSON."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.live_profit_evidence import assess_live_profit


def _read_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _now(raw: str | None) -> str:
    if raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live first-profit evidence probe")
    parser.add_argument("--performance-json", type=Path)
    parser.add_argument("--prior-json", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--now")
    parser.add_argument("--run-id", default="local")
    args = parser.parse_args(argv)

    report = assess_live_profit(
        _read_json(args.performance_json),
        prior=_read_json(args.prior_json),
        observed_at_utc=_now(args.now),
        source_run_id=args.run_id,
    )
    json_text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    markdown = report.as_markdown()
    if args.json_out:
        args.json_out.write_text(json_text + "\n", encoding="utf-8")
    if args.summary_out:
        args.summary_out.write_text(markdown + "\n", encoding="utf-8")
    print(json_text if args.json else markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
