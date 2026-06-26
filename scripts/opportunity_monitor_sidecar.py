#!/usr/bin/env python3
"""Update rejected-order opportunity history and emit a monitor summary.

This helper intentionally uses only the standard library plus the local source
tree, so GitHub Actions can run it from checkout without installing the package.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_invest.analytics.opportunity_monitor import (  # noqa: E402
    OpportunityMonitorThresholds,
    append_opportunity_record,
    empty_opportunity_history,
    render_opportunity_monitor_text,
    summarize_opportunity_history,
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
    parser.add_argument("--history-json", type=Path)
    parser.add_argument("--opportunity-json", type=Path)
    parser.add_argument("--history-out", type=Path)
    parser.add_argument("--monitor-out", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--run-url")
    parser.add_argument("--event")
    parser.add_argument("--live-outcome")
    parser.add_argument("--armed")
    parser.add_argument("--capital-usd")
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--max-entries", type=int, default=60)
    parser.add_argument("--min-valued-reports", type=int, default=2)
    parser.add_argument("--strategy-review-loss-usd", default="-5.00")
    parser.add_argument("--execution-review-gain-usd", default="5.00")
    parser.add_argument("--streak-threshold", type=int, default=2)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)

    history = _load_json(args.history_json)
    if args.opportunity_json is not None:
        history = append_opportunity_record(
            history,
            _load_json(args.opportunity_json),
            run_id=args.run_id,
            run_url=args.run_url,
            event=args.event,
            live_outcome=args.live_outcome,
            armed=args.armed,
            capital_usd=args.capital_usd,
            timestamp_utc=args.timestamp_utc,
            max_entries=args.max_entries,
        )
    elif not history:
        history = empty_opportunity_history(max_entries=args.max_entries)

    thresholds = OpportunityMonitorThresholds(
        min_valued_reports=args.min_valued_reports,
        strategy_review_loss_usd=args.strategy_review_loss_usd,
        execution_review_gain_usd=args.execution_review_gain_usd,
        streak_threshold=args.streak_threshold,
    )
    summary = summarize_opportunity_history(history, thresholds=thresholds)

    if args.history_out is not None:
        args.history_out.write_text(
            json.dumps(history, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.monitor_out is not None:
        args.monitor_out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_opportunity_monitor_text(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
