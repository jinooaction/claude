#!/usr/bin/env python3
"""Run spec 146 against stored KIS daily bars without any order path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_invest.analytics.daily_cross_asset_ml import (
    UNIVERSE,
    DailyClose,
    render_markdown,
    run_low_turnover_daily_cross_asset_ml,
)
from auto_invest.market_data.store import get_bars
from auto_invest.persistence import db


def _blocked(exc: Exception) -> dict:
    reason = f"{type(exc).__name__}: {exc}"
    return {
        "schema_version": "1.0",
        "experiment_id": "low-turnover-daily-cross-asset-ml-v2",
        "verdict": "BLOCKED",
        "reason": reason,
        "candidate_package": {
            "eligible": False,
            "candidate_id": "candidate-low-turnover-daily-cross-asset-ml-v2",
            "status": "blocked",
            "verdict": "BLOCKED",
            "reason_ko": reason,
            "live_promotion_authorized": False,
        },
        "safety": {
            "orders_submitted": 0,
            "orders_cancelled": 0,
            "live_strategy_changed": False,
            "capital_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/forward_wide.db"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    conn = db.get_connection(args.db)
    try:
        daily = {
            symbol: [
                DailyClose(row.bar_open_utc[:10], float(row.close_usd), row.volume)
                for row in get_bars(conn, symbol=symbol, timeframe="1d")
            ]
            for symbol in UNIVERSE
        }
        report = run_low_turnover_daily_cross_asset_ml(daily)
        payload = report.as_dict()
        markdown = render_markdown(report)
    except Exception as exc:  # A blocked report is evidence, not a silent stale success.
        payload = _blocked(exc)
        markdown = (
            "# 일봉 교차자산 AI 후보\n\n"
            f"- 판정: `BLOCKED`\n- 이유: `{payload['reason']}`\n"
            "- 실주문: 0건\n"
        )
    finally:
        conn.close()

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.json_out:
        args.json_out.write_text(encoded, encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.write_text(markdown, encoding="utf-8")
    print(encoded if args.json else markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
