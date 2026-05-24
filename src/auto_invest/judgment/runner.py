"""Volatility judgment runner — 거래 루프와 판단 클라이언트의 접착층 (US1/US4).

트리거 발화 후 주문 라우팅 직전에 호출된다. 변동성 요약 통계를 계산하고,
판단 지점이 활성(룰 enabled + 캐너리 단계)이며 변동성이 임계값을 넘고 비용
예산이 남아 있을 때만 Claude 자문을 받는다. 어떤 이유로든 자문을 못 받으면
`(None, None)` 을 반환해 거래 루프가 v1 동작(폴백)으로 진행하게 한다 — 거래는
절대 막히지 않는다(SC-001). 폴백 사유는 `JUDGMENT_FALLBACK` 로 감사된다.
"""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from auto_invest.config.enums import StrategyStage
from auto_invest.config.rules import TradingRule
from auto_invest.judgment import registry
from auto_invest.judgment.budget import BudgetTracker
from auto_invest.judgment.client import JudgmentClient
from auto_invest.judgment.points.volatility import build_volatility_prompt
from auto_invest.judgment.schemas import (
    JudgmentSchemaError,
    VolatilityAdvisory,
    parse_and_validate,
)
from auto_invest.persistence import audit
from auto_invest.persistence.audit import JudgmentFallbackPayload

_DECISION_CLASS = "volatility_assessment"


def realized_vol_summary(bars: Any) -> dict[str, float]:
    """최근 바 종가들로 단기 실현 변동성(수익률 표준편차) 요약을 계산.

    원시 바를 그대로 넘기지 않고 요약 통계만 만든다(헌법 III 입력 계약).
    바가 2개 미만이면 변동성 0(트리거 미발화).
    """
    closes: list[float] = []
    for bar in bars:
        close = getattr(bar, "close_usd", None)
        if close is None:
            continue
        closes.append(float(close))
    if len(closes) < 2:
        return {"realized_vol_5m": 0.0, "sample_size": len(closes)}
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1] != 0
    ]
    if not returns:
        return {"realized_vol_5m": 0.0, "sample_size": len(closes)}
    vol = statistics.pstdev(returns) if len(returns) > 1 else abs(returns[0])
    return {
        "realized_vol_5m": round(vol, 6),
        "recent_return_pct": round(returns[-1] * 100.0, 4),
        "sample_size": len(closes),
    }


@dataclass
class VolatilityJudgmentRunner:
    """판단 클라이언트를 거래 루프에 연결. 워커가 선택적으로 보유한다."""

    client: JudgmentClient
    conn: sqlite3.Connection
    budget: BudgetTracker | None = None

    async def assess(
        self, rule: TradingRule, bars: Any, *, current_price: Decimal | None = None
    ) -> tuple[VolatilityAdvisory | None, str | None]:
        """(advisory, judgment_correlation_id) 또는 폴백 시 (None, None)."""
        cfg = rule.judgment
        if cfg is None or not cfg.enabled:
            return None, None
        if rule.stage is not StrategyStage.CANARY:
            return None, None  # 헌법 VI — 캐너리에서만 자문 반영.

        if self.budget is not None and self.budget.is_disabled(_DECISION_CLASS):
            audit.append(
                self.conn,
                JudgmentFallbackPayload(
                    decision_class=_DECISION_CLASS, reason="budget_exceeded"
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
            )
            return None, None

        summary = realized_vol_summary(bars)
        if summary.get("realized_vol_5m", 0.0) < cfg.volatility_threshold:
            return None, None  # 변동성 트리거 미발화 — 판단 호출 안 함.

        jp = registry.get(_DECISION_CLASS)
        system_prompt, user_prompt = build_volatility_prompt(
            symbol=rule.symbol, summary_stats=summary
        )
        result = await self.client.call(
            decision_class=_DECISION_CLASS,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=jp.model,
            max_tokens=jp.max_tokens,
            latency_budget_ms=jp.latency_budget_ms,
        )
        if self.budget is not None and result.ok:
            self.budget.record(_DECISION_CLASS, result.cost_usd)

        if not result.ok:
            audit.append(
                self.conn,
                JudgmentFallbackPayload(
                    decision_class=_DECISION_CLASS,
                    reason=result.fallback_reason or "failure",
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=result.correlation_id,
            )
            return None, None

        try:
            advisory = parse_and_validate(_DECISION_CLASS, result.text or "")
        except JudgmentSchemaError:
            audit.append(
                self.conn,
                JudgmentFallbackPayload(
                    decision_class=_DECISION_CLASS, reason="schema_invalid"
                ),
                rule_id=rule.id,
                symbol=rule.symbol,
                correlation_id=result.correlation_id,
            )
            return None, None

        assert isinstance(advisory, VolatilityAdvisory)
        return advisory, result.correlation_id
