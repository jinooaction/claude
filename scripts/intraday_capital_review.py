#!/usr/bin/env python3
"""검토용 예산 계산. 계좌 설정·승인·주문 기능은 없다."""

import argparse
import json
from pathlib import Path

from auto_invest.analytics.intraday_capital_review import load_prices, review


def main():
    parser = argparse.ArgumentParser(description="단타 자금 한도와 정수주 수량 검토")
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--capital-usd", required=True)
    args = parser.parse_args()
    try:
        result = review(load_prices(args.prices), args.capital_usd)
    except (ValueError, OSError) as exc:
        print(
            json.dumps(
                dict(
                    mode="capital_review_only",
                    status="INVALID_INPUT",
                    error_type=type(exc).__name__,
                    live_eligible=False,
                    capital_change_usd="0.00",
                    orders_submitted=0,
                )
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
