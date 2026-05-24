"""news_screen 판단 지점 (US3).

장 시작 전, 화이트리스트 종목에 매칭된 헤드라인이 **주입되면** Claude 에게
헤드라인+종목을 넘겨 bull/bear/neutral 스탠스를 받는다. 결정론적 게이트는
bear+고신뢰일 때만 그 종목 당일 신규 매수를 보류한다(노출 증가 불가). 새 뉴스
피드는 구축하지 않는다 — 헤드라인 공급원이 없으면 판단 지점은 비활성(neutral).
"""

from __future__ import annotations

import json
import sqlite3

from auto_invest.config.enums import Side
from auto_invest.judgment import registry
from auto_invest.judgment.client import JudgmentClient
from auto_invest.judgment.schemas import (
    JudgmentSchemaError,
    NewsAdvisory,
    parse_and_validate,
)
from auto_invest.persistence import audit
from auto_invest.persistence.audit import JudgmentFallbackPayload

_DECISION_CLASS = "news_screen"

_SYSTEM_PROMPT = (
    "You are a pre-market news screener for an automated US-equity trading "
    "system. Given a HEADLINE for a whitelisted symbol, classify the near-term "
    "stance. You do NOT place orders; your output is advisory and can only cause "
    "the deterministic gate to SKIP a new buy, never to enlarge a position. "
    "Respond with ONLY a single JSON object: "
    '{"stance": "bull"|"bear"|"neutral", "confidence": <0..1>}.'
)


def build_news_prompt(*, symbol: str, headline: str) -> tuple[str, str]:
    """(system, user) 반환."""
    user = "Classify the stance for this pre-market headline:\n" + json.dumps(
        {"symbol": symbol, "headline": headline}, default=str
    )
    return _SYSTEM_PROMPT, user


def should_block_buy(
    advisory: NewsAdvisory,
    *,
    side: Side,
    block_min_confidence: float,
    block_buy_stance: str | None = "bear",
) -> bool:
    """결정론적: BUY 이고 스탠스가 차단 대상(기본 bear)이며 신뢰도가 임계 이상이면 보류."""
    if side is not Side.BUY:
        return False
    if block_buy_stance is None:
        return False
    return advisory.stance == block_buy_stance and advisory.confidence >= block_min_confidence


async def screen_headline(
    client: JudgmentClient,
    *,
    conn: sqlite3.Connection,
    symbol: str,
    headline: str | None,
) -> tuple[NewsAdvisory | None, str | None]:
    """헤드라인을 스크리닝. headline 이 없으면(공급원 부재) 호출 없이 (None, None).

    LLM 실패/스키마위반 시 neutral 폴백((None, None)) + JUDGMENT_FALLBACK 기록.
    """
    if not headline:
        return None, None  # 공급원 부재 → 비활성(neutral).

    jp = registry.get(_DECISION_CLASS)
    system_prompt, user_prompt = build_news_prompt(symbol=symbol, headline=headline)
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
            symbol=symbol,
            correlation_id=result.correlation_id,
        )
        return None, None
    try:
        advisory = parse_and_validate(_DECISION_CLASS, result.text or "")
    except JudgmentSchemaError:
        audit.append(
            conn,
            JudgmentFallbackPayload(decision_class=_DECISION_CLASS, reason="schema_invalid"),
            symbol=symbol,
            correlation_id=result.correlation_id,
        )
        return None, None

    assert isinstance(advisory, NewsAdvisory)
    return advisory, result.correlation_id
