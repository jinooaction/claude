"""자율 튜너 데이터 모델 (스펙 005, data-model.md §2~7).

전부 frozen dataclass(불변) + 결정론적. 단위는 문자열 Decimal로 직렬화해
감사·리포트와 byte-stable하게 맞춘다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AuthorityTier = Literal["L1", "L2", "L3", "L4"]

SkipReason = Literal[
    "market_hours",
    "insufficient_measurement",
    "already_applied_this_session",
    "no_apply_path",
    "non_l1_tier",
]

ChangeKind = Literal["threshold_tighten", "proposal_only"]


@dataclass(frozen=True)
class ProposedChange:
    """후보가 제안하는 구체적 변경."""

    kind: ChangeKind
    target_paths: tuple[str, ...]
    config_key: str | None = None
    old_value: str | None = None
    new_value: str | None = None


@dataclass(frozen=True)
class CandidateChange:
    """탐지 규칙 1건의 발화 결과(분류 전)."""

    candidate_id: str
    detection_rule: str
    kpi_name: str
    observed_value: str
    observed_tier: str
    window: str
    proposed: ProposedChange
    rationale: str
    measurement_sample: int


@dataclass(frozen=True)
class Classification:
    """후보에 부여된 권한 등급."""

    candidate: CandidateChange
    tier: AuthorityTier
    kernel_groups: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""


@dataclass(frozen=True)
class AppliedChange:
    """실제 적용된 L1 변경."""

    candidate_id: str
    config_key: str
    old_value: str
    new_value: str
    audit_seq: int


@dataclass(frozen=True)
class TunerRunResult:
    """한 번의 `tune` 실행 산출물(→ auto-tuner-report.json)."""

    session_date: str
    generated_at_utc: str
    mode: Literal["dry_run", "apply"]
    candidates: tuple[Classification, ...]
    applied: tuple[AppliedChange, ...]
    canary_entered: tuple[Classification, ...]
    awaiting_human_merge: tuple[Classification, ...]
    skipped: tuple[tuple[str, SkipReason], ...]


__all__ = [
    "AppliedChange",
    "AuthorityTier",
    "CandidateChange",
    "ChangeKind",
    "Classification",
    "ProposedChange",
    "SkipReason",
    "TunerRunResult",
]
