"""Spec 143 live first-profit state machine."""

from __future__ import annotations

from auto_invest.analytics.live_profit_evidence import (
    STATUS_FIRST_PROFIT,
    STATUS_INCOMPLETE,
    STATUS_NO_FILLS,
    STATUS_NOT_PROFITABLE,
    STATUS_UNKNOWN,
    assess_live_profit,
)

NOW = "2026-08-18T00:01:00Z"


def _performance(
    *,
    fills: int = 1,
    realized: str = "0",
    unrealized: str = "1.25",
    total: str = "1.25",
    unmarked: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "mode": "live",
        "fills_count": fills,
        "gross_invested_usd": "178.32" if fills else "0",
        "realized_pnl_usd": realized,
        "unrealized_pnl_usd": unrealized,
        "total_pnl_usd": total,
        "return_pct": "0.700" if fills else None,
        "unmarked_symbols": unmarked or [],
        "data_quality_warnings": warnings or [],
    }


def _assess(performance: dict | None, prior: dict | None = None):
    return assess_live_profit(
        performance,
        prior=prior,
        observed_at_utc=NOW,
        source_run_id="31900000000",
    )


def test_no_fills_is_not_profit() -> None:
    report = _assess(_performance(fills=0, unrealized="0", total="0"))

    assert report.status == STATUS_NO_FILLS
    assert report.first_profit_observed is False


def test_missing_marks_fail_closed() -> None:
    report = _assess(_performance(unmarked=["SPYM"]))

    assert report.status == STATUS_INCOMPLETE
    assert report.first_profit_observed is False


def test_data_quality_warning_fails_closed() -> None:
    report = _assess(_performance(warnings=["unknown live fill side"]))

    assert report.status == STATUS_INCOMPLETE


def test_filled_non_positive_pnl_is_not_profitable() -> None:
    report = _assess(_performance(unrealized="-0.10", total="-0.10"))

    assert report.status == STATUS_NOT_PROFITABLE
    assert report.total_pnl_usd == "-0.10"


def test_complete_positive_live_pnl_records_first_profit() -> None:
    report = _assess(_performance())

    assert report.status == STATUS_FIRST_PROFIT
    assert report.current_status == STATUS_FIRST_PROFIT
    assert report.first_profit_observed is True
    assert report.first_profit_observed_at_utc == NOW
    assert report.first_profit_fills_count == 1
    assert report.first_profit_total_pnl_usd == "1.25"


def test_first_profit_is_sticky_when_current_pnl_turns_negative() -> None:
    first = _assess(_performance()).to_dict()
    later = assess_live_profit(
        _performance(unrealized="-2.00", total="-2.00"),
        prior=first,
        observed_at_utc="2026-08-18T01:00:00Z",
        source_run_id="31900000001",
    )

    assert later.status == STATUS_FIRST_PROFIT
    assert later.current_status == STATUS_NOT_PROFITABLE
    assert later.first_profit_observed_at_utc == NOW
    assert later.first_profit_total_pnl_usd == "1.25"
    assert later.total_pnl_usd == "-2.00"


def test_malformed_prior_cannot_forge_first_profit() -> None:
    prior = {
        "status": STATUS_FIRST_PROFIT,
        "first_profit_observed": True,
        "first_profit_total_pnl_usd": "1.00",
    }
    report = _assess(_performance(fills=0, unrealized="0", total="0"), prior)

    assert report.status == STATUS_NO_FILLS
    assert report.first_profit_observed is False


def test_missing_or_non_live_performance_is_unknown() -> None:
    assert _assess(None).status == STATUS_UNKNOWN
    assert _assess({"mode": "paper"}).status == STATUS_UNKNOWN
