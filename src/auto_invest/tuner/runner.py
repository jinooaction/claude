"""자율 튜너 오케스트레이션 (스펙 005, data-model.md §10).

흐름: 스냅샷 → detect → classify → (apply 모드) 게이트·적용·감사 → 리포트.

dry-run 은 순수 분석이다 — 벽시계 `now`·감사 상태에 의존하지 않아 재현 가능
(SC-A01). 설정 파일·감사를 쓰지 않는다(SC-A03). apply 모드만 게이트(장 시간·
측정)·멱등 dedup·실제 적용·감사 기록을 수행한다.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from auto_invest.persistence.audit import (
    AutoTunedCanaryCandidatePayload,
    AutoTunedL1Payload,
    AutoTunedL2CanaryEnteredPayload,
    AutoTunedL4ForensicPayload,
    AutoTunerRunPayload,
    append,
)
from auto_invest.telemetry.thresholds import load_thresholds
from auto_invest.tuner import gates
from auto_invest.tuner.candidate import build_canary_candidate
from auto_invest.tuner.classify import classify_all
from auto_invest.tuner.detect import detect
from auto_invest.tuner.knobs import apply_threshold
from auto_invest.tuner.models import (
    AppliedChange,
    CanaryCandidate,
    CanaryValidationResult,
    Classification,
    SkipReason,
    TunerRunResult,
)
from auto_invest.tuner.report import write_report

Mode = Literal["dry_run", "apply"]


def _utcnow_iso_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _already_applied(
    conn: sqlite3.Connection, *, kpi_name: str, session_date: str
) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM audit_log
        WHERE event_type = 'AUTO_TUNED_L1'
          AND json_extract(payload_json, '$.kpi_name') = ?
          AND json_extract(payload_json, '$.session_date') = ?
        """,
        (kpi_name, session_date),
    ).fetchone()
    return int(row["n"]) > 0


def _candidate_already_recorded(
    conn: sqlite3.Connection, *, candidate_id: str, session_date: str
) -> bool:
    """같은 세션·같은 후보의 캐너리 후보 기록이 이미 있으면 True(멱등 dedup)."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM audit_log
        WHERE event_type = 'AUTO_TUNED_CANARY_CANDIDATE'
          AND json_extract(payload_json, '$.candidate_id') = ?
          AND json_extract(payload_json, '$.session_date') = ?
        """,
        (candidate_id, session_date),
    ).fetchone()
    return int(row["n"]) > 0


