"""스펙 069 — 자율 승격 실행 루프.

스펙 068의 read-only 승격 판단을 forward paper 등록과 hardened canary
제출 상태로 변환한다. 이 모듈은 브로커 API, 주문, 자본 사다리, live 설정,
sentinel 파일을 직접 건드리지 않는다.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.evolution_loop import mask_sensitive_values
from auto_invest.analytics.promotion_loop import (
    STAGE_CANARY_CANDIDATE,
    STAGE_EXISTING_GATE_READY,
    STAGE_FORWARD_REGISTRATION_READY,
)

SCHEMA_VERSION = "1.0"

OVERALL_OK = "ok"
OVERALL_DEGRADED = "degraded"

ACTION_FORWARD_REGISTRATION = "forward_registration"
ACTION_CANARY_SUBMISSION = "canary_submission"
ACTION_EXISTING_GATE_REPORT = "existing_gate_report"

STATUS_REGISTERED = "registered"
STATUS_ALREADY_REGISTERED = "already_registered"
STATUS_SUBMITTED = "submitted"
STATUS_ALREADY_SUBMITTED = "already_submitted"
STATUS_REPORTED = "reported"

DEFAULT_PAPER_CAPITAL_USD = 12_000.0
MAX_PAPER_CAPITAL_USD = 100_000.0
DEFAULT_MAX_SYMBOLS = 120
DEFAULT_MIN_BARS = 1_000
DEFAULT_CANARY_BANDS_TOML = "config/canary_bands_reassign.toml"

_SAFE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


@dataclass(frozen=True)
class PromotionAction:
    kind: str
    candidate_id: str
    title_ko: str
    stage: str
    status: str
    reason_ko: str
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "candidate_id": self.candidate_id,
            "title_ko": self.title_ko,
            "stage": self.stage,
            "status": self.status,
            "reason_ko": self.reason_ko,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class ActionBlock:
    candidate_id: str
    title_ko: str
    stage: str
    field: str
    reason: str
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title_ko": self.title_ko,
            "stage": self.stage,
            "field": self.field,
            "reason": self.reason,
            "reason_ko": self.reason_ko,
        }


@dataclass(frozen=True)
class PromotionActionRun:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    actions: tuple[PromotionAction, ...]
    blocked: tuple[ActionBlock, ...]
    missing_inputs: tuple[str, ...]
    forward_registry_next: Mapping[str, Any]
    canary_submissions_next: Mapping[str, Any]

    @property
    def counts(self) -> dict[str, int]:
        counts = {
            STATUS_REGISTERED: 0,
            STATUS_ALREADY_REGISTERED: 0,
            STATUS_SUBMITTED: 0,
            STATUS_ALREADY_SUBMITTED: 0,
            STATUS_REPORTED: 0,
            "blocked": len(self.blocked),
        }
        for action in self.actions:
            if action.status in counts:
                counts[action.status] += 1
        return counts

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "counts": self.counts,
            "missing_inputs": list(self.missing_inputs),
            "actions": [action.to_dict() for action in self.actions],
            "blocked": [block.to_dict() for block in self.blocked],
            "forward_registry_next": dict(self.forward_registry_next),
            "canary_submissions_next": dict(self.canary_submissions_next),
        }

    def as_markdown(self) -> str:
        lines = [
            "# 자율 승격 실행 루프 최신 실행",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| schema_version | {self.schema_version} |",
            f"| run_id | {self.run_id} |",
            f"| commit | {self.commit} |",
            f"| timestamp_utc | {self.timestamp_utc} |",
            f"| overall_status | {self.overall_status} |",
            "",
            "## 한 줄 결론",
            "",
            "승격 후보를 실거래로 바로 보내지 않고, forward paper 등록 큐와 "
            "hardened canary 제출 큐로만 자동 연결했다.",
            "",
            "## 집계",
            "",
        ]
        for key, value in self.counts.items():
            lines.append(f"- `{key}`: {value}")
        if self.missing_inputs:
            lines += ["", "## 누락 입력", ""]
            for item in self.missing_inputs:
                lines.append(f"- `{item}`")
        lines += ["", "## 수행된 자동 연결", ""]
        if not self.actions:
            lines.append("- 없음")
        for action in self.actions:
            lines.append(
                f"- `{action.status}` {action.kind}: "
                f"{action.title_ko} (`{action.candidate_id}`) — {action.reason_ko}"
            )
        lines += ["", "## 차단된 자동 연결", ""]
        if not self.blocked:
            lines.append("- 없음")
        for block in self.blocked:
            lines.append(
                f"- {block.title_ko} (`{block.candidate_id}`, {block.field}): "
                f"{block.reason_ko}"
            )
        lines += [
            "",
            "## 안전 문구",
            "",
            "이 실행은 주문, 자본 사다리, live 전략 설정, whitelist, caps, "
            "실거래 sentinel을 변경하지 않는다. forward 실행은 paper 전용이며, "
            "canary 실행은 기존 안전 게이트 밖에서 실주문을 만들지 않는다.",
        ]
        return mask_sensitive_values("\n".join(lines))


def build_promotion_actions(
    *,
    promotion_summary: Mapping[str, Any] | None,
    forward_registry: Mapping[str, Any] | None = None,
    canary_submissions: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    commit: str = "unknown",
    run_id: str = "local",
) -> PromotionActionRun:
    now = _ensure_utc(now or datetime.now(UTC))
    missing_inputs: list[str] = []
    actions: list[PromotionAction] = []
    blocked: list[ActionBlock] = []

    registry_next = _normalize_forward_registry(forward_registry)
    submissions_next = _normalize_canary_submissions(canary_submissions)

    assessments = _assessments(promotion_summary)
    if promotion_summary is None or not isinstance(promotion_summary, Mapping):
        missing_inputs.append("promotion_summary")
    elif "assessments" not in promotion_summary:
        missing_inputs.append("promotion_summary.assessments")

    for assessment in assessments:
        stage = str(assessment.get("stage") or "")
        candidate = _candidate(assessment)
        candidate_id = str(candidate.get("candidate_id") or assessment.get("candidate_id") or "")
        if not candidate_id:
            continue
        title = str(candidate.get("title_ko") or candidate_id)
        evidence = _mapping(candidate.get("promotion_evidence"))
        if stage == STAGE_FORWARD_REGISTRATION_READY:
            action, block, registry_next = _register_forward_track(
                candidate_id=candidate_id,
                title_ko=title,
                stage=stage,
                evidence=evidence,
                registry=registry_next,
                timestamp_utc=_iso(now),
            )
        elif stage == STAGE_CANARY_CANDIDATE:
            action, block, submissions_next = _submit_canary(
                candidate_id=candidate_id,
                title_ko=title,
                stage=stage,
                evidence=evidence,
                submissions=submissions_next,
                timestamp_utc=_iso(now),
            )
        elif stage == STAGE_EXISTING_GATE_READY:
            action = PromotionAction(
                kind=ACTION_EXISTING_GATE_REPORT,
                candidate_id=candidate_id,
                title_ko=title,
                stage=stage,
                status=STATUS_REPORTED,
                reason_ko="전략·실행 검증 완료 후보를 기존 자본/재지정 게이트 입력으로만 보고한다.",
                payload={
                    "next_gate": assessment.get("next_gate") or "existing-promotion-gates",
                    "safety_note": (
                        "no direct live order, no capital scaling, no live config change"
                    ),
                },
            )
            block = None
        else:
            action = None
            block = None
        if action is not None:
            actions.append(action)
        if block is not None:
            blocked.append(block)

    overall = OVERALL_DEGRADED if missing_inputs or blocked else OVERALL_OK
    return PromotionActionRun(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=_iso(now),
        overall_status=overall,
        actions=tuple(actions),
        blocked=tuple(blocked),
        missing_inputs=tuple(missing_inputs),
        forward_registry_next=registry_next,
        canary_submissions_next=submissions_next,
    )


def write_promotion_action_artifacts(
    run: PromotionActionRun,
    *,
    summary_out: Path | None = None,
    json_out: Path | None = None,
    forward_registry_out: Path | None = None,
    canary_submissions_out: Path | None = None,
) -> None:
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(run.as_markdown() + "\n", encoding="utf-8")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(run.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if forward_registry_out is not None:
        forward_registry_out.parent.mkdir(parents=True, exist_ok=True)
        forward_registry_out.write_text(
            json.dumps(
                run.forward_registry_next,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    if canary_submissions_out is not None:
        canary_submissions_out.parent.mkdir(parents=True, exist_ok=True)
        canary_submissions_out.write_text(
            json.dumps(
                run.canary_submissions_next,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def _register_forward_track(
    *,
    candidate_id: str,
    title_ko: str,
    stage: str,
    evidence: Mapping[str, Any],
    registry: Mapping[str, Any],
    timestamp_utc: str,
) -> tuple[PromotionAction | None, ActionBlock | None, dict[str, Any]]:
    track = _mapping(evidence.get("forward_track"))
    config, block = _forward_config(candidate_id, title_ko, stage, track)
    registry_next = _clone_state(registry, "tracks")
    if block is not None or config is None:
        return None, block, registry_next

    tracks = registry_next["tracks"]
    assert isinstance(tracks, list)
    existing = _find_existing_track(tracks, candidate_id, str(config["track_key"]))
    if existing is not None:
        return (
            PromotionAction(
                kind=ACTION_FORWARD_REGISTRATION,
                candidate_id=candidate_id,
                title_ko=title_ko,
                stage=stage,
                status=STATUS_ALREADY_REGISTERED,
                reason_ko="이미 promotion forward registry에 등록된 후보라 중복 추가하지 않았다.",
                payload=_redacted_payload(existing),
            ),
            None,
            registry_next,
        )

    row = {
        **config,
        "candidate_id": candidate_id,
        "title_ko": title_ko,
        "registered_at_utc": timestamp_utc,
        "status": "active",
    }
    tracks.append(row)
    return (
        PromotionAction(
            kind=ACTION_FORWARD_REGISTRATION,
            candidate_id=candidate_id,
            title_ko=title_ko,
            stage=stage,
            status=STATUS_REGISTERED,
            reason_ko="표본외 검증을 통과한 후보를 promotion 전용 forward paper 트랙에 등록했다.",
            payload=_redacted_payload(row),
        ),
        None,
        registry_next,
    )


def _submit_canary(
    *,
    candidate_id: str,
    title_ko: str,
    stage: str,
    evidence: Mapping[str, Any],
    submissions: Mapping[str, Any],
    timestamp_utc: str,
) -> tuple[PromotionAction | None, ActionBlock | None, dict[str, Any]]:
    track = _mapping(evidence.get("canary_track"))
    config, block = _canary_config(candidate_id, title_ko, stage, track)
    submissions_next = _clone_state(submissions, "submissions")
    if block is not None or config is None:
        return None, block, submissions_next

    rows = submissions_next["submissions"]
    assert isinstance(rows, list)
    existing = _find_existing_submission(rows, candidate_id)
    if existing is not None:
        return (
            PromotionAction(
                kind=ACTION_CANARY_SUBMISSION,
                candidate_id=candidate_id,
                title_ko=title_ko,
                stage=stage,
                status=STATUS_ALREADY_SUBMITTED,
                reason_ko="이미 promotion canary 제출 큐에 있는 후보라 중복 추가하지 않았다.",
                payload=_redacted_payload(existing),
            ),
            None,
            submissions_next,
        )

    row = {
        **config,
        "candidate_id": candidate_id,
        "title_ko": title_ko,
        "submitted_at_utc": timestamp_utc,
        "status": "pending",
    }
    rows.append(row)
    return (
        PromotionAction(
            kind=ACTION_CANARY_SUBMISSION,
            candidate_id=candidate_id,
            title_ko=title_ko,
            stage=stage,
            status=STATUS_SUBMITTED,
            reason_ko=(
                "forward 검증을 통과한 후보를 promotion 전용 hardened canary 검증 큐에 "
                "제출했다."
            ),
            payload=_redacted_payload(row),
        ),
        None,
        submissions_next,
    )


def _forward_config(
    candidate_id: str,
    title_ko: str,
    stage: str,
    track: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, ActionBlock | None]:
    track_key = str(track.get("track_key") or _safe_slug(candidate_id)).strip()
    portfolio_path = str(track.get("portfolio_path") or "").strip()
    db_path = str(track.get("db_path") or f"data/promotion_forward_{track_key}.db").strip()
    halt_path = str(
        track.get("halt_path") or f"data/promotion_forward_{track_key}.halt.flag"
    ).strip()

    checks = (
        ("track_key", track_key, _validate_track_key),
        ("portfolio_path", portfolio_path, _validate_portfolio_path),
        ("db_path", db_path, _validate_promotion_db_path),
        ("halt_path", halt_path, _validate_promotion_halt_path),
    )
    for field, value, validator in checks:
        ok, reason_ko = validator(value)
        if not ok:
            return None, _block(candidate_id, title_ko, stage, field, value, reason_ko)

    capital = _float(track.get("capital_usd"), DEFAULT_PAPER_CAPITAL_USD)
    if capital <= 0 or capital > MAX_PAPER_CAPITAL_USD:
        return None, _block(
            candidate_id,
            title_ko,
            stage,
            "capital_usd",
            capital,
            "paper capital은 0보다 크고 100000달러 이하여야 한다.",
        )
    max_symbols = _int(track.get("max_symbols"), DEFAULT_MAX_SYMBOLS)
    min_bars = _int(track.get("min_bars"), DEFAULT_MIN_BARS)
    if max_symbols <= 0 or min_bars <= 0:
        return None, _block(
            candidate_id,
            title_ko,
            stage,
            "max_symbols|min_bars",
            f"{max_symbols}|{min_bars}",
            "max_symbols와 min_bars는 양수여야 한다.",
        )

    return (
        {
            "track_key": track_key,
            "portfolio_path": portfolio_path,
            "db_path": db_path,
            "halt_path": halt_path,
            "capital_usd": capital,
            "max_symbols": max_symbols,
            "min_bars": min_bars,
        },
        None,
    )


def _canary_config(
    candidate_id: str,
    title_ko: str,
    stage: str,
    track: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, ActionBlock | None]:
    slug = _safe_slug(candidate_id)
    portfolio_path = str(track.get("portfolio_path") or "").strip()
    db_path = str(track.get("db_path") or f"data/promotion_canary_{slug}.db").strip()
    halt_path = str(track.get("halt_path") or f"data/promotion_canary_{slug}.halt.flag").strip()
    bands_toml = str(track.get("bands_toml") or DEFAULT_CANARY_BANDS_TOML).strip()

    checks = (
        ("portfolio_path", portfolio_path, _validate_portfolio_path),
        ("db_path", db_path, _validate_promotion_canary_db_path),
        ("halt_path", halt_path, _validate_promotion_canary_halt_path),
        ("bands_toml", bands_toml, _validate_bands_path),
    )
    for field, value, validator in checks:
        ok, reason_ko = validator(value)
        if not ok:
            return None, _block(candidate_id, title_ko, stage, field, value, reason_ko)
    return (
        {
            "portfolio_path": portfolio_path,
            "db_path": db_path,
            "halt_path": halt_path,
            "bands_toml": bands_toml,
        },
        None,
    )


def _validate_track_key(value: str) -> tuple[bool, str]:
    if _SAFE_KEY_RE.fullmatch(value):
        return True, ""
    return False, "track_key는 소문자·숫자·하이픈·밑줄 3~64자여야 한다."


def _validate_portfolio_path(value: str) -> tuple[bool, str]:
    if _safe_relative(value) and value.startswith("deploy/") and value.endswith(".toml"):
        return True, ""
    return False, "portfolio_path는 repo 상대경로 deploy/*.toml 만 허용한다."


def _validate_promotion_db_path(value: str) -> tuple[bool, str]:
    if (
        _safe_relative(value)
        and value.startswith("data/promotion_")
        and value.endswith(".db")
    ):
        return True, ""
    return False, "db_path는 data/promotion_*.db 만 허용한다."


def _validate_promotion_canary_db_path(value: str) -> tuple[bool, str]:
    if (
        _safe_relative(value)
        and value.startswith("data/promotion_canary_")
        and value.endswith(".db")
    ):
        return True, ""
    return False, "canary db_path는 data/promotion_canary_*.db 만 허용한다."


def _validate_promotion_halt_path(value: str) -> tuple[bool, str]:
    if (
        _safe_relative(value)
        and value.startswith("data/promotion_")
        and value.endswith(".halt.flag")
        and value != "data/halt.flag"
    ):
        return True, ""
    return False, "halt_path는 data/promotion_*.halt.flag 만 허용한다."


def _validate_promotion_canary_halt_path(value: str) -> tuple[bool, str]:
    if (
        _safe_relative(value)
        and value.startswith("data/promotion_canary_")
        and value.endswith(".halt.flag")
    ):
        return True, ""
    return False, "canary halt_path는 data/promotion_canary_*.halt.flag 만 허용한다."


def _validate_bands_path(value: str) -> tuple[bool, str]:
    if _safe_relative(value) and value.startswith("config/") and value.endswith(".toml"):
        return True, ""
    return False, "bands_toml은 config/*.toml 만 허용한다."


def _safe_relative(value: str) -> bool:
    if not value or value.startswith("/") or "\\" in value:
        return False
    parts = Path(value).parts
    return ".." not in parts


def _normalize_forward_registry(doc: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(doc, Mapping):
        return {"schema_version": SCHEMA_VERSION, "tracks": []}
    tracks = doc.get("tracks")
    return {
        "schema_version": str(doc.get("schema_version") or SCHEMA_VERSION),
        "tracks": [dict(row) for row in tracks if isinstance(row, Mapping)]
        if isinstance(tracks, list)
        else [],
    }


def _normalize_canary_submissions(doc: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(doc, Mapping):
        return {"schema_version": SCHEMA_VERSION, "submissions": []}
    submissions = doc.get("submissions")
    return {
        "schema_version": str(doc.get("schema_version") or SCHEMA_VERSION),
        "submissions": [dict(row) for row in submissions if isinstance(row, Mapping)]
        if isinstance(submissions, list)
        else [],
    }


def _clone_state(state: Mapping[str, Any], list_key: str) -> dict[str, Any]:
    rows = state.get(list_key)
    return {
        "schema_version": str(state.get("schema_version") or SCHEMA_VERSION),
        list_key: [dict(row) for row in rows if isinstance(row, Mapping)]
        if isinstance(rows, list)
        else [],
    }


def _find_existing_track(
    tracks: Sequence[Any],
    candidate_id: str,
    track_key: str,
) -> Mapping[str, Any] | None:
    for row in tracks:
        if not isinstance(row, Mapping):
            continue
        if row.get("candidate_id") == candidate_id or row.get("track_key") == track_key:
            return row
    return None


def _find_existing_submission(
    submissions: Sequence[Any],
    candidate_id: str,
) -> Mapping[str, Any] | None:
    for row in submissions:
        if isinstance(row, Mapping) and row.get("candidate_id") == candidate_id:
            return row
    return None


def _assessments(summary: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(summary, Mapping):
        return ()
    raw = summary.get("assessments")
    if not isinstance(raw, list):
        return ()
    return tuple(row for row in raw if isinstance(row, Mapping))


def _candidate(assessment: Mapping[str, Any]) -> Mapping[str, Any]:
    candidate = assessment.get("candidate")
    return candidate if isinstance(candidate, Mapping) else assessment


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _block(
    candidate_id: str,
    title_ko: str,
    stage: str,
    field: str,
    value: object,
    reason_ko: str,
) -> ActionBlock:
    return ActionBlock(
        candidate_id=candidate_id,
        title_ko=title_ko,
        stage=stage,
        field=field,
        reason=f"invalid {field}: {value}",
        reason_ko=reason_ko,
    )


def _redacted_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(mask_sensitive_values(json.dumps(dict(payload), ensure_ascii=False)))


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-_")
    if len(slug) < 3:
        slug = f"candidate-{slug or 'unknown'}"
    return slug[:64]


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "ACTION_CANARY_SUBMISSION",
    "ACTION_EXISTING_GATE_REPORT",
    "ACTION_FORWARD_REGISTRATION",
    "OVERALL_DEGRADED",
    "OVERALL_OK",
    "SCHEMA_VERSION",
    "STATUS_ALREADY_REGISTERED",
    "STATUS_ALREADY_SUBMITTED",
    "STATUS_REGISTERED",
    "STATUS_REPORTED",
    "STATUS_SUBMITTED",
    "ActionBlock",
    "PromotionAction",
    "PromotionActionRun",
    "build_promotion_actions",
    "write_promotion_action_artifacts",
]
