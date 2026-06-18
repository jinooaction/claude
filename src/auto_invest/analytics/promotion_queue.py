"""캐너리 합격 후보 운영자 승격 큐 (읽기 전용 소비자 계층).

배경 / 왜 필요한가:
  자율 튜너(스펙 005)의 L2/L3 후보(예: 판단 지점 `max_tokens`)는 하드닝 캐너리(스펙 012)로
  검증된다. 그런데 검증을 *통과해도*(`outcome="passed"`) 그 변경은 적용되지 않는다 —
  `AUTO_TUNED_CANARY_VALIDATED` 로 감사 로그에 `promoted=False` 로 남고 버려진다
  (`tuner/runner.py`, `tuner/canary_submit.py`). 이 합격 이벤트를 *읽는 곳이 없어서*
  시스템이 스스로 검증한 개선이 감사 로그 깊숙이 묻힌다 — 자율 성장의 누수다.

이 모듈이 하는 일:
  감사 로그의 `AUTO_TUNED_CANARY_CANDIDATE`(변경 상세: config_key·old→new)와
  `AUTO_TUNED_CANARY_VALIDATED`(결과: outcome·promoted)를 `candidate_id` 로 이어, "캐너리를
  통과했고 아직 승격되지 않은" 후보를 운영자 승격 큐로 종합한다. 변경 내용·캐너리 run_id·
  검증일을 한눈에 보이는 텍스트 + 기계용 JSON 으로 낸다. **새 검증·캐너리 실행을 하지
  않는다** — 발행된 감사 이벤트를 집계할 뿐이다(money_path 와 같은 소비자 계층).

안전 경계(중요):
  순수·결정론·비커널·읽기 전용. 주문 0건, 돈 0 이동, **자동 승격 0건**. 이건 *가시성*이지
  승격이 아니다. 캐너리 합격은 검증일 뿐 배포·승격이 아니며(헌법 IX.B-2), 라이브 승격은
  운영자/스펙 006 게이트 전용이다. 이 모듈은 합격 후보를 운영자가 한눈에 보고 승격을
  *결정*할 수 있게 *표면화*할 뿐, 어떤 것도 적용하지 않는다. 같은 후보가 나중에 재검증돼
  불합격/스킵이 되면 *최신* 판정이 이긴다(낡은 합격이 큐에 영영 남지 않는다).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

SCHEMA_VERSION = "1.0"

# 감사 이벤트 타입(audit.py 와 동일 — 재사용보다 명시로 결합도 낮춤).
EVENT_CANDIDATE = "AUTO_TUNED_CANARY_CANDIDATE"
EVENT_VALIDATED = "AUTO_TUNED_CANARY_VALIDATED"

# 캐너리 검증 결과 라벨(canary_submit 과 동일).
OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_SKIPPED = "skipped"
OUTCOME_ERROR = "internal_error"

# 변경 상세를 못 찾았을 때의 표시(VALIDATED 는 있는데 CANDIDATE 가 없는 비정상 케이스).
_UNKNOWN = "(상세 불명)"


@dataclass(frozen=True)
class QueueItem:
    """승격 대기 1건 — 캐너리를 통과했고 아직 승격되지 않은 후보."""

    candidate_id: str
    detection_rule: str
    authority_tier: str  # L2 | L3
    target_path: str
    config_key: str
    old_value: str
    new_value: str
    recommended_tier: str
    recommended_window_days: int | None
    canary_run_id: str | None
    validated_session_date: str | None  # 합격 판정이 기록된 세션 날짜
    candidate_session_date: str | None  # 후보가 구체화된 세션 날짜

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "detection_rule": self.detection_rule,
            "authority_tier": self.authority_tier,
            "target_path": self.target_path,
            "config_key": self.config_key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "recommended_tier": self.recommended_tier,
            "recommended_window_days": self.recommended_window_days,
            "canary_run_id": self.canary_run_id,
            "validated_session_date": self.validated_session_date,
            "candidate_session_date": self.candidate_session_date,
            # 불변(헌법 IX.B-2)을 항목마다 명시 — 이 큐는 가시성이지 승격이 아니다.
            "promotion": "operator-gated (spec 006); NOT auto-promoted",
        }


@dataclass(frozen=True)
class PromotionQueueReport:
    """캐너리 합격 후보 승격 큐 종합 — 읽기 전용 결정 표면."""

    schema_version: str
    as_of_utc: str
    queue: list[QueueItem]  # 승격 대기(최신 판정이 합격, 미승격) — 정렬됨
    passed_pending: int  # = len(queue)
    failed: int  # 최신 판정이 불합격인 후보 수
    skipped: int  # 최신 판정이 스킵(리플레이 데이터 없음 등)
    errored: int  # 최신 판정이 내부 오류로 격리됨
    headline: str  # 운영자가 먼저 읽는 한 문장
    next_action: str  # 운영자 게이트가 무엇인지

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "as_of_utc": self.as_of_utc,
            "queue": [item.to_dict() for item in self.queue],
            "counts": {
                "passed_pending": self.passed_pending,
                "failed": self.failed,
                "skipped": self.skipped,
                "errored": self.errored,
            },
            "headline": self.headline,
            "next_action": self.next_action,
        }

    def as_text(self) -> str:
        lines = [
            f"# 캐너리 합격 후보 승격 큐 (as of {self.as_of_utc}) — 읽기 전용, 돈 0 이동",
            "",
            f"> {self.headline}",
            "",
            "| 결과 | 수 |",
            "|------|----:|",
            f"| ✅ 합격·승격 대기 | {self.passed_pending} |",
            f"| ❌ 불합격 | {self.failed} |",
            f"| ⏭ 스킵(데이터 없음 등) | {self.skipped} |",
            f"| ⚠ 내부 오류 | {self.errored} |",
        ]
        if self.queue:
            lines += [
                "",
                "## 승격 대기 (운영자 승인 필요)",
                "",
                "| 후보 | 등급 | 대상 | 변경 | 캐너리 | 검증일 |",
                "|------|:----:|------|------|--------|--------|",
            ]
            for item in self.queue:
                window = (
                    f"{item.recommended_tier}/{item.recommended_window_days}d"
                    if item.recommended_window_days is not None
                    else item.recommended_tier
                )
                lines.append(
                    f"| {item.candidate_id} | {item.authority_tier} | "
                    f"{item.config_key} ({item.target_path}) | "
                    f"{item.old_value} → {item.new_value} | {window} | "
                    f"{item.validated_session_date or '?'} |"
                )
        else:
            lines += ["", "_승격 대기 후보 없음._"]
        lines += [
            "",
            "## 다음 행동",
            "",
            f"- {self.next_action}",
            "",
            "⚠ 이건 가시성 표면이다(읽기 전용). 캐너리 합격은 검증일 뿐 배포·승격이 아니다"
            "(헌법 IX.B-2). 라이브 승격은 운영자/스펙 006 게이트 전용 — 이 큐는 자동으로 "
            "어떤 것도 적용하지 않는다.",
        ]
        return "\n".join(lines)


def assess_promotion_queue(
    *,
    candidates: list[dict],
    validations: list[dict],
    promoted_ids: set[str] | None = None,
    now: datetime,
) -> PromotionQueueReport:
    """발행된 캐너리 감사 이벤트로 승격 큐를 종합(순수·결정론·읽기 전용).

    candidates: `AUTO_TUNED_CANARY_CANDIDATE` 페이로드 dict 목록(변경 상세).
    validations: `AUTO_TUNED_CANARY_VALIDATED` 페이로드 dict 목록(결과). **감사 seq 오름차순
        (시간순)을 가정** — 같은 후보의 여러 판정 중 *마지막*이 최신(권위)이다.
    promoted_ids: 이미 운영자가 승격한 후보 id(미래 확장용, 기본 빈 집합 — 아직 승격 0건).
    now: 보고 시각(UTC). tz 없으면 UTC 로 본다.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    as_of = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    promoted = promoted_ids or set()

    # 후보 상세: candidate_id → 마지막으로 본 후보 페이로드(가장 최신 구체화).
    detail: dict[str, dict] = {}
    for c in candidates:
        cid = c.get("candidate_id")
        if cid:
            detail[str(cid)] = c

    # 최신 판정: candidate_id → 마지막(시간순) 판정 페이로드. 재검증이 과거 판정을 덮는다.
    latest: dict[str, dict] = {}
    for v in validations:
        cid = v.get("candidate_id")
        if cid:
            latest[str(cid)] = v

    queue: list[QueueItem] = []
    failed = skipped = errored = 0
    for cid, v in latest.items():
        outcome = v.get("outcome")
        if cid in promoted:
            continue  # 이미 승격됨 — 대기 아님.
        if outcome == OUTCOME_PASSED:
            queue.append(_queue_item(cid, detail.get(cid), v))
        elif outcome == OUTCOME_FAILED:
            failed += 1
        elif outcome == OUTCOME_SKIPPED:
            skipped += 1
        else:  # internal_error 또는 알 수 없는 상태 → 오류로 격리(거짓 합격 0).
            errored += 1

    # 결정적 정렬: 검증일 → 후보 id(같은 입력이면 같은 순서, SC 재현성).
    queue.sort(key=lambda i: (i.validated_session_date or "", i.candidate_id))

    passed_pending = len(queue)
    headline = _headline(passed_pending, failed, skipped, errored)
    next_action = _next_action(passed_pending)
    return PromotionQueueReport(
        schema_version=SCHEMA_VERSION,
        as_of_utc=as_of,
        queue=queue,
        passed_pending=passed_pending,
        failed=failed,
        skipped=skipped,
        errored=errored,
        headline=headline,
        next_action=next_action,
    )


