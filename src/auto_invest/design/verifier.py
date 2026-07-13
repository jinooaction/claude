"""Fail-closed verification for generated design rules.

`ok=True` means static validation, backtest evidence, and paper/simulation
evidence all ran and passed for the same candidate fingerprint. Missing dynamic
integration is a proposal-only waiting state, never a pass.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from auto_invest.design.validator import validate_generated_rules

StageName = Literal["static", "backtest", "paper"]
StageStatus = Literal["PASS", "WAIT", "FAIL"]
OverallStatus = Literal["VERIFIED", "WAIT_DYNAMIC_VALIDATION", "BLOCKED"]


@dataclass(frozen=True)
class VerificationStageResult:
    stage: StageName | str
    status: StageStatus
    reason_code: str
    reason_ko: str
    candidate_fingerprint: str
    evidence_ref: str | None = None
    observed_at_utc: str | None = None
    fresh_until_utc: str | None = None
    metrics: dict[str, object] = field(default_factory=dict)


StageValidator = Callable[
    ...,
    VerificationStageResult | None,
]


@dataclass(frozen=True)
class VerifyResult:
    """`verify_rules` result with legacy compatibility fields.

    - `ok=True`: all required stages passed with evidence for one candidate.
    - `ok=False`: either the candidate is blocked or waiting for real dynamic
      validation. Callers must not treat this as live authority.
    """

    ok: bool
    reason: str | None = None
    detail: str = ""
    backtest_skipped: bool = False
    paper_run_skipped: bool = False
    candidate_fingerprint: str = ""
    overall_status: OverallStatus = "BLOCKED"
    static_result: VerificationStageResult | None = None
    backtest_result: VerificationStageResult | None = None
    paper_result: VerificationStageResult | None = None
    blocking_reasons: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


def candidate_fingerprint(toml_text: str) -> str:
    """Return the deterministic candidate digest used to bind evidence."""
    normalized = toml_text.strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def verify_rules(
    toml_text: str,
    *,
    kis_balance_usd: Decimal,
    backtest_validator: StageValidator | None = None,
    paper_validator: StageValidator | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> VerifyResult:
    """Validate generated rules and fail closed on missing dynamic evidence."""
    now_fn = now_fn or (lambda: datetime.now(UTC))
    fingerprint = candidate_fingerprint(toml_text)

    static = validate_generated_rules(
        toml_text,
        kis_balance_usd=kis_balance_usd,
    )
    if not static.ok:
        static_result = _stage(
            "static",
            "FAIL",
            static.reason or "static_validation_failed",
            static.detail,
            fingerprint,
        )
        return _aggregate(
            candidate_fingerprint=fingerprint,
            static_result=static_result,
            backtest_result=_wait_stage(
                "backtest",
                fingerprint,
                "backtest_not_run_after_static_failure",
            ),
            paper_result=_wait_stage(
                "paper",
                fingerprint,
                "paper_not_run_after_static_failure",
            ),
        )

    static_result = _stage(
        "static",
        "PASS",
        "static_validation_passed",
        "정적 검증 통과",
        fingerprint,
        evidence_ref="static-validator",
    )
    backtest_result = _run_dynamic_stage(
        "backtest",
        backtest_validator,
        toml_text=toml_text,
        candidate_fingerprint=fingerprint,
        now=now_fn(),
    )
    paper_result = _run_dynamic_stage(
        "paper",
        paper_validator,
        toml_text=toml_text,
        candidate_fingerprint=fingerprint,
        now=now_fn(),
    )
    return _aggregate(
        candidate_fingerprint=fingerprint,
        static_result=static_result,
        backtest_result=backtest_result,
        paper_result=paper_result,
    )


def availability_notice() -> str:
    """Tell the operator that dynamic validation is required and fail-closed."""
    return "\n".join(
        [
            "검증 단계 가용성:",
            "- 정적 검증: 활성화 (cap·whitelist·자본 한도·종목 형식)",
            "- 백테스트 검증: 별도 증거가 필요하며 없으면 WAIT_DYNAMIC_VALIDATION",
            "- paper/모의 검증: 별도 증거가 필요하며 없으면 WAIT_DYNAMIC_VALIDATION",
            "- 현재 design 명령은 PROPOSAL_ONLY이며 실거래 실행 권한이 없습니다.",
        ]
    )


def _run_dynamic_stage(
    stage: StageName,
    validator: StageValidator | None,
    *,
    toml_text: str,
    candidate_fingerprint: str,
    now: datetime,
) -> VerificationStageResult:
    if validator is None:
        return _wait_stage(stage, candidate_fingerprint, f"{stage}_validator_not_configured")

    try:
        result = validator(
            toml_text=toml_text,
            candidate_fingerprint=candidate_fingerprint,
        )
    except Exception as exc:  # noqa: BLE001 - evidence failures become structured blocks
        return _stage(
            stage,
            "FAIL",
            f"{stage}_exception",
            f"{stage} 검증 실행 중 예외: {exc}",
            candidate_fingerprint,
        )

    if not isinstance(result, VerificationStageResult):
        return _stage(
            stage,
            "FAIL",
            f"{stage}_malformed_result",
            f"{stage} 검증 결과가 구조화된 증거가 아닙니다.",
            candidate_fingerprint,
        )
    if result.stage != stage:
        return _stage(
            stage,
            "FAIL",
            f"{stage}_malformed_result",
            f"{stage} 검증 결과의 stage가 일치하지 않습니다: {result.stage!r}",
            candidate_fingerprint,
        )
    if result.candidate_fingerprint != candidate_fingerprint:
        return _stage(
            stage,
            "FAIL",
            f"{stage}_fingerprint_mismatch",
            f"{stage} 증거가 다른 후보 지문에 묶여 있습니다.",
            candidate_fingerprint,
        )
    if result.status == "PASS" and not result.evidence_ref:
        return _stage(
            stage,
            "FAIL",
            f"{stage}_missing_evidence",
            f"{stage} PASS에는 evidence_ref가 필요합니다.",
            candidate_fingerprint,
        )
    if result.fresh_until_utc and _is_stale(result.fresh_until_utc, now):
        return _stage(
            stage,
            "FAIL",
            f"{stage}_stale_evidence",
            f"{stage} 증거가 신선도 만료 시각을 지났습니다.",
            candidate_fingerprint,
        )
    return result


def _aggregate(
    *,
    candidate_fingerprint: str,
    static_result: VerificationStageResult,
    backtest_result: VerificationStageResult,
    paper_result: VerificationStageResult,
) -> VerifyResult:
    stages = (static_result, backtest_result, paper_result)
    blocking_reasons = tuple(
        stage.stage
        for stage in stages
        if stage.status != "PASS"
    )
    evidence_refs = tuple(
        ref
        for ref in (
            backtest_result.evidence_ref,
            paper_result.evidence_ref,
        )
        if ref
    )

    if any(stage.status == "FAIL" for stage in stages):
        overall: OverallStatus = "BLOCKED"
    elif all(stage.status == "PASS" for stage in stages):
        overall = "VERIFIED"
    else:
        overall = "WAIT_DYNAMIC_VALIDATION"

    ok = overall == "VERIFIED"
    return VerifyResult(
        ok=ok,
        reason=_legacy_reason(stages) if not ok else None,
        detail=_detail(stages),
        backtest_skipped=backtest_result.status != "PASS",
        paper_run_skipped=paper_result.status != "PASS",
        candidate_fingerprint=candidate_fingerprint,
        overall_status=overall,
        static_result=static_result,
        backtest_result=backtest_result,
        paper_result=paper_result,
        blocking_reasons=blocking_reasons,
        evidence_refs=evidence_refs,
    )


def _legacy_reason(stages: tuple[VerificationStageResult, ...]) -> str:
    static_result, backtest_result, paper_result = stages
    if static_result.status != "PASS":
        return static_result.reason_code
    if backtest_result.status != "PASS":
        return "backtest_fail"
    if paper_result.status != "PASS":
        return "paper_run_fail"
    return "parse_error"


def _detail(stages: tuple[VerificationStageResult, ...]) -> str:
    return "; ".join(
        f"{stage.stage}:{stage.status}:{stage.reason_ko}"
        for stage in stages
        if stage.status != "PASS"
    )


def _wait_stage(
    stage: StageName,
    candidate_fingerprint: str,
    reason_code: str,
) -> VerificationStageResult:
    return _stage(
        stage,
        "WAIT",
        reason_code,
        f"{stage} 검증 증거가 아직 없습니다.",
        candidate_fingerprint,
    )


def _stage(
    stage: StageName,
    status: StageStatus,
    reason_code: str,
    reason_ko: str,
    candidate_fingerprint: str,
    *,
    evidence_ref: str | None = None,
) -> VerificationStageResult:
    return VerificationStageResult(
        stage=stage,
        status=status,
        reason_code=reason_code,
        reason_ko=reason_ko,
        candidate_fingerprint=candidate_fingerprint,
        evidence_ref=evidence_ref,
        metrics={},
    )


def _is_stale(value: str, now: datetime) -> bool:
    try:
        fresh_until = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if fresh_until.tzinfo is None:
        fresh_until = fresh_until.replace(tzinfo=UTC)
    return fresh_until < now
