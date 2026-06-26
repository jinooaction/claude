from __future__ import annotations

from auto_invest.analytics.opportunity_monitor import (
    SIGNAL_INTENT_GAIN,
    SIGNAL_INTENT_LOSS,
    VERDICT_EXECUTION_REVIEW,
    VERDICT_INSUFFICIENT_DATA,
    VERDICT_NO_VALUED_REJECTIONS,
    VERDICT_STRATEGY_REVIEW,
    append_opportunity_record,
    render_opportunity_monitor_text,
    summarize_opportunity_history,
)


def _report(total: str, *, valued_count: int = 1, rejected_count: int = 1) -> dict:
    return {
        "schema_version": 1,
        "as_of_utc": "2026-06-26T00:00:00Z",
        "rejected_count": rejected_count,
        "valued_count": valued_count,
        "total_opportunity_pnl_usd": total,
        "buy_opportunity_pnl_usd": total,
        "sell_opportunity_pnl_usd": "+0.00",
        "rows": [],
    }


def _history(*reports: dict) -> dict:
    history: dict = {}
    for idx, report in enumerate(reports, start=1):
        history = append_opportunity_record(
            history,
            report,
            run_id=str(idx),
            timestamp_utc=f"2026-06-26T00:0{idx}:00Z",
            max_entries=60,
        )
    return history


def test_single_negative_signal_is_insufficient_for_auto_review() -> None:
    summary = summarize_opportunity_history(_history(_report("-10.00")))

    assert summary["verdict"] == VERDICT_INSUFFICIENT_DATA
    assert summary["latest_signal"] == SIGNAL_INTENT_LOSS
    assert summary["cumulative"]["total_intended_order_mark_pnl_usd"] == "-10.00"


def test_negative_cumulative_triggers_strategy_review() -> None:
    summary = summarize_opportunity_history(_history(_report("-3.00"), _report("-2.50")))

    assert summary["verdict"] == VERDICT_STRATEGY_REVIEW
    assert summary["streaks"]["intent_loss"] == 2
    assert "전략" in summary["next_action_ko"]


def test_positive_cumulative_triggers_execution_review() -> None:
    summary = summarize_opportunity_history(_history(_report("+2.00"), _report("+3.50")))

    assert summary["verdict"] == VERDICT_EXECUTION_REVIEW
    assert summary["latest_signal"] == SIGNAL_INTENT_GAIN
    assert "KIS" in summary["next_action_ko"]


def test_no_valued_rejections_is_not_strategy_review() -> None:
    summary = summarize_opportunity_history(
        _history(_report("+0.00", valued_count=0, rejected_count=1))
    )

    assert summary["verdict"] == VERDICT_NO_VALUED_REJECTIONS
    assert summary["latest_signal"] == "FLAT_OR_UNVALUED"


def test_history_is_capped() -> None:
    history: dict = {}
    for idx in range(1, 5):
        history = append_opportunity_record(
            history,
            _report("+1.00"),
            run_id=str(idx),
            timestamp_utc=f"2026-06-26T00:0{idx}:00Z",
            max_entries=2,
        )

    assert [record["run_id"] for record in history["records"]] == ["3", "4"]


def test_render_text_explains_verdict_and_safety_note() -> None:
    summary = summarize_opportunity_history(_history(_report("-3.00"), _report("-2.50")))
    text = render_opportunity_monitor_text(summary)

    assert "거부 주문 누적 평가" in text
    assert "STRATEGY_REVIEW" in text
    assert "주문 재시도" in text
