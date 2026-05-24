"""Output schemas for LLM judgment points (헌법 III — output schema 계약).

Claude의 자유 텍스트 응답에서 JSON 한 덩어리를 추출해 판단 지점별 pydantic
모델로 검증한다. 검증을 통과한 자문만 결정론적 게이트로 전달된다(FR-006).
검증 실패(잘못된 enum·범위 밖 confidence·길이 초과·JSON 파싱 실패)는
`JudgmentSchemaError`로 올라가 호출자가 결정론적 폴백으로 전환한다.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class JudgmentSchemaError(ValueError):
    """LLM 판단 출력이 스키마 검증에 실패. 호출자는 폴백으로 전환한다."""


class VolatilityAdvisory(BaseModel):
    """volatility_assessment 출력. action 은 노출을 줄이거나 멈추는 자문일 뿐."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Literal["hold", "size_down", "halt"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=4000)


class NewsAdvisory(BaseModel):
    """news_screen 출력. 자문 스탠스 — bear 고신뢰만 당일 신규 매수 보류."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    stance: Literal["bull", "bear", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)


class DailySummaryAdvisory(BaseModel):
    """daily_summary 출력. 순수 자문 — 주문 경로 무접촉, 리포트에만 표시."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    narrative: str = Field(max_length=500)
    alerts: list[str] = Field(default_factory=list)


_SCHEMAS: dict[str, type[BaseModel]] = {
    "volatility_assessment": VolatilityAdvisory,
    "news_screen": NewsAdvisory,
    "daily_summary": DailySummaryAdvisory,
}


def schema_for(decision_class: str) -> type[BaseModel]:
    """판단 지점 decision_class 의 출력 스키마 모델을 반환."""
    try:
        return _SCHEMAS[decision_class]
    except KeyError as exc:
        raise JudgmentSchemaError(f"unknown decision_class: {decision_class}") from exc


def _extract_json_object(text: str) -> str:
    """자유 텍스트에서 첫 번째 균형 잡힌 JSON 객체 `{...}` 를 추출.

    Claude 가 마크다운 펜스나 설명 문장을 곁들여 응답해도 JSON 본체만 뽑는다.
    """
    start = text.find("{")
    if start == -1:
        raise JudgmentSchemaError("응답에 JSON 객체가 없음")
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise JudgmentSchemaError("JSON 객체가 닫히지 않음")


def parse_and_validate(decision_class: str, raw_text: str) -> BaseModel:
    """raw_text 에서 JSON 을 추출해 판단 지점 스키마로 검증한 자문을 반환.

    실패하면 `JudgmentSchemaError`. 호출자는 이를 폴백 신호로 변환한다.
    """
    model = schema_for(decision_class)
    json_str = _extract_json_object(raw_text)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise JudgmentSchemaError(f"JSON 파싱 실패: {exc}") from exc
    if not isinstance(data, dict):
        raise JudgmentSchemaError("JSON 최상위가 객체가 아님")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise JudgmentSchemaError(f"스키마 검증 실패: {exc}") from exc
