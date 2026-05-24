"""daily_summary 판단 지점 (US2).

장 마감 후 그날 audit 집계 카운터를 Claude 에게 넘겨 사람이 읽는 서술 요약과
경보 목록을 받는다. 순수 자문 — 주문 경로에 전혀 닿지 않는다. LLM 이 없거나
실패하면 결정론적 폴백 문장(카운터만)을 돌려준다(거래/리포트 막지 않음).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from auto_invest.judgment import registry
from auto_invest.judgment.client import JudgmentClient
from auto_invest.judgment.schemas import (
    DailySummaryAdvisory,
    JudgmentSchemaError,
    parse_and_validate,
)
from auto_invest.persistence import audit
from auto_invest.persistence.audit import JudgmentFallbackPayload

_DECISION_CLASS = "daily_summary"

_SYSTEM_PROMPT = (
    "You are the operations analyst for an automated US-equity trading system. "
    "You are given AGGREGATE COUNTERS for one trading day (order/fill/rejection/"
    "error/judgment counts). Write a concise operator-facing summary. Respond "
    "with ONLY a single JSON object: "
    '{"narrative": "<=500 chars plain text", "alerts": ["<short>", ...]}. '
    "Put genuinely notable conditions (spikes in rejections, errors, halts) in "
    '"alerts"; keep "narrative" factual and under 500 characters.'
)


def build_daily_summary_prompt(counters: dict[str, int]) -> tuple[str, str]:
    """(system, user) 반환. 입력은 집계 카운터만(원시 행 아님)."""
    user = "Summarize this trading day from these aggregate counters:\n" + json.dumps(
        counters, default=str, sort_keys=True
    )
    return _SYSTEM_PROMPT, user


def fallback_narrative(counters: dict[str, int]) -> str:
    """LLM 비활성/실패 시 결정론적 요약 — 카운터만."""
    return (
        "자동 요약 생성 불가(LLM 비활성/실패) — 결정론적 카운터만: "
        f"주문 시도 {counters.get('orders_attempted', 0)}, "
        f"체결 {counters.get('fills', 0)}, "
        f"게이트 거부 {counters.get('orders_rejected_by_gate', 0)}, "
        f"오류 {counters.get('errors', 0)}."
    )


async def summarize_day(
    client: JudgmentClient,
    *,
    conn: sqlite3.Connection,
    counters: dict[str, int],
) -> str:
    """그날 카운터로 서술 요약을 생성. 실패 시 결정론적 폴백 문장 반환."""
    jp = registry.get(_DECISION_CLASS)
    system_prompt, user_prompt = build_daily_summary_prompt(counters)
    result = await client.call(
        decision_class=_DECISION_CLASS,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=jp.model,
        max_tokens=jp.max_tokens,
        latency_budget_ms=jp.latency_budget_ms,
    )
    if not result.ok:
        audit.append(
            conn,
            JudgmentFallbackPayload(
                decision_class=_DECISION_CLASS, reason=result.fallback_reason or "failure"
            ),
            correlation_id=result.correlation_id,
        )
        return fallback_narrative(counters)
    try:
        advisory = parse_and_validate(_DECISION_CLASS, result.text or "")
    except JudgmentSchemaError:
        audit.append(
            conn,
            JudgmentFallbackPayload(
                decision_class=_DECISION_CLASS, reason="schema_invalid"
            ),
            correlation_id=result.correlation_id,
        )
        return fallback_narrative(counters)

    assert isinstance(advisory, DailySummaryAdvisory)
    parts: list[str] = [advisory.narrative]
    if advisory.alerts:
        parts.append("경보: " + "; ".join(advisory.alerts))
    return "\n".join(parts)


def attach_summary_to_report(report: Any, summary: str) -> Any:
    """DailyReport 에 judgment_summary 를 채운 복제본을 만든다(frozen dataclass)."""
    from dataclasses import replace

    return replace(report, judgment_summary=summary)