def _queue_item(cid: str, detail: dict | None, validation: dict) -> QueueItem:
    """후보 상세(CANDIDATE) + 판정(VALIDATED)을 한 줄로 합친다. 상세 없으면 보수적 표시."""
    d = detail or {}
    window = d.get("recommended_window_days")
    return QueueItem(
        candidate_id=cid,
        detection_rule=str(d.get("detection_rule", _UNKNOWN)),
        authority_tier=str(d.get("authority_tier", _UNKNOWN)),
        target_path=str(d.get("target_path", _UNKNOWN)),
        config_key=str(d.get("config_key", _UNKNOWN)),
        old_value=str(d.get("old_value", _UNKNOWN)),
        new_value=str(d.get("new_value", _UNKNOWN)),
        recommended_tier=str(d.get("recommended_tier", _UNKNOWN)),
        recommended_window_days=int(window) if window is not None else None,
        canary_run_id=validation.get("canary_run_id"),
        validated_session_date=validation.get("session_date"),
        candidate_session_date=d.get("session_date"),
    )


def _headline(passed_pending: int, failed: int, skipped: int, errored: int) -> str:
    if passed_pending > 0:
        return (
            f"✅ 캐너리 합격·승격 대기 **{passed_pending}건** — 운영자 승인을 기다리는 "
            f"검증된 개선이 있다(자동 승격 0, 헌법 IX.B-2)."
        )
    if failed or errored:
        return (
            f"➖ 승격 대기 없음 — 최근 후보는 불합격 {failed}·오류 {errored}·스킵 {skipped}건. "
            "검증된 개선이 아직 없다(정상, 안전 자세)."
        )
    if skipped:
        return (
            f"⏳ 승격 대기 없음 — 후보 {skipped}건이 스킵(리플레이 데이터 없음 등). "
            "검증을 못 돌린 것이지 불합격은 아니다."
        )
    return "➖ 캐너리 후보 자체가 없음 — 튜너가 아직 L2/L3 후보를 검증하지 않았다."