def run_tuner(
    *,
    db_path: Path,
    thresholds_path: Path,
    kernel_path: Path | None = None,
    as_of: date,
    mode: Mode,
    window_short_days: int = 7,
    window_long_days: int = 30,
    min_sample: int = gates.DEFAULT_MIN_SAMPLE,
    now: datetime | None = None,
    output_root: Path | None = None,
    tunables_path: Path = Path("config/judgment_tunables.toml"),
) -> TunerRunResult:
    session_date = as_of.isoformat()
    thresholds_target = str(thresholds_path).replace("\\", "/")
    tunables_target = str(tunables_path).replace("\\", "/")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        tiers = load_thresholds(thresholds_path)
        candidates = detect(
            conn,
            as_of=as_of,
            tiers=tiers,
            thresholds_path=thresholds_target,
            window_short_days=window_short_days,
            window_long_days=window_long_days,
            tunables_path=tunables_target,
        )
        classifications = classify_all(candidates, kernel_path=kernel_path)

        applied: list[AppliedChange] = []
        canary_entered: list[Classification] = []
        canary_candidates: list[CanaryCandidate] = []
        canary_validations: list[CanaryValidationResult] = []
        awaiting_human_merge: list[Classification] = []
        skipped: list[tuple[str, SkipReason]] = []

        apply_now = now or datetime.now(UTC)

        for c in classifications:
            cand = c.candidate
            if c.tier == "L4":
                awaiting_human_merge.append(c)
                if mode == "apply":
                    append(
                        conn,
                        AutoTunedL4ForensicPayload(
                            session_date=session_date,
                            candidate_id=cand.candidate_id,
                            detection_rule=cand.detection_rule,
                            kernel_groups=list(c.kernel_groups),
                            target_paths=list(cand.proposed.target_paths),
                            reason=c.reason,
                        ),
                    )
                continue
            if c.tier in ("L2", "L3"):
                canary_candidate = build_canary_candidate(c)
                if canary_candidate is None:
                    # 구체 노브 없음 → 기존 동작(캐너리 진입 식별 마커만).
                    canary_entered.append(c)
                    if mode == "apply":
                        append(
                            conn,
                            AutoTunedL2CanaryEnteredPayload(
                                session_date=session_date,
                                candidate_id=cand.candidate_id,
                                authority_tier=c.tier,
                                detection_rule=cand.detection_rule,
                                proposed_change=cand.rationale,
                                target_paths=list(cand.proposed.target_paths),
                            ),
                        )
                    continue

                canary_candidates.append(canary_candidate)
                if mode == "apply":
                    if _candidate_already_recorded(
                        conn,
                        candidate_id=canary_candidate.candidate_id,
                        session_date=session_date,
                    ):
                        skipped.append(
                            (canary_candidate.candidate_id, "already_validated_this_session")
                        )
                        continue
                    append(
                        conn,
                        AutoTunedCanaryCandidatePayload(
                            session_date=session_date,
                            candidate_id=canary_candidate.candidate_id,
                            detection_rule=canary_candidate.detection_rule,
                            authority_tier=canary_candidate.authority_tier,
                            target_path=canary_candidate.target_path,
                            config_key=canary_candidate.config_key,
                            old_value=canary_candidate.old_value,
                            new_value=canary_candidate.new_value,
                            recommended_tier=canary_candidate.recommended_tier,
                            recommended_window_days=canary_candidate.recommended_window_days,
                        ),
                    )
                continue

            # L1
            if cand.proposed.kind != "threshold_tighten":
                skipped.append((cand.candidate_id, "no_apply_path"))
                continue
            if mode == "dry_run":
                # 순수 분석: 게이트·적용·감사 없음(재현성·무변경 보장).
                continue
            if gates.market_hours_blocked(apply_now):
                skipped.append((cand.candidate_id, "market_hours"))
                continue
            if not gates.measurement_sufficient(cand.measurement_sample, min_sample):
                skipped.append((cand.candidate_id, "insufficient_measurement"))
                continue
            if _already_applied(
                conn, kpi_name=cand.kpi_name, session_date=session_date
            ):
                skipped.append((cand.candidate_id, "already_applied_this_session"))
                continue

            entry = tiers.entries[cand.kpi_name]
            tier_before = entry.tier_b
            old_value, new_value = apply_threshold(
                thresholds_path,
                cand.kpi_name,
                Decimal(str(cand.proposed.new_value)),
            )
            seq = append(
                conn,
                AutoTunedL1Payload(
                    session_date=session_date,
                    detection_rule=cand.detection_rule,
                    kpi_name=cand.kpi_name,
                    config_key=str(cand.proposed.config_key),
                    old_value=old_value,
                    new_value=new_value,
                    tier_before=str(tier_before),
                    tier_after=new_value,
                    window=cand.window,
                ),
            )
            applied.append(
                AppliedChange(
                    candidate_id=cand.candidate_id,
                    config_key=str(cand.proposed.config_key),
                    old_value=old_value,
                    new_value=new_value,
                    audit_seq=seq,
                )
            )

        result = TunerRunResult(
            session_date=session_date,
            generated_at_utc=_utcnow_iso_ms(),
            mode=mode,
            candidates=tuple(classifications),
            applied=tuple(applied),
            canary_entered=tuple(canary_entered),
            awaiting_human_merge=tuple(awaiting_human_merge),
            skipped=tuple(skipped),
            canary_candidates=tuple(canary_candidates),
            canary_validations=tuple(canary_validations),
        )

        if mode == "apply":
            append(
                conn,
                AutoTunerRunPayload(
                    session_date=session_date,
                    mode=mode,
                    candidates_count=len(classifications),
                    applied_count=len(applied),
                    canary_count=len(canary_entered) + len(canary_candidates),
                    l4_count=len(awaiting_human_merge),
                    skipped_count=len(skipped),
                ),
            )
            conn.commit()

        if output_root is not None:
            write_report(result, output_root=output_root)

        return result
    finally:
        conn.close()


__all__ = ["run_tuner"]
