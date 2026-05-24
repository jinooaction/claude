"""자율 튜너 (스펙 005).

측정 → 분석 → 행동 루프를 헌법 안전 경계 안에서 닫는 순수 결정론적 엔진
(LLM 미호출). KPI 드리프트를 감지하고 권한 등급(L1~L4)으로 분류한 뒤,
저위험 L1 변경(KPI 임계값 조이기)을 장외·측정 충분·멱등하게 자동 적용한다.
"""

from __future__ import annotations

from auto_invest.tuner.classify import classify, classify_all
from auto_invest.tuner.detect import detect, parse_as_of
from auto_invest.tuner.models import (
    AppliedChange,
    AuthorityTier,
    CandidateChange,
    Classification,
    ProposedChange,
    SkipReason,
    TunerRunResult,
)
from auto_invest.tuner.runner import run_tuner

__all__ = [
    "AppliedChange",
    "AuthorityTier",
    "CandidateChange",
    "Classification",
    "ProposedChange",
    "SkipReason",
    "TunerRunResult",
    "classify",
    "classify_all",
    "detect",
    "parse_as_of",
    "run_tuner",
]
