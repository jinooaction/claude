from __future__ import annotations

from decimal import Decimal

from auto_invest.analytics.order_opportunity import (
    build_rejected_order_opportunity_report,
    rejected_order_symbols,
    render_rejected_order_opportunity_text,
)


def test_rejected_buy_and_sell_opportunity_pnl() -> None:
    result = {
        "results": [
            {
                "symbol": "SPYM",
                "side": "BUY",
                "requested_qty": 3,
                "routed_qty": 3,
                "limit_price_usd": "86.94",
                "state": "REJECTED_BY_BROKER",
                "reason": "'output'",
            },
            {
                "symbol": "MRK",
                "side": "SELL",
                "requested_qty": 3,
                "routed_qty": 3,
                "limit_price_usd": "118.71",
                "state": "REJECTED_BY_BROKER",
            },
            {
                "symbol": "BHP",
                "side": "SELL",
                "requested_qty": 1,
                "routed_qty": 1,
                "limit_price_usd": "82.52",
                "state": "SUBMITTED",
            },
        ]
    }

    report = build_rejected_order_opportunity_report(
        result,
        {"SPYM": Decimal("86.31"), "MRK": Decimal("125.45")},
        as_of_utc="2026-06-26T00:00:00Z",
    )

    assert rejected_order_symbols(result) == ("MRK", "SPYM")
    assert report.rejected_count == 2
    assert report.valued_count == 2
    assert report.buy_opportunity_pnl_usd == Decimal("-1.89")
    assert report.sell_opportunity_pnl_usd == Decimal("-20.22")
    assert report.total_opportunity_pnl_usd == Decimal("-22.11")
    payload = report.to_json_dict()
    assert payload["total_opportunity_pnl_usd"] == "-22.11"
    assert payload["rows"][0]["opportunity_pnl_usd"] == "-1.89"
    assert payload["rows"][1]["opportunity_pnl_usd"] == "-20.22"


def test_missing_marks_are_reported_without_failing() -> None:
    report = build_rejected_order_opportunity_report(
        {
            "results": [
                {
                    "symbol": "IEF",
                    "side": "BUY",
                    "requested_qty": 3,
                    "routed_qty": 3,
                    "limit_price_usd": "95.08",
                    "state": "REJECTED_BY_BROKER",
                }
            ]
        },
        {},
        as_of_utc="2026-06-26T00:00:00Z",
        mark_fetch_error="network down",
    )

    assert report.rejected_count == 1
    assert report.valued_count == 0
    assert report.missing_mark_symbols == ("IEF",)
    text = render_rejected_order_opportunity_text(report)
    assert "현재가 조회 오류: network down" in text
    assert "현재가 없음: IEF" in text
    assert "N/A USD" in text
