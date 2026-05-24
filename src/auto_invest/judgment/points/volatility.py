"""volatility_assessment 판단 지점 (US1).

변동성 급등 시 Claude 에게 요약 통계만 넘겨 hold/size_down/halt 자문을 받고
(`build_volatility_prompt`), 그 자문을 **결정론적으로** 소비한다
(`apply_volatility_advisory`). 소비는 노출을 줄이거나 건너뛰기만 하며, 같은
자문 + 같은 노브 → 항상 같은 결정이다(SC-002).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from auto_invest.judgment.schemas import VolatilityAdvisory

_SYSTEM_PROMPT = (
    "You are a conservative risk assessor for an automated US-equity trading "
    "system. You are given SUMMARY STATISTICS for a whitelisted symbol whose "
    "short-term realized volatility has exceeded a configured threshold. You do "
    "NOT place orders; your output is advisory and is consumed by deterministic "
    "gate logic that can only REDUCE or SKIP an order, never enlarge it. "
    "Respond with ONLY a single JSON object and nothing else, of the form: "
    '{"action": "hold"|"size_down"|"halt", "confidence": <0..1>, '
    '"reason": "<short>"}. Use "halt" only when the statistics indicate '
    "abnormal danger; prefer \"size_down\" for elevated-but-orderly volatility; "
    'use "hold" when the move looks benign.'
)


def build_volatility_prompt(*, symbol: str, summary_stats: dict[str, Any]) -> tuple[str, str]:
    """(system_prompt, user_prompt) 반환. 입력은 요약 통계만 — 원시 바 금지(헌법 III)."""
    payload = {"symbol": symbol, **summary_stats}
    user_prompt = (
        "Assess the order risk given these summary statistics:\n"
        + json.dumps(payload, default=str)
    )
    return _SYSTEM_PROMPT, user_prompt


@dataclass(frozen=True)
class VolatilityDecision:
    """자문을 결정론적으로 소비한 결과."""

    skip: bool
    effective_qty: int
    applied_decision: str  # "skip" | "size_down:<f>" | "no_effect"
    advisory_summary: str  # "halt@0.95"


def apply_volatility_advisory(
    advisory: VolatilityAdvisory,
    *,
    qty: int,
    halt_min_confidence: float,
    size_down_factor: float,
) -> VolatilityDecision:
    """자문 → 주문 결정(결정론적). 노출은 줄어들거나 0(건너뛰기)만 된다.

    - `halt` & confidence ≥ halt_min_confidence → 주문 건너뜀.
    - `size_down` → qty *= size_down_factor (0..1 로 클램프; 0 이면 건너뜀).
    - 그 외(hold, 또는 임계 미달 halt) → 무효과.
    """
    summary = f"{advisory.action}@{advisory.confidence:.2f}"

    if advisory.action == "halt" and advisory.confidence >= halt_min_confidence:
        return VolatilityDecision(
            skip=True, effective_qty=0, applied_decision="skip", advisory_summary=summary
        )

    if advisory.action == "size_down":
        factor = min(1.0, max(0.0, size_down_factor))
        new_qty = int(qty * factor)
        if new_qty <= 0:
            return VolatilityDecision(
                skip=True,
                effective_qty=0,
                applied_decision=f"size_down:{factor}->skip",
                advisory_summary=summary,
            )
        return VolatilityDecision(
            skip=False,
            effective_qty=new_qty,
            applied_decision=f"size_down:{factor}",
            advisory_summary=summary,
        )

    return VolatilityDecision(
        skip=False,
        effective_qty=qty,
        applied_decision="no_effect",
        advisory_summary=summary,
    )
