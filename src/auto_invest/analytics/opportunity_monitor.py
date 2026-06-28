"""Rolling rejected-order opportunity monitor.

This module is deliberately side-effect free. It turns per-run rejected-order
opportunity reports into bounded history and cumulative review signals. It does
not submit orders, retry orders, change strategy configs, or contact brokers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA_VERSION = 1

SIGNAL_INTENT_GAIN = "INTENT_GAIN"
SIGNAL_INTENT_LOSS = "INTENT_LOSS"
SIGNAL_FLAT_OR_UNVALUED = "FLAT_OR_UNVALUED"

VERDICT_NO_VALUED_REJECTIONS = "NO_VALUED_REJECTIONS"
VERDICT_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
VERDICT_OBSERVE = "OBSERVE"
VERDICT_STRATEGY_REVIEW = "STRATEGY_REVIEW"
VERDICT_EXECUTION_REVIEW = "EXECUTION_REVIEW"

LIVE_GATE_REASON_ALLOWED = "allowed"
LIVE_GATE_REASON_MONITOR_UNAVAILABLE = "monitor_unavailable"
LIVE_GATE_REASON_INTENT_LOSS = "latest_intent_loss"
LIVE_GATE_REASON_STRATEGY_REVIEW = "strategy_review"

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class OpportunityMonitorThresholds:
    min_valued_reports: int = 2
    strategy_review_loss_usd: Decimal | str = Decimal("-5.00")
    execution_review_gain_usd: Decimal | str = Decimal("5.00")
    streak_threshold: int = 2

    def normalized(self) -> OpportunityMonitorThresholds:
        loss = _decimal(self.strategy_review_loss_usd) or Decimal("-5.00")
        if loss > 0:
            loss = -loss
        gain = _decimal(self.execution_review_gain_usd) or Decimal("5.00")
        if gain < 0:
            gain = -gain
        return OpportunityMonitorThresholds(
            min_valued_reports=max(1, int(self.min_valued_reports)),
            strategy_review_loss_usd=loss,
            execution_review_gain_usd=gain,
            streak_threshold=max(1, int(self.streak_threshold)),
        )


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NONE", "NULL"}:
        return None
    text = text.replace(",", "").replace("USD", "").strip()
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _money(value: Decimal | None, *, signed: bool = True) -> str | None:
    if value is None:
        return None
    sign = "+" if signed else ""
    return f"{value.quantize(_CENT):{sign},.2f}"


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opportunity_total(report: Mapping[str, Any], key: str) -> Decimal:
    return _decimal(report.get(key)) or Decimal("0")


def _signal_for(total: Decimal | None, valued_count: int) -> str:
    if total is None or valued_count <= 0:
        return SIGNAL_FLAT_OR_UNVALUED
    if total > 0:
        return SIGNAL_INTENT_GAIN
    if total < 0:
        return SIGNAL_INTENT_LOSS
    return SIGNAL_FLAT_OR_UNVALUED


def _history_records(history_doc: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(history_doc, Mapping):
        return []
    records = history_doc.get("records")
    if not isinstance(records, list):
        return []
    return [dict(record) for record in records if isinstance(record, Mapping)]


def empty_opportunity_history(
    *,
    generated_at_utc: str | None = None,
    max_entries: int = 60,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_iso(),
        "max_entries": max_entries,
        "definition": (
            "Rolling rejected-order opportunity history. Positive PnL means "
            "the rejected order would have been favorable at the mark; negative "
            "PnL means rejection avoided a worse mark-to-current outcome."
        ),
        "records": [],
    }


def build_opportunity_record(
    opportunity_report: Mapping[str, Any] | None,
    *,
    run_id: str | None = None,
    run_url: str | None = None,
    event: str | None = None,
    live_outcome: str | None = None,
    armed: object = None,
    capital_usd: object = None,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    report = dict(opportunity_report or {})
    recorded_at = timestamp_utc or _now_iso()
    valued_count = _int(report.get("valued_count"))
    rejected_count = _int(report.get("rejected_count"))
    total = _opportunity_total(report, "total_opportunity_pnl_usd")
    buy_total = _opportunity_total(report, "buy_opportunity_pnl_usd")
    sell_total = _opportunity_total(report, "sell_opportunity_pnl_usd")
    return {
        "schema_version": SCHEMA_VERSION,
        "recorded_at_utc": recorded_at,
        "run_id": _string_or_none(run_id),
        "run_url": _string_or_none(run_url),
        "event": _string_or_none(event),
        "live_outcome": _string_or_none(live_outcome),
        "armed": _bool_or_none(armed),
        "capital_usd": _string_or_none(capital_usd),
        "opportunity_as_of_utc": _string_or_none(report.get("as_of_utc")),
        "rejected_count": rejected_count,
        "valued_count": valued_count,
        "total_intended_order_mark_pnl_usd": _money(total),
        "buy_intended_order_mark_pnl_usd": _money(buy_total),
        "sell_intended_order_mark_pnl_usd": _money(sell_total),
        "latest_signal": _signal_for(total, valued_count),
        "opportunity_report": report,
    }


def append_opportunity_record(
    history_doc: Mapping[str, Any] | None,
    opportunity_report: Mapping[str, Any] | None,
    *,
    run_id: str | None = None,
    run_url: str | None = None,
    event: str | None = None,
    live_outcome: str | None = None,
    armed: object = None,
    capital_usd: object = None,
    timestamp_utc: str | None = None,
    max_entries: int = 60,
) -> dict[str, Any]:
    records = _history_records(history_doc)
    records.append(
        build_opportunity_record(
            opportunity_report,
            run_id=run_id,
            run_url=run_url,
            event=event,
            live_outcome=live_outcome,
            armed=armed,
            capital_usd=capital_usd,
            timestamp_utc=timestamp_utc,
        )
    )
    max_entries = max(1, int(max_entries))
    records = records[-max_entries:]
    history = empty_opportunity_history(
        generated_at_utc=timestamp_utc or _now_iso(),
        max_entries=max_entries,
    )
    history["records"] = records
    return history


def _record_total(record: Mapping[str, Any]) -> Decimal | None:
    return _decimal(record.get("total_intended_order_mark_pnl_usd"))


def _record_buy_total(record: Mapping[str, Any]) -> Decimal:
    return _decimal(record.get("buy_intended_order_mark_pnl_usd")) or Decimal("0")


def _record_sell_total(record: Mapping[str, Any]) -> Decimal:
    return _decimal(record.get("sell_intended_order_mark_pnl_usd")) or Decimal("0")


def _signed_streak(records: list[Mapping[str, Any]], *, positive: bool) -> int:
    count = 0
    for record in reversed(records):
        total = _record_total(record)
        if total is None:
            break
        if (positive and total > 0) or (not positive and total < 0):
            count += 1
        else:
            break
    return count


def _verdict_text(verdict: str) -> tuple[str, str]:
    labels = {
        VERDICT_NO_VALUED_REJECTIONS: (
            "평가 가능한 거부 주문 없음",
            "전략 또는 실행 문제를 단정할 현재가 평가 표본이 없습니다.",
        ),
        VERDICT_INSUFFICIENT_DATA: (
            "표본 부족",
            "최신 신호는 보이지만 자동 전략 판단을 내리기에는 표본이 부족합니다.",
        ),
        VERDICT_OBSERVE: (
            "관찰 지속",
            "누적 손익이 검토 임계값 안에 있어 기존 관찰 루프를 유지합니다.",
        ),
        VERDICT_STRATEGY_REVIEW: (
            "전략 검토 필요",
            "거부된 주문들이 정상 체결됐다면 손실이었을 가능성이 누적됐습니다.",
        ),
        VERDICT_EXECUTION_REVIEW: (
            "실행 경로 검토 필요",
            "거부된 주문들이 정상 체결됐다면 이익이었을 가능성이 누적됐습니다.",
        ),
    }
    return labels.get(verdict, ("알 수 없음", "알 수 없는 verdict 입니다."))


def summarize_opportunity_history(
    history_doc: Mapping[str, Any] | None,
    *,
    thresholds: OpportunityMonitorThresholds | None = None,
    as_of_utc: str | None = None,
) -> dict[str, Any]:
    threshold = (thresholds or OpportunityMonitorThresholds()).normalized()
    records = _history_records(history_doc)
    valued_records = [
        record
        for record in records
        if _int(record.get("valued_count")) > 0 and _record_total(record) is not None
    ]
    total = sum(
        (_record_total(record) or Decimal("0") for record in valued_records),
        Decimal("0"),
    )
    buy_total = sum(
        (_record_buy_total(record) for record in valued_records),
        Decimal("0"),
    )
    sell_total = sum(
        (_record_sell_total(record) for record in valued_records),
        Decimal("0"),
    )
    negative_streak = _signed_streak(valued_records, positive=False)
    positive_streak = _signed_streak(valued_records, positive=True)
    latest_record = records[-1] if records else None
    latest_total = _record_total(latest_record) if latest_record else None
    latest_valued = _int(latest_record.get("valued_count")) if latest_record else 0
    latest_signal = _signal_for(latest_total, latest_valued)

    if not valued_records:
        verdict = VERDICT_NO_VALUED_REJECTIONS
    elif len(valued_records) < threshold.min_valued_reports:
        verdict = VERDICT_INSUFFICIENT_DATA
    elif (
        total <= threshold.strategy_review_loss_usd
        or negative_streak >= threshold.streak_threshold
    ):
        verdict = VERDICT_STRATEGY_REVIEW
    elif (
        total >= threshold.execution_review_gain_usd
        or positive_streak >= threshold.streak_threshold
    ):
        verdict = VERDICT_EXECUTION_REVIEW
    else:
        verdict = VERDICT_OBSERVE

    label, interpretation = _verdict_text(verdict)
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of_utc": as_of_utc or _now_iso(),
        "definition": (
            "positive intended_order_mark_pnl_usd means rejected orders would "
            "currently look favorable; negative means rejection avoided a worse "
            "mark-to-current outcome. This is diagnostic, not accounting PnL."
        ),
        "verdict": verdict,
        "verdict_label_ko": label,
        "latest_signal": latest_signal,
        "interpretation_ko": interpretation,
        "next_action_ko": _next_action(verdict, latest_signal),
        "safety_note_ko": (
            "이 신호는 관찰·검토 입력입니다. 주문 재시도, 전략 교체, "
            "자본 변경을 직접 수행하지 않습니다."
        ),
        "thresholds": {
            "min_valued_reports": threshold.min_valued_reports,
            "strategy_review_loss_usd": _money(threshold.strategy_review_loss_usd),
            "execution_review_gain_usd": _money(threshold.execution_review_gain_usd),
            "streak_threshold": threshold.streak_threshold,
        },
        "counts": {
            "records": len(records),
            "valued_records": len(valued_records),
            "rejected_orders": sum(_int(record.get("rejected_count")) for record in records),
            "valued_orders": sum(_int(record.get("valued_count")) for record in records),
        },
        "cumulative": {
            "total_intended_order_mark_pnl_usd": _money(total),
            "buy_intended_order_mark_pnl_usd": _money(buy_total),
            "sell_intended_order_mark_pnl_usd": _money(sell_total),
        },
        "streaks": {
            "intent_loss": negative_streak,
            "intent_gain": positive_streak,
        },
        "latest": _latest_summary(latest_record),
        "strategy_loop_input": {
            "target": "specs/055-autonomous-reassignment",
            "effect": "evidence_only_no_gate_override",
        },
    }


def _latest_summary(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "run_id": record.get("run_id"),
        "run_url": record.get("run_url"),
        "recorded_at_utc": record.get("recorded_at_utc"),
        "opportunity_as_of_utc": record.get("opportunity_as_of_utc"),
        "rejected_count": _int(record.get("rejected_count")),
        "valued_count": _int(record.get("valued_count")),
        "total_intended_order_mark_pnl_usd": record.get(
            "total_intended_order_mark_pnl_usd"
        ),
        "latest_signal": record.get("latest_signal") or SIGNAL_FLAT_OR_UNVALUED,
    }


def _next_action(verdict: str, latest_signal: str | None = None) -> str:
    if verdict == VERDICT_STRATEGY_REVIEW:
        return (
            "전략 의도 손실 신호입니다. forward 토너먼트·캐너리 증거와 함께 "
            "전략 교체 후보를 검토합니다."
        )
    if verdict == VERDICT_EXECUTION_REVIEW:
        return (
            "거부 때문에 이익을 놓친 신호입니다. KIS 주문 접수·현금·세션·"
            "게이트 문제를 우선 검토합니다."
        )
    if verdict == VERDICT_INSUFFICIENT_DATA:
        if latest_signal == SIGNAL_INTENT_LOSS:
            return (
                "최신 손실 의도 신호가 실주문을 막고 있어 새 live 표본은 자동으로 "
                "쌓이지 않습니다. forward 토너먼트·재지정 증거를 기다리거나 별도 "
                "전략 검토 후 재무장 여부를 판단합니다."
            )
        return "다음 micro GTAA 실행에서 표본을 더 쌓습니다."
    if verdict == VERDICT_NO_VALUED_REJECTIONS:
        return "현재가로 평가 가능한 거부 주문이 생길 때까지 관찰합니다."
    return "관찰을 지속하고 기존 자율 재지정 5중 게이트를 유지합니다."


def assess_opportunity_live_gate(
    monitor_doc: Mapping[str, Any] | None,
    *,
    as_of_utc: str | None = None,
) -> dict[str, Any]:
    """Return whether opportunity evidence allows another live micro GTAA attempt.

    The gate is intentionally one-way: it may block a live order attempt, but it
    never approves one by itself. Existing arming, session, cash, caps, whitelist,
    and circuit-breaker gates still have to pass.
    """

    if not isinstance(monitor_doc, Mapping) or not monitor_doc:
        return {
            "schema_version": SCHEMA_VERSION,
            "as_of_utc": as_of_utc or _now_iso(),
            "ok": True,
            "reason": LIVE_GATE_REASON_MONITOR_UNAVAILABLE,
            "blocking_reasons": [],
            "verdict": None,
            "latest_signal": None,
            "cumulative_pnl_usd": None,
            "latest_run_id": None,
            "policy_ko": (
                "기회손익 monitor를 읽지 못했습니다. 이 게이트만으로는 추가 차단하지 "
                "않지만, 기존 무장·정규장·현금·손실 브레이커 게이트는 그대로 적용됩니다."
            ),
            "next_action_ko": "opportunity_monitor.json 발행 상태를 확인합니다.",
            "safety_note_ko": (
                "이 게이트는 주문을 허용하지 않고, 손실 의도 신호가 있을 때만 "
                "차단합니다."
            ),
        }

    verdict = _string_or_none(monitor_doc.get("verdict"))
    latest_signal = _string_or_none(monitor_doc.get("latest_signal"))
    cumulative = (
        monitor_doc.get("cumulative")
        if isinstance(monitor_doc.get("cumulative"), Mapping)
        else {}
    )
    latest = monitor_doc.get("latest") if isinstance(monitor_doc.get("latest"), Mapping) else {}
    blocking_reasons: list[str] = []

    if latest_signal == SIGNAL_INTENT_LOSS:
        blocking_reasons.append(LIVE_GATE_REASON_INTENT_LOSS)
    if verdict == VERDICT_STRATEGY_REVIEW:
        blocking_reasons.append(LIVE_GATE_REASON_STRATEGY_REVIEW)

    ok = not blocking_reasons
    reason = LIVE_GATE_REASON_ALLOWED if ok else ",".join(blocking_reasons)
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of_utc": as_of_utc or _now_iso(),
        "ok": ok,
        "reason": reason,
        "blocking_reasons": blocking_reasons,
        "verdict": verdict,
        "latest_signal": latest_signal,
        "cumulative_pnl_usd": cumulative.get("total_intended_order_mark_pnl_usd"),
        "latest_run_id": latest.get("run_id"),
        "policy_ko": (
            "최신 거부 주문 기회손익이 손실 방향(INTENT_LOSS)이거나 누적 판정이 "
            "STRATEGY_REVIEW이면 micro GTAA 실주문을 차단합니다."
        ),
        "next_action_ko": (
            "실주문을 멈추고 forward 토너먼트·전략 검토 증거를 확인합니다."
            if not ok
            else "이 게이트는 추가 차단하지 않습니다. 기존 live 안전 게이트를 계속 확인합니다."
        ),
        "safety_note_ko": (
            "이 게이트는 실주문을 차단만 합니다. 주문 재시도, 전략 교체, 자본 변경을 "
            "직접 수행하지 않습니다."
        ),
    }


def render_opportunity_live_gate_text(decision: Mapping[str, Any]) -> str:
    lines = [
        "micro GTAA 전략 의도 게이트",
        f"ok={decision.get('ok')}",
        f"reason={decision.get('reason')}",
        (
            "evidence: verdict={verdict}, latest_signal={signal}, "
            "cumulative_pnl_usd={pnl}, latest_run_id={run_id}"
        ).format(
            verdict=decision.get("verdict"),
            signal=decision.get("latest_signal"),
            pnl=decision.get("cumulative_pnl_usd"),
            run_id=decision.get("latest_run_id"),
        ),
        f"정책: {decision.get('policy_ko')}",
        f"다음 조치: {decision.get('next_action_ko')}",
        str(decision.get("safety_note_ko")),
    ]
    return "\n".join(lines)


def render_opportunity_monitor_text(summary: Mapping[str, Any]) -> str:
    counts = summary.get("counts") if isinstance(summary.get("counts"), Mapping) else {}
    cumulative = (
        summary.get("cumulative")
        if isinstance(summary.get("cumulative"), Mapping)
        else {}
    )
    streaks = summary.get("streaks") if isinstance(summary.get("streaks"), Mapping) else {}
    latest = summary.get("latest") if isinstance(summary.get("latest"), Mapping) else None
    lines = [
        "거부 주문 누적 평가",
        f"verdict={summary.get('verdict')} ({summary.get('verdict_label_ko')})",
        f"해석: {summary.get('interpretation_ko')}",
        (
            "누적 전략 의도 손익: "
            f"{cumulative.get('total_intended_order_mark_pnl_usd', '+0.00')} USD "
            f"(매수 {cumulative.get('buy_intended_order_mark_pnl_usd', '+0.00')}, "
            f"매도 {cumulative.get('sell_intended_order_mark_pnl_usd', '+0.00')})"
        ),
        (
            f"표본: 평가 실행 {counts.get('valued_records', 0)}/"
            f"{counts.get('records', 0)}회, 평가 주문 "
            f"{counts.get('valued_orders', 0)}/{counts.get('rejected_orders', 0)}건"
        ),
        (
            f"연속 신호: 손실 {streaks.get('intent_loss', 0)}회, "
            f"이익 {streaks.get('intent_gain', 0)}회"
        ),
    ]
    if latest:
        lines.append(
            "최신: run_id={run_id}, signal={signal}, pnl={pnl} USD, "
            "평가 {valued}/{rejected}건".format(
                run_id=latest.get("run_id") or "?",
                signal=latest.get("latest_signal") or SIGNAL_FLAT_OR_UNVALUED,
                pnl=latest.get("total_intended_order_mark_pnl_usd") or "N/A",
                valued=latest.get("valued_count", 0),
                rejected=latest.get("rejected_count", 0),
            )
        )
    lines.append(f"다음 조치: {summary.get('next_action_ko')}")
    lines.append(str(summary.get("safety_note_ko")))
    return "\n".join(lines)


__all__ = [
    "OpportunityMonitorThresholds",
    "SIGNAL_FLAT_OR_UNVALUED",
    "SIGNAL_INTENT_GAIN",
    "SIGNAL_INTENT_LOSS",
    "LIVE_GATE_REASON_ALLOWED",
    "LIVE_GATE_REASON_INTENT_LOSS",
    "LIVE_GATE_REASON_MONITOR_UNAVAILABLE",
    "LIVE_GATE_REASON_STRATEGY_REVIEW",
    "VERDICT_EXECUTION_REVIEW",
    "VERDICT_INSUFFICIENT_DATA",
    "VERDICT_NO_VALUED_REJECTIONS",
    "VERDICT_OBSERVE",
    "VERDICT_STRATEGY_REVIEW",
    "assess_opportunity_live_gate",
    "append_opportunity_record",
    "build_opportunity_record",
    "empty_opportunity_history",
    "render_opportunity_live_gate_text",
    "render_opportunity_monitor_text",
    "summarize_opportunity_history",
]
