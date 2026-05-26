"""Judgment-point registry — 헌법 III 계약 선언 (FR-001).

각 판단 지점은 트리거 조건·입력 계약·출력 스키마·지연 예산·비용 예산·모델·
max_tokens·자본 영향 여부·결정론적 폴백을 코드로 선언한다. 단일 레지스트리에
모여 조회 가능하다. 틱마다 호출 금지 — 트리거 발화 + 쿨다운에서만.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from auto_invest.judgment.schemas import (
    DailySummaryAdvisory,
    NewsAdvisory,
    VolatilityAdvisory,
)

# 비커널 튜닝 표면(스펙 012). 없으면 아래 하드코딩 기본값 사용 → 동작 무변경.
_TUNABLES_PATH = Path("config/judgment_tunables.toml")
# 튜너가 max_tokens 를 이 아래로 내리지 않는다(품질 바닥).
JUDGMENT_MAX_TOKENS_FLOOR = 32

# 비용 적합 기본 모델 (config/llm_prices.toml 에 존재):
#   저비용 enum/score 판단 → Haiku, 서술형 일일 요약 → Sonnet.
_HAIKU = "claude-haiku-4-5-20251001"
_SONNET = "claude-sonnet-4-6"


@dataclass(frozen=True)
class JudgmentPoint:
    """한 판단 지점의 헌법 III 계약."""

    decision_class: str
    output_schema: type[BaseModel]
    latency_budget_ms: int
    cost_budget_usd: Decimal
    model: str
    max_tokens: int
    affects_capital: bool
    trigger_description: str
    input_contract: str
    fallback_description: str


_REGISTRY: dict[str, JudgmentPoint] = {
    "volatility_assessment": JudgmentPoint(
        decision_class="volatility_assessment",
        output_schema=VolatilityAdvisory,
        latency_budget_ms=2_000,
        cost_budget_usd=Decimal("0.01"),
        model=_HAIKU,
        max_tokens=256,
        affects_capital=True,
        trigger_description=(
            "화이트리스트 종목의 단기 실현 변동성이 룰 임계값 초과 (쿨다운 존중)."
        ),
        input_contract="요약 통계만 (symbol, realized_vol_5m, threshold, ...). 원시 바 금지.",
        fallback_description="자문 없음 = v1 동작 (축소/건너뛰기 없음). 거래 진행.",
    ),
    "daily_summary": JudgmentPoint(
        decision_class="daily_summary",
        output_schema=DailySummaryAdvisory,
        latency_budget_ms=10_000,
        cost_budget_usd=Decimal("0.05"),
        model=_SONNET,
        max_tokens=700,
        affects_capital=False,
        trigger_description="장 마감 후 1회 (시각 게이트).",
        input_contract="그날 audit_log 집계 카운터 (원시 행 아님).",
        fallback_description="'요약 생성 불가', 결정론적 카운터만 표시. 리포트 정상 종료.",
    ),
    "news_screen": JudgmentPoint(
        decision_class="news_screen",
        output_schema=NewsAdvisory,
        latency_budget_ms=5_000,
        cost_budget_usd=Decimal("0.02"),
        model=_HAIKU,
        max_tokens=128,
        affects_capital=False,
        trigger_description=(
            "장 시작 전, 화이트리스트 종목 매칭 헤드라인 주입 시. 공급원 없으면 비활성."
        ),
        input_contract="{symbol, headline}. 새 뉴스 피드 구축 안 함 (주입 입력).",
        fallback_description="neutral 취급 (거래 영향 없음).",
    ),
}


def _apply_tunables_overlay(
    registry: dict[str, JudgmentPoint], path: Path
) -> dict[str, JudgmentPoint]:
    """`judgment_tunables.toml` 의 max_tokens 오버레이 적용 (스펙 012).

    파일/섹션/키가 없거나 값이 유효하지 않으면 기존 하드코딩값을 유지한다
    (조용한 폴백 — 절대 import 를 깨지 않는다). 바닥값 클램프.
    """
    try:
        if not path.exists():
            return registry
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return registry

    overlaid = dict(registry)
    for decision_class, point in registry.items():
        section = data.get(decision_class)
        if not isinstance(section, dict):
            continue
        raw = section.get("max_tokens")
        if not isinstance(raw, int) or isinstance(raw, bool):
            continue
        clamped = max(JUDGMENT_MAX_TOKENS_FLOOR, raw)
        if clamped != point.max_tokens:
            overlaid[decision_class] = replace(point, max_tokens=clamped)
    return overlaid


_REGISTRY = _apply_tunables_overlay(_REGISTRY, _TUNABLES_PATH)


def get(decision_class: str) -> JudgmentPoint:
    """판단 지점 계약 조회. 미등록이면 KeyError."""
    return _REGISTRY[decision_class]


def all_points() -> list[JudgmentPoint]:
    """등록된 모든 판단 지점."""
    return list(_REGISTRY.values())


def decision_classes() -> list[str]:
    """등록된 판단 지점 decision_class 목록."""
    return list(_REGISTRY.keys())