def _next_action(passed_pending: int) -> str:
    if passed_pending > 0:
        return (
            "운영자가 위 합격 후보를 검토하고 승격을 결정한다(라이브 승격은 운영자/스펙 006 "
            "게이트 전용). 시스템은 자동으로 승격하지 않는다 — 이 큐는 가시성만 제공한다."
        )
    return (
        "할 일 없음 — 승격 대기 후보가 없다. 튜너가 L2/L3 후보를 검증해 합격시키면 여기 쌓인다."
    )


def load_canary_events(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    """감사 로그에서 캐너리 후보·검증 이벤트를 seq 오름차순으로 읽어 dict 목록으로.

    반환 `(candidates, validations)`. 읽기 전용 — 감사 로그를 수정하지 않는다.
    단일 컬럼만 읽으므로 `conn.row_factory` 설정과 무관하다(인덱스 접근).
    """
    candidates: list[dict] = []
    validations: list[dict] = []
    rows = conn.execute(
        "SELECT payload_json FROM audit_log "
        "WHERE event_type IN (?, ?) ORDER BY seq",
        (EVENT_CANDIDATE, EVENT_VALIDATED),
    )
    for row in rows:
        payload = json.loads(row[0])
        etype = payload.get("event_type")
        if etype == EVENT_CANDIDATE:
            candidates.append(payload)
        elif etype == EVENT_VALIDATED:
            validations.append(payload)
    return candidates, validations


def build_promotion_queue(
    conn: sqlite3.Connection,
    *,
    now: datetime,
    promoted_ids: set[str] | None = None,
) -> PromotionQueueReport:
    """감사 로그를 읽어 승격 큐를 종합하는 편의 함수(read + assess)."""
    candidates, validations = load_canary_events(conn)
    return assess_promotion_queue(
        candidates=candidates,
        validations=validations,
        promoted_ids=promoted_ids,
        now=now,
    )


__all__ = [
    "EVENT_CANDIDATE",
    "EVENT_VALIDATED",
    "OUTCOME_ERROR",
    "OUTCOME_FAILED",
    "OUTCOME_PASSED",
    "OUTCOME_SKIPPED",
    "SCHEMA_VERSION",
    "PromotionQueueReport",
    "QueueItem",
    "assess_promotion_queue",
    "build_promotion_queue",
    "load_canary_events",
]
