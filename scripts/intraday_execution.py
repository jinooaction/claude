#!/usr/bin/env python3
"""Account-free KIS execution verification. No live option exists."""

import argparse
import asyncio
import json

from auto_invest.execution.intraday_rehearsal import rehearse
from auto_invest.execution.preparation import preflight


def main():
    parser = argparse.ArgumentParser(description="단타 주문 수명 오프라인 검증")
    parser.add_argument("command", choices=["rehearse", "preflight"])
    args = parser.parse_args()
    try:
        result = asyncio.run(preflight() if args.command == "preflight" else rehearse())
    except Exception as exc:
        print(
            json.dumps(
                dict(
                    schema_version=182,
                    mode="confirmed_budget_preflight"
                    if args.command == "preflight"
                    else "offline_rehearsal",
                    status="FAILED",
                    error_type=type(exc).__name__,
                    orders_submitted=0,
                    live_eligible=False,
                )
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
