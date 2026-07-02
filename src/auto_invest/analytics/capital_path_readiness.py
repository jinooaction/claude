"""스펙 076 — 자본 경로 준비도 루프.

여러 자동 루프의 사이드카를 읽어 "지금 돈을 더 벌기 위한 자본 경로가 어느 상태인가"와
"다음 안전 행동이 무엇인가"를 한 장으로 합친다.

안전 경계: 읽기 전용·순수·결정론. 브로커, 주문, 계좌, 라이브 설정, whitelist/caps 를
변경하지 않는다. 실제 자본 투입 여부는 기존 money-path/edge-autoarm/reassign/live gate가
계속 결정한다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"

STATE_UNKNOWN = "UNKNOWN"
STATE_ACCUMULATING_EDGE = "ACCUMULATING_EDGE"
STATE_EDGE_READY = "EDGE_READY"
STATE_CAPITAL_ARMABLE = "CAPITAL_ARMABLE"
STATE_PREVIEW_ONLY = "PREVIEW_ONLY"
STATE_LIVE_BLOCKED = "LIVE_BLOCKED"

LIVE_STATUS_UNKNOWN = "UNKNOWN"
LIVE_STATUS_PREVIEW = "PREVIEW_ONLY"
LIVE_STATUS_ARMED = "REAL_ORDER_PATH_ARMED"
LIVE_STATUS_BLOCKED = "BLOCKED"

STAGE_UNKNOWN = "UNKNOWN"
STAGE_ACCUMULATING = "ACCUMULATING_EDGE"
STAGE_NO_EDGE_YET = "NO_EDGE_YET"
STAGE_EDGE_CONFIRMED = "EDGE_CONFIRMED_PENDING_DEPLOY"
STAGE_DEPLOYED = "DEPLOYED"
STAGE_DEFENDED = "DEFENDED"
STAGE_BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_PRESENT = "present"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

OBS_INFO = "info"
OBS_WARNING = "warning"
OBS_CRITICAL = "critical"

_CAPITAL_RELATED_DOMAINS = {
    "live_readiness": 0,
    "execution_quality": 1,
    "data_quality": 2,
    "data_collection": 3,
    "analysis": 4,
    "portfolio_design": 5,
}
_REJECTED_WORDS = {"rejected", "discard", "discarded", "failed", "blocked"}
_RELEASED_WORDS = {"released", "complete", "completed", "done"}
_LIVENESS_OK_STATUSES = {"OK", "PASS", "PRESENT", "PENDING", "HEALTHY"}
_LIVENESS_CRITICAL_STATUSES = {"STALE", "MISSING", "CRITICAL"}


@dataclass(frozen=True)
class ReadinessEvidenceSurface:
    """자본 경로 판정에 쓰인 입력 표면 한 개."""

    key: str
    source_ref: str
    present: bool
    parse_status: str
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source_ref": self.source_ref,
            "present": self.present,
            "parse_status": self.parse_status,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class ReadinessCandidate:
    """준비도 루프가 다음 행동 후보로 끌어올리거나 억제한 후보."""

    candidate_id: str
    domain_key: str
    status: str
    title_ko: str
    reason_ko: str
    source: str
    score: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "domain_key": self.domain_key,
            "status": self.status,
            "title_ko": self.title_ko,
            "reason_ko": self.reason_ko,
            "source": self.source,
            "score": self.score,
        }


@dataclass(frozen=True)
class ReadinessObservabilityIssue:
    """후보 실패와 분리해 보여줄 증거·관측 품질 이슈."""

    issue_id: str
    issue_type: str
    severity: str
    source_key: str
    status: str
    summary_ko: str
    next_action_ko: str
    affected_candidate_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "source_key": self.source_key,
            "status": self.status,
            "summary_ko": self.summary_ko,
            "next_action_ko": self.next_action_ko,
            "affected_candidate_id": self.affected_candidate_id,
        }


@dataclass(frozen=True)
class CapitalPathReadinessReport:
    """자본 경로 준비도 종합 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    readiness_state: str
    live_money_status: str
    capital_ladder_stage: str
    blocking_gate: str
    next_action_ko: str
    required_existing_gates: list[str]
    priority_candidates: list[ReadinessCandidate]
    suppressed_candidates: list[ReadinessCandidate]
    observability_issues: list[ReadinessObservabilityIssue]
    evidence_surfaces: list[ReadinessEvidenceSurface]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "readiness_state": self.readiness_state,
            "live_money_status": self.live_money_status,
            "capital_ladder_stage": self.capital_ladder_stage,
            "blocking_gate": self.blocking_gate,
            "next_action_ko": self.next_action_ko,
            "required_existing_gates": self.required_existing_gates,
            "priority_candidates": [c.to_dict() for c in self.priority_candidates],
            "suppressed_candidates": [c.to_dict() for c in self.suppressed_candidates],
            "observability_issues": [issue.to_dict() for issue in self.observability_issues],
            "evidence_surfaces": [s.to_dict() for s in self.evidence_surfaces],
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 자본 경로 준비도 루프 (as of {self.timestamp_utc})",
            "",
            "읽기 전용 보고입니다. 주문, 자본 배분, 라이브 설정 변경은 하지 않습니다.",
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| readiness_state | {self.readiness_state} |",
            f"| live_money_status | {self.live_money_status} |",
            f"| capital_ladder_stage | {self.capital_ladder_stage} |",
            f"| blocking_gate | {self.blocking_gate} |",
            f"| next_action_ko | {self.next_action_ko} |",
            f"| required_existing_gates | {', '.join(self.required_existing_gates)} |",
            "",
            "## 우선 후보",
            "",
        ]
        if self.priority_candidates:
            lines += [
                "| 후보 | 영역 | 상태 | 점수 | 이유 |",
                "|------|------|------|-----:|------|",
            ]
            for candidate in self.priority_candidates:
                score = "" if candidate.score is None else str(candidate.score)
                lines.append(
                    f"| {candidate.candidate_id} | {candidate.domain_key} | "
                    f"{candidate.status} | {score} | {candidate.reason_ko} |"
                )
        else:
            lines.append("- 현재 자본 경로 준비도를 높이는 우선 후보 없음.")
        lines += ["", "## 억제 후보", ""]
        if self.suppressed_candidates:
            lines += [
                "| 후보 | 영역 | 상태 | 출처 | 이유 |",
                "|------|------|------|------|------|",
            ]
            for candidate in self.suppressed_candidates:
                lines.append(
                    f"| {candidate.candidate_id} | {candidate.domain_key} | "
                    f"{candidate.status} | {candidate.source} | {candidate.reason_ko} |"
                )
        else:
            lines.append("- 억제할 실패 후보 없음.")
        lines += [
            "",
            "## 관측 이슈",
            "",
        ]
        if self.observability_issues:
            lines += [
                "| 이슈 | 심각도 | 출처 | 상태 | 요약 | 다음 조치 |",
                "|------|--------|------|------|------|-----------|",
            ]
            for issue in self.observability_issues:
                lines.append(
                    f"| {issue.issue_id} | {issue.severity} | {issue.source_key} | "
                    f"{issue.status} | {issue.summary_ko} | {issue.next_action_ko} |"
                )
        else:
            lines.append("- 후보 실패와 분리해 볼 증거 관측 이슈 없음.")
        lines += [
            "",
            "## 입력 증거",
            "",
            "| 증거 | 존재 | 파싱 | 요약 |",
            "|------|:----:|------|------|",
        ]
        for surface in self.evidence_surfaces:
            present = "yes" if surface.present else "no"
            lines.append(
                f"| {surface.key} | {present} | {surface.parse_status} | "
                f"{surface.summary_ko} |"
            )
        lines += [
            "",
            "## 안전 경계",
            "",
            "- 이 루프는 기존 sidecar를 읽고 자기 sidecar만 발행합니다.",
            "- 실제 주문, 실거래 전환, 자본 배분, whitelist/caps/live 설정 변경을 하지 않습니다.",
            "- 자본 투입 판단은 기존 `money-path`, `edge-autoarm`, `reassign` 게이트를 유지합니다.",
        ]
        return "\n".join(lines)


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _json_value(text: str | None) -> Any | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_json_after_header(text: str | None, header: str) -> dict[str, Any] | None:
    """마크다운에서 `header` 다음의 첫 fenced JSON dict를 꺼낸다."""

    if not text:
        return None
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if header in line:
            start = i
            break
    if start is None:
        return None
    in_block = False
    buf: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```"):
                in_block = True
            continue
        if stripped.startswith("```"):
            break
        buf.append(line)
    if not buf:
        return None
    value = _json_value("\n".join(buf))
    return value if isinstance(value, dict) else None


