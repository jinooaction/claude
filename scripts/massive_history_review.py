#!/usr/bin/env python3
"""Acquire private historical research data, without brokerage access."""

import argparse
import asyncio
import json
import os

import httpx

from auto_invest.market_data.intraday import DataError
from auto_invest.market_data.massive_history import acquire_and_review


async def run(args):
    async with httpx.AsyncClient(follow_redirects=False) as client:
        return await acquire_and_review(start=args.start, end=args.end, output=args.out,
            api_key=os.environ.get("MASSIVE_API_KEY"), client=client)


def main():
    parser = argparse.ArgumentParser(description="장기 실제 분봉 수집과 독립 전략 재검증")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except Exception as exc:
        print(json.dumps(dict(status="FAILED", reason=str(exc) if isinstance(exc, DataError)
                              else "HISTORY_LOCAL_OR_SCHEMA_ERROR", orders_submitted=0)))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