def _json_dict(text: str | None, *headers: str) -> dict[str, Any] | None:
    value = _json_value(text)
    if isinstance(value, dict):
        return value
    for header in headers:
        parsed = extract_json_after_header(text, header)
        if parsed is not None:
            return parsed
    return None


def _json_list_or_dict(text: str | None, *headers: str) -> list[Any] | dict[str, Any] | None:
    value = _json_value(text)
    if isinstance(value, (list, dict)):
        return value
    parsed = _json_dict(text, *headers)
    return parsed


def _is_rejected(value: object) -> bool:
    return str(value or "").strip().lower() in _REJECTED_WORDS


def _is_released(value: object) -> bool:
    return str(value or "").strip().lower() in _RELEASED_WORDS


def _items(value: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []
    for key in keys:
        raw = value.get(key)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    return []


def _candidate_id(item: Mapping[str, Any]) -> str:
    return str(
        item.get("candidate_id")
        or item.get("id")
        or item.get("candidate")
        or item.get("candidate_key")
        or ""
    )


def _candidate_domain(item: Mapping[str, Any]) -> str:
    return str(item.get("domain_key") or item.get("domain") or item.get("category") or "")


def _candidate_status(item: Mapping[str, Any]) -> str:
    return str(item.get("status") or item.get("decision") or item.get("action") or "")


def _candidate_score(item: Mapping[str, Any]) -> int | None:
    raw = item.get("score") or item.get("priority_score") or item.get("composite_score")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _candidate_title(item: Mapping[str, Any]) -> str:
    return str(
        item.get("title_ko")
        or item.get("title")
        or item.get("name")
        or item.get("summary_ko")
        or "제목 없음"
    )


def _candidate_reason(item: Mapping[str, Any], fallback: str) -> str:
    return str(
        item.get("reason_ko")
        or item.get("next_action_ko")
        or item.get("reason")
        or item.get("summary_ko")
        or fallback
    )


def _candidate_from_item(
    item: Mapping[str, Any],
    source: str,
    fallback_reason: str,
) -> ReadinessCandidate | None:
    candidate_id = _candidate_id(item)
    if not candidate_id:
        return None
    return ReadinessCandidate(
        candidate_id=candidate_id,
        domain_key=_candidate_domain(item),
        status=_candidate_status(item),
        title_ko=_candidate_title(item),
        reason_ko=_candidate_reason(item, fallback_reason),
        source=source,
        score=_candidate_score(item),
    )


def _ledger_rejections(ledger_value: Any) -> dict[str, ReadinessCandidate]:
    rejected: dict[str, ReadinessCandidate] = {}
    for item in _items(ledger_value, ("entries", "ledger", "decisions", "records")):
        status = item.get("status") or item.get("decision") or item.get("outcome")
        if not _is_rejected(status):
            continue
        candidate = _candidate_from_item(
            item,
            source="evolution-ledger",
            fallback_reason="learning ledger가 실패 후보로 억제했다.",
        )
        if candidate is not None:
            rejected[candidate.candidate_id] = candidate
    return rejected


def _released_candidates(released_value: Any) -> dict[str, ReadinessCandidate]:
    released: dict[str, ReadinessCandidate] = {}
    for item in _items(released_value, ("released_work", "entries", "items", "candidates")):
        status = item.get("status") or item.get("decision") or item.get("outcome")
        if not _is_released(status):
            continue
        candidate_id = _candidate_id(item)
        if not candidate_id:
            continue
        released[candidate_id] = ReadinessCandidate(
            candidate_id=candidate_id,
            domain_key=_candidate_domain(item),
            status="released",
            title_ko=_candidate_title(item),
            reason_ko=_candidate_reason(
                item,
                "released-work가 완료 후보로 기록했다.",
            ),
            source="released-work",
            score=None,
        )
    return released


def _promotion_candidates(
    promotion_value: Any,
) -> tuple[list[ReadinessCandidate], list[ReadinessCandidate]]:
    priority: list[ReadinessCandidate] = []
    suppressed: list[ReadinessCandidate] = []
    for item in _items(
        promotion_value,
        ("candidates", "actions", "promotion_actions", "summary", "results"),
    ):
        candidate = _candidate_from_item(
            item,
            source="autonomous-promotion",
            fallback_reason="승격 루프가 후보 검증 패키지로 분류했다.",
        )
        if candidate is None:
            continue
        if _is_rejected(candidate.status):
            suppressed.append(candidate)
        elif candidate.domain_key in _CAPITAL_RELATED_DOMAINS:
            priority.append(candidate)
    return priority, suppressed


def _candidate_routing(
    backlog_value: Any,
    ledger_value: Any,
    promotion_value: Any,
    released_value: Any,
) -> tuple[
    list[ReadinessCandidate],
    list[ReadinessCandidate],
    list[ReadinessObservabilityIssue],
]:
    ledger_rejected = _ledger_rejections(ledger_value)
    released = _released_candidates(released_value)
    priority: list[ReadinessCandidate] = []
    suppressed: dict[str, ReadinessCandidate] = dict(ledger_rejected)
    observability_issues: dict[str, ReadinessObservabilityIssue] = {}

    def suppress_released_echo(candidate: ReadinessCandidate) -> bool:
        released_candidate = released.get(candidate.candidate_id)
        if released_candidate is None:
            return False
        suppressed.setdefault(
            candidate.candidate_id,
            ReadinessCandidate(
                candidate_id=candidate.candidate_id,
                domain_key=candidate.domain_key or released_candidate.domain_key,
                status="released",
                title_ko=candidate.title_ko or released_candidate.title_ko,
                reason_ko=(
                    "released-work가 완료로 기록했지만 upstream 후보 목록에 남아 있어 "
                    "작업 후보가 아니라 관측 잔향으로 분리했다."
                ),
                source=f"{candidate.source}+released-work",
                score=candidate.score,
            ),
        )
        issue_id = f"released-candidate-echo:{candidate.candidate_id}"
        observability_issues.setdefault(
            issue_id,
            ReadinessObservabilityIssue(
                issue_id=issue_id,
                issue_type="released_candidate_echo",
                severity=OBS_INFO,
                source_key="released-work",
                status="RELEASED",
                summary_ko=(
                    f"이미 출시된 후보가 {candidate.source} 후보 목록에 남아 있습니다."
                ),
                next_action_ko=(
                    "released-work 장부와 upstream 후보 sidecar 생산 순서를 확인합니다."
                ),
                affected_candidate_id=candidate.candidate_id,
            ),
        )
        return True

    promotion_priority, promotion_suppressed = _promotion_candidates(promotion_value)
    for candidate in promotion_suppressed:
        suppress_released_echo(candidate)
        suppressed.setdefault(candidate.candidate_id, candidate)
    for candidate in promotion_priority:
        if suppress_released_echo(candidate):
            continue
        if candidate.candidate_id not in suppressed:
            priority.append(candidate)

    for item in _items(backlog_value, ("candidates", "backlog", "items")):
        candidate = _candidate_from_item(
            item,
            source="evolution-backlog",
            fallback_reason="자본 경로 준비도 개선 후보로 유지한다.",
        )
        if candidate is None:
            continue
        if suppress_released_echo(candidate):
            continue
        if _is_rejected(candidate.status):
            suppressed.setdefault(candidate.candidate_id, candidate)
            continue
        if candidate.candidate_id in suppressed:
            continue
        if candidate.domain_key not in _CAPITAL_RELATED_DOMAINS:
            continue
        priority.append(candidate)

    priority_by_id: dict[str, ReadinessCandidate] = {}
    for candidate in priority:
        priority_by_id.setdefault(candidate.candidate_id, candidate)

    ordered = sorted(
        priority_by_id.values(),
        key=lambda c: (
            _CAPITAL_RELATED_DOMAINS.get(c.domain_key, 99),
            -(c.score or 0),
            c.candidate_id,
        ),
    )
    return ordered[:5], list(suppressed.values()), list(observability_issues.values())


def _liveness_severity(status: str, critical: bool) -> str:
    if critical and status in _LIVENESS_CRITICAL_STATUSES:
        return OBS_CRITICAL
    return OBS_WARNING


def _pipeline_liveness_issues(
    pipeline_value: Any,
    *,
    raw_present: bool,
) -> list[ReadinessObservabilityIssue]:
    if not raw_present:
        return [
            ReadinessObservabilityIssue(
                issue_id="pipeline-liveness:missing-input",
                issue_type="pipeline_liveness",
                severity=OBS_WARNING,
                source_key="pipeline-liveness",
                status="MISSING",
                summary_ko=(
                    "pipeline-liveness sidecar를 읽지 못해 증거 신선도를 "
                    "확인할 수 없습니다."
                ),
                next_action_ko="pipeline-liveness workflow와 sidecar 발행 상태를 확인합니다.",
            )
        ]
    if not isinstance(pipeline_value, dict):
        return [
            ReadinessObservabilityIssue(
                issue_id="pipeline-liveness:malformed-input",
                issue_type="malformed_evidence",
                severity=OBS_WARNING,
                source_key="pipeline-liveness",
                status="MALFORMED",
                summary_ko="pipeline-liveness sidecar는 있지만 구조화 JSON을 읽지 못했습니다.",
                next_action_ko="pipeline-liveness LAST_RUN.md의 결정 JSON 형식을 확인합니다.",
            )
        ]

    issues: list[ReadinessObservabilityIssue] = []
    for check in _items(pipeline_value, ("checks",)):
        key = str(check.get("key") or check.get("name") or "unknown")
        status = str(check.get("status") or "UNKNOWN").upper()
        if status in _LIVENESS_OK_STATUSES:
            continue
        critical = bool(check.get("critical"))
        detail = str(check.get("detail") or "").strip()
        summary = f"{key} sidecar 상태가 {status}입니다."
        if detail:
            summary = f"{summary} {detail}"
        issues.append(
            ReadinessObservabilityIssue(
                issue_id=f"pipeline-liveness:{key}",
                issue_type="pipeline_liveness",
                severity=_liveness_severity(status, critical),
                source_key=key,
                status=status,
                summary_ko=summary,
                next_action_ko=(
                    "해당 sidecar의 마지막 workflow 실행과 발행 시각을 확인합니다."
                ),
            )
        )
    return issues


def _gate_list(money: Mapping[str, Any] | None) -> list[str]:
    gates = ["money-path", "edge-autoarm", "reassign"]
    if not money:
        return gates
    live_state = money.get("live_money_state")
    if isinstance(live_state, dict):
        required = live_state.get("required_gates")
        if isinstance(required, list):
            gates.extend(str(item) for item in required)
    for key in ("required_existing_gates", "required_gates"):
        raw = money.get(key)
        if isinstance(raw, list):
            gates.extend(str(item) for item in raw)
    deduped: list[str] = []
    for gate in gates:
        if gate and gate not in deduped:
            deduped.append(gate)
    return deduped


def _blocking_gate(money: Mapping[str, Any] | None, reassign: Mapping[str, Any] | None) -> str:
    if money:
        for key in ("blocking_gate", "blocker", "reason"):
            value = money.get(key)
            if value:
                return str(value)
        gates = money.get("gates")
        if isinstance(gates, list):
            for gate in gates:
                if not isinstance(gate, dict):
                    continue
                status = str(gate.get("status") or "").upper()
                if status in {"FAIL", "PENDING", "BLOCKED"}:
                    name = gate.get("name") or gate.get("gate")
                    reason = gate.get("reason") or gate.get("detail")
                    if name and reason:
                        return f"{name}: {reason}"
                    if name:
                        return str(name)
    if reassign:
        for key in ("blocking_gate", "reason", "action_reason"):
            value = reassign.get(key)
            if value:
                return str(value)
    return "money-path evidence missing"


def _live_status(money: Mapping[str, Any] | None) -> str:
    if not money:
        return LIVE_STATUS_UNKNOWN
    live_state = money.get("live_money_state")
    if isinstance(live_state, dict):
        status = live_state.get("status")
        if status:
            return str(status)
    return str(money.get("live_money_status") or LIVE_STATUS_UNKNOWN)


def _capital_stage(money: Mapping[str, Any] | None) -> str:
    if not money:
        return STAGE_UNKNOWN
    return str(money.get("stage") or money.get("capital_ladder_stage") or STAGE_UNKNOWN)


def _can_submit_orders(money: Mapping[str, Any] | None) -> bool:
    if not money:
        return False
    live_state = money.get("live_money_state")
    if isinstance(live_state, dict):
        return bool(live_state.get("can_submit_real_orders"))
    return bool(money.get("can_submit_real_orders"))


def _classify(money: Mapping[str, Any] | None) -> str:
    if not money:
        return STATE_UNKNOWN
    status = _live_status(money)
    stage = _capital_stage(money)
    if status == LIVE_STATUS_BLOCKED or stage == STAGE_BLOCKED:
        return STATE_LIVE_BLOCKED
    if _can_submit_orders(money) or status == LIVE_STATUS_ARMED:
        return STATE_CAPITAL_ARMABLE
    if stage == STAGE_DEPLOYED:
        return STATE_CAPITAL_ARMABLE
    if stage == STAGE_EDGE_CONFIRMED:
        return STATE_EDGE_READY
    if stage in {STAGE_ACCUMULATING, STAGE_NO_EDGE_YET, STAGE_DEFENDED}:
        return STATE_ACCUMULATING_EDGE
    if status == LIVE_STATUS_PREVIEW:
        return STATE_PREVIEW_ONLY
    return STATE_UNKNOWN


def _next_action(state: str, money: Mapping[str, Any] | None, priority_count: int) -> str:
    if money and money.get("next_action"):
        return str(money["next_action"])
    if state == STATE_UNKNOWN:
        return "money-path sidecar를 먼저 갱신하고 기존 자본 사다리 게이트를 다시 확인한다."
    if state == STATE_LIVE_BLOCKED:
        return "차단 원인을 기존 money-path/edge-autoarm/reassign 게이트에서 해결한다."
    if state == STATE_EDGE_READY:
        return "기존 자본 사다리와 reassign 게이트로 승격 가능성을 검증한다."
    if state == STATE_CAPITAL_ARMABLE:
        return "기존 라이브 안전 게이트를 유지한 채 운영자 승인 범위 안에서만 진행한다."
    if priority_count:
        return "우선 후보를 검증 패키지로 연결하고 기존 전진 관측과 자본 사다리를 계속 누적한다."
    return "기존 전진 관측과 자본 사다리 게이트를 계속 사용한다."


def _surface(
    key: str,
    source_ref: str,
    raw: str | None,
    parsed: Any,
    summary_ok: str,
    parse_required: bool,
) -> ReadinessEvidenceSurface:
    if raw is None:
        return ReadinessEvidenceSurface(
            key=key,
            source_ref=source_ref,
            present=False,
            parse_status=PARSE_MISSING,
            summary_ko="sidecar 없음",
        )
    if parsed is not None:
        return ReadinessEvidenceSurface(
            key=key,
            source_ref=source_ref,
            present=True,
            parse_status=PARSE_OK,
            summary_ko=summary_ok,
        )
    return ReadinessEvidenceSurface(
        key=key,
        source_ref=source_ref,
        present=True,
        parse_status=PARSE_MALFORMED if parse_required else PARSE_PRESENT,
        summary_ko="원문 존재, 구조화 JSON 없음" if parse_required else summary_ok,
    )


def build_capital_path_readiness(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> CapitalPathReadinessReport:
    """수집된 sidecar 원문으로 자본 경로 준비도 보고를 만든다."""

    now = _as_utc(now)
    money = _json_dict(evidence_texts.get("money-path"), "결정 JSON", "money-path")
    reassign = _json_dict(evidence_texts.get("reassign"), "5중 게이트 결정 JSON", "결정 JSON")
    promotion = _json_list_or_dict(evidence_texts.get("autonomous-promotion"), "결정 JSON")
    backlog = _json_list_or_dict(evidence_texts.get("evolution-backlog"), "결정 JSON")
    ledger = _json_list_or_dict(evidence_texts.get("evolution-ledger"), "결정 JSON")
    released_work = _json_dict(evidence_texts.get("released-work"), "결정 JSON")
    pipeline_liveness = _json_dict(evidence_texts.get("pipeline-liveness"), "결정 JSON")

    priority_candidates, suppressed_candidates, routing_issues = _candidate_routing(
        backlog,
        ledger,
        promotion,
        released_work,
    )
    observability_issues = [
        *routing_issues,
        *_pipeline_liveness_issues(
            pipeline_liveness,
            raw_present=evidence_texts.get("pipeline-liveness") is not None,
        ),
    ]
    readiness_state = _classify(money)
    live_money_status = _live_status(money)
    capital_ladder_stage = _capital_stage(money)
    blocking_gate = _blocking_gate(money, reassign)
    next_action = _next_action(readiness_state, money, len(priority_candidates))
    liveness_overall = (
        str(pipeline_liveness.get("overall", "UNKNOWN"))
        if isinstance(pipeline_liveness, dict)
        else "UNKNOWN"
    )

    evidence_surfaces = [
        _surface(
            "money-path",
            "automation/money-path-last-run:LAST_RUN.md",
            evidence_texts.get("money-path"),
            money,
            f"stage={capital_ladder_stage}, live={live_money_status}",
            parse_required=True,
        ),
        _surface(
            "edge-autoarm",
            "automation/edge-autoarm-last-run:LAST_RUN.md",
            evidence_texts.get("edge-autoarm"),
            _json_dict(evidence_texts.get("edge-autoarm"), "결정 JSON"),
            "자본 사다리 원천 sidecar 존재",
            parse_required=False,
        ),
        _surface(
            "reassign",
            "automation/reassign-last-run:LAST_RUN.md",
            evidence_texts.get("reassign"),
            reassign,
            "reassign 판정 JSON 확인",
            parse_required=False,
        ),
        _surface(
            "rebalance-paper-forward",
            "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
            evidence_texts.get("rebalance-paper-forward"),
            _json_dict(evidence_texts.get("rebalance-paper-forward"), "결정 JSON"),
            "전진 페이퍼 관측 sidecar 존재",
            parse_required=False,
        ),
        _surface(
            "kis-smoke",
            "automation/kis-smoke-last-run:LAST_RUN.md",
            evidence_texts.get("kis-smoke"),
            _json_dict(evidence_texts.get("kis-smoke"), "결정 JSON"),
            "KIS smoke sidecar 존재",
            parse_required=False,
        ),
        _surface(
            "autonomous-promotion",
            "automation/autonomous-promotion-last-run:promotion_summary.json",
            evidence_texts.get("autonomous-promotion"),
            promotion,
            "승격 요약 JSON 확인",
            parse_required=True,
        ),
        _surface(
            "evolution-backlog",
            "automation/autonomous-evolution-last-run:candidate_backlog.json",
            evidence_texts.get("evolution-backlog"),
            backlog,
            f"후보 {len(_items(backlog, ('candidates', 'backlog', 'items')))}개 확인",
            parse_required=True,
        ),
        _surface(
            "evolution-ledger",
            "automation/autonomous-evolution-last-run:learning_ledger.json",
            evidence_texts.get("evolution-ledger"),
            ledger,
            f"억제 후보 {len(_ledger_rejections(ledger))}개 확인",
            parse_required=True,
        ),
        _surface(
            "released-work",
            "automation/released-work-last-run:released_work.json",
            evidence_texts.get("released-work"),
            released_work,
            f"완료 후보 {len(_released_candidates(released_work))}개 확인",
            parse_required=True,
        ),
        _surface(
            "pipeline-liveness",
            "automation/pipeline-liveness-last-run:LAST_RUN.md",
            evidence_texts.get("pipeline-liveness"),
            pipeline_liveness,
            f"overall={liveness_overall}",
            parse_required=True,
        ),
    ]

    return CapitalPathReadinessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        readiness_state=readiness_state,
        live_money_status=live_money_status,
        capital_ladder_stage=capital_ladder_stage,
        blocking_gate=blocking_gate,
        next_action_ko=next_action,
        required_existing_gates=_gate_list(money),
        priority_candidates=priority_candidates,
        suppressed_candidates=suppressed_candidates,
        observability_issues=observability_issues,
        evidence_surfaces=evidence_surfaces,
    )


__all__ = [
    "LIVE_STATUS_ARMED",
    "LIVE_STATUS_BLOCKED",
    "LIVE_STATUS_PREVIEW",
    "LIVE_STATUS_UNKNOWN",
    "PARSE_MALFORMED",
    "PARSE_MISSING",
    "PARSE_OK",
    "PARSE_PRESENT",
    "OBS_CRITICAL",
    "OBS_INFO",
    "OBS_WARNING",
    "SCHEMA_VERSION",
    "STATE_ACCUMULATING_EDGE",
    "STATE_CAPITAL_ARMABLE",
    "STATE_EDGE_READY",
    "STATE_LIVE_BLOCKED",
    "STATE_PREVIEW_ONLY",
    "STATE_UNKNOWN",
    "CapitalPathReadinessReport",
    "ReadinessCandidate",
    "ReadinessEvidenceSurface",
    "ReadinessObservabilityIssue",
    "build_capital_path_readiness",
    "extract_json_after_header",
]
