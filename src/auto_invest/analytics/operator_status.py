"""스펙 080 — 운영자 대시보드와 모바일 알림 상태 보고.

읽기 전용 소비자 계층이다. 이미 발행된 automation sidecar를 요약해 운영자가
모바일에서 볼 상태와, 개입 필요 시 보낼 짧은 알림 본문을 만든다. 주문, 자본,
broker, live 설정, 서버 SSH에는 접근하지 않는다.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"

PARSE_OK = "ok"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

SEVERITY_INFO = "info"
SEVERITY_ATTENTION = "attention"
SEVERITY_ACTION = "action"
SEVERITY_CRITICAL = "critical"

STATUS_OK = "OK"
STATUS_ATTENTION = "ATTENTION"
STATUS_ACTION_REQUIRED = "ACTION_REQUIRED"
STATUS_CRITICAL = "CRITICAL"

ALERT_SILENT_OK = "SILENT_OK"
ALERT_ATTENTION_ONLY = "ATTENTION_ONLY"
ALERT_ACTION_REQUIRED = "ACTION_REQUIRED"
ALERT_CRITICAL = "CRITICAL"

SEND_NOT_ATTEMPTED = "NOT_ATTEMPTED"
SEND_SKIPPED_MISSING_SECRETS = "SKIPPED_MISSING_SECRETS"
SEND_SENT = "SENT"
SEND_FAILED = "FAILED"

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no server SSH",
    "no secret persistence",
    "operator visibility only",
)

SOURCE_REFS: dict[str, str] = {
    "pipeline-liveness": "automation/pipeline-liveness-last-run:LAST_RUN.md",
    "money-path": "automation/money-path-last-run:LAST_RUN.md",
    "capital-path-readiness": (
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
    ),
    "money-gate-alignment": "automation/money-gate-alignment-last-run:money_gate_alignment.json",
    "autonomous-work-execution": (
        "automation/autonomous-work-execution-last-run:autonomous_work_execution.json"
    ),
    "released-work": "automation/released-work-last-run:released_work.json",
}

CONSUMED_SIDECARS: tuple[tuple[str, str, str], ...] = (
    ("pipeline-liveness", "automation/pipeline-liveness-last-run", "LAST_RUN.md"),
    ("money-path", "automation/money-path-last-run", "LAST_RUN.md"),
    (
        "capital-path-readiness",
        "automation/capital-path-readiness-last-run",
        "capital_path_readiness.json",
    ),
    (
        "money-gate-alignment",
        "automation/money-gate-alignment-last-run",
        "money_gate_alignment.json",
    ),
    (
        "autonomous-work-execution",
        "automation/autonomous-work-execution-last-run",
        "autonomous_work_execution.json",
    ),
    ("released-work", "automation/released-work-last-run", "released_work.json"),
)

_FENCED_JSON_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class OperatorSurface:
    key: str
    source_ref: str
    present: bool
    parse_status: str
    status: str
    severity: str
    summary_ko: str
    next_action_ko: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source_ref": self.source_ref,
            "present": self.present,
            "parse_status": self.parse_status,
            "status": self.status,
            "severity": self.severity,
            "summary_ko": self.summary_ko,
            "next_action_ko": self.next_action_ko,
        }


@dataclass(frozen=True)
class MobileAlertDecision:
    alert_level: str
    should_send: bool
    reason_ko: str
    message_ko: str
    send_status: str = SEND_NOT_ATTEMPTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_level": self.alert_level,
            "should_send": self.should_send,
            "reason_ko": self.reason_ko,
            "message_ko": self.message_ko,
            "send_status": self.send_status,
        }


@dataclass(frozen=True)
class DashboardSection:
    key: str
    title_ko: str
    status: str
    body_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title_ko": self.title_ko,
            "status": self.status,
            "body_ko": self.body_ko,
        }


@dataclass(frozen=True)
class OperatorStatusReport:
    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    headline_ko: str
    next_action_ko: str
    dashboard_url: str | None
    alert_decision: MobileAlertDecision
    surfaces: tuple[OperatorSurface, ...]
    dashboard_sections: tuple[DashboardSection, ...]
    safety_invariants: tuple[str, ...]

    def with_send_status(self, send_status: str) -> OperatorStatusReport:
        return replace(
            self,
            alert_decision=replace(self.alert_decision, send_status=send_status),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "headline_ko": self.headline_ko,
            "next_action_ko": self.next_action_ko,
            "dashboard_url": self.dashboard_url,
            "alert_decision": self.alert_decision.to_dict(),
            "surfaces": [surface.to_dict() for surface in self.surfaces],
            "dashboard_sections": [section.to_dict() for section in self.dashboard_sections],
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 운영자 상태 보고 (as of {self.timestamp_utc})",
            "",
            "읽기 전용 보고입니다. 자율 루프 진행 상황과 개입 필요 이벤트만 요약합니다.",
            "주문, 자본 배분, live 설정, 서버 SSH, broker 호출은 수행하지 않습니다.",
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| headline_ko | {_table(self.headline_ko)} |",
            f"| next_action_ko | {_table(self.next_action_ko)} |",
            f"| dashboard_url | {_table(self.dashboard_url or '(없음)')} |",
            "",
            "## 모바일 알림 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| alert_level | {self.alert_decision.alert_level} |",
            f"| should_send | {str(self.alert_decision.should_send).lower()} |",
            f"| send_status | {self.alert_decision.send_status} |",
            f"| reason_ko | {_table(self.alert_decision.reason_ko)} |",
            "",
            "## 입력 표면",
            "",
            "| 표면 | 존재 | 파싱 | 상태 | 심각도 | 요약 | 다음 행동 |",
            "|------|:----:|------|------|--------|------|-----------|",
        ]
        for surface in self.surfaces:
            present = "yes" if surface.present else "no"
            lines.append(
                f"| {surface.key} | {present} | {surface.parse_status} | "
                f"{_table(surface.status)} | {surface.severity} | "
                f"{_table(surface.summary_ko)} | {_table(surface.next_action_ko)} |"
            )

        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)


def build_operator_status(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
    dashboard_url: str | None = None,
) -> OperatorStatusReport:
    """sidecar 텍스트 모음으로 운영자 상태 보고를 만든다."""

    timestamp = _as_utc(now).isoformat().replace("+00:00", "Z")
    surfaces = (
        _pipeline_surface(evidence_texts.get("pipeline-liveness")),
        _money_path_surface(evidence_texts.get("money-path")),
        _capital_surface(evidence_texts.get("capital-path-readiness")),
        _alignment_surface(evidence_texts.get("money-gate-alignment")),
        _work_surface(evidence_texts.get("autonomous-work-execution")),
        _released_surface(evidence_texts.get("released-work")),
    )
    overall = _overall_status(surfaces)
    headline = _headline(overall, surfaces)
    next_action = _next_action(overall, surfaces)
    sections = _dashboard_sections(surfaces)
    alert = _alert_decision(
        overall=overall,
        headline=headline,
        next_action=next_action,
        surfaces=surfaces,
        dashboard_url=dashboard_url,
    )
    return OperatorStatusReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=timestamp,
        overall_status=overall,
        headline_ko=headline,
        next_action_ko=next_action,
        dashboard_url=dashboard_url,
        alert_decision=alert,
        surfaces=surfaces,
        dashboard_sections=sections,
        safety_invariants=SAFETY_INVARIANTS,
    )


def report_from_dict(payload: Mapping[str, Any]) -> OperatorStatusReport:
    """JSON sidecar dict를 상태판 렌더링에 쓰는 dataclass로 복원한다."""

    alert = payload.get("alert_decision") if isinstance(payload.get("alert_decision"), dict) else {}
    return OperatorStatusReport(
        schema_version=_str(payload.get("schema_version"), SCHEMA_VERSION),
        run_id=_str(payload.get("run_id"), "unknown"),
        commit=_str(payload.get("commit"), "unknown"),
        timestamp_utc=_str(payload.get("timestamp_utc"), ""),
        overall_status=_str(payload.get("overall_status"), STATUS_ATTENTION),
        headline_ko=_str(payload.get("headline_ko"), "운영자 상태 보고를 읽었습니다."),
        next_action_ko=_str(payload.get("next_action_ko"), ""),
        dashboard_url=_optional_str(payload.get("dashboard_url")),
        alert_decision=MobileAlertDecision(
            alert_level=_str(alert.get("alert_level"), ALERT_ATTENTION_ONLY),
            should_send=bool(alert.get("should_send", False)),
            reason_ko=_str(alert.get("reason_ko"), ""),
            message_ko=_str(alert.get("message_ko"), ""),
            send_status=_str(alert.get("send_status"), SEND_NOT_ATTEMPTED),
        ),
        surfaces=tuple(
            OperatorSurface(
                key=_str(item.get("key"), "unknown"),
                source_ref=_str(item.get("source_ref"), ""),
                present=bool(item.get("present")),
                parse_status=_str(item.get("parse_status"), PARSE_MALFORMED),
                status=_str(item.get("status"), "UNKNOWN"),
                severity=_str(item.get("severity"), SEVERITY_ATTENTION),
                summary_ko=_str(item.get("summary_ko"), ""),
                next_action_ko=_str(item.get("next_action_ko"), ""),
            )
            for item in _list_of_dicts(payload.get("surfaces"))
        ),
        dashboard_sections=tuple(
            DashboardSection(
                key=_str(item.get("key"), "unknown"),
                title_ko=_str(item.get("title_ko"), ""),
                status=_str(item.get("status"), "UNKNOWN"),
                body_ko=_str(item.get("body_ko"), ""),
            )
            for item in _list_of_dicts(payload.get("dashboard_sections"))
        ),
        safety_invariants=tuple(str(item) for item in payload.get("safety_invariants", ())),
    )


def parse_operator_status(text: str | None) -> OperatorStatusReport | None:
    payload = _json_any(text)
    if not isinstance(payload, Mapping):
        return None
    return report_from_dict(payload)


def _pipeline_surface(raw: str | None) -> OperatorSurface:
    parsed = _json_any(raw)
    if parsed is None:
        return _missing_or_malformed("pipeline-liveness", raw)
    overall = _str(parsed.get("overall") or parsed.get("overall_status"), "UNKNOWN")
    if overall == "CRITICAL":
        severity = SEVERITY_CRITICAL
        summary = "핵심 자동화 sidecar 중 하나 이상이 정지 상태입니다."
        next_action = "pipeline-liveness LAST_RUN.md에서 멈춘 workflow를 확인한다."
    elif overall == "DEGRADED":
        severity = SEVERITY_ATTENTION
        summary = "핵심 돈 경로는 막히지 않았지만 일부 보고 sidecar가 늦었습니다."
        next_action = "지연된 비핵심 sidecar를 상태판에서 확인한다."
    else:
        severity = SEVERITY_INFO
        summary = "핵심 자동화 생존 감시는 정상입니다."
        next_action = ""
    return OperatorSurface(
        key="pipeline-liveness",
        source_ref=SOURCE_REFS["pipeline-liveness"],
        present=True,
        parse_status=PARSE_OK,
        status=overall,
        severity=severity,
        summary_ko=summary,
        next_action_ko=next_action,
    )


def _money_path_surface(raw: str | None) -> OperatorSurface:
    parsed = _json_any(raw)
    if parsed is None:
        return _missing_or_malformed("money-path", raw)
    live_state = parsed.get("live_money_state")
    live_status = "UNKNOWN"
    if isinstance(live_state, Mapping):
        live_status = _str(live_state.get("status"), "UNKNOWN")
    stage = _str(parsed.get("stage"), "UNKNOWN")
    blocker = _str(parsed.get("blocking_gate") or parsed.get("next_action"), "")
    if live_status == "BLOCKED" or stage == "BLOCKED":
        severity = SEVERITY_ACTION
        summary = f"실제 돈 경로가 차단 상태입니다: {blocker or live_status}"
        next_action = blocker or "money-path sidecar의 차단 사유를 확인한다."
    elif live_status == "REAL_ORDER_PATH_ARMED":
        severity = SEVERITY_ATTENTION
        summary = (
            "실제 주문 경로가 무장 상태입니다. "
            "최신 주문 sidecar와 감사 로그를 함께 봐야 합니다."
        )
        next_action = "micro GTAA와 live canary 최신 sidecar를 확인한다."
    else:
        severity = SEVERITY_INFO
        summary = f"실제 돈 경로는 {live_status}, 진행 단계는 {stage}입니다."
        next_action = blocker if stage not in {"DEPLOYED", "UNKNOWN"} else ""
    return OperatorSurface(
        key="money-path",
        source_ref=SOURCE_REFS["money-path"],
        present=True,
        parse_status=PARSE_OK,
        status=live_status,
        severity=severity,
        summary_ko=summary,
        next_action_ko=next_action,
    )


def _capital_surface(raw: str | None) -> OperatorSurface:
    parsed = _json_any(raw)
    if parsed is None:
        return _missing_or_malformed("capital-path-readiness", raw)
    readiness = _str(parsed.get("readiness_state"), "UNKNOWN")
    live_status = _str(parsed.get("live_money_status"), "UNKNOWN")
    blocker = _str(parsed.get("blocking_gate") or parsed.get("next_action_ko"), "")
    if readiness in {"BLOCKED", "UNKNOWN"} or live_status == "BLOCKED":
        severity = SEVERITY_ACTION
        summary = f"자본 경로 준비도가 {readiness}입니다."
        next_action = blocker or "capital-path-readiness JSON 발행과 입력 sidecar를 확인한다."
    else:
        severity = SEVERITY_INFO
        summary = f"자본 준비도는 {readiness}, 실제 돈 상태는 {live_status}입니다."
        next_action = blocker if readiness == "ACCUMULATING_EDGE" else ""
    return OperatorSurface(
        key="capital-path-readiness",
        source_ref=SOURCE_REFS["capital-path-readiness"],
        present=True,
        parse_status=PARSE_OK,
        status=readiness,
        severity=severity,
        summary_ko=summary,
        next_action_ko=next_action,
    )


def _alignment_surface(raw: str | None) -> OperatorSurface:
    parsed = _json_any(raw)
    if parsed is None:
        return _missing_or_malformed("money-gate-alignment", raw)
    status = _str(parsed.get("overall_status"), "UNKNOWN")
    next_action = _str(parsed.get("next_action_ko"), "")
    if status == "BLOCKED":
        severity = SEVERITY_ACTION
        summary = "돈 경로 sidecar들이 차단 상태를 보고합니다."
    elif status == "MISALIGNED":
        severity = SEVERITY_ACTION
        summary = "돈 경로 sidecar들이 서로 다른 상태를 말합니다."
    else:
        severity = SEVERITY_INFO
        summary = f"돈 경로 정렬 상태는 {status}입니다."
    return OperatorSurface(
        key="money-gate-alignment",
        source_ref=SOURCE_REFS["money-gate-alignment"],
        present=True,
        parse_status=PARSE_OK,
        status=status,
        severity=severity,
        summary_ko=summary,
        next_action_ko=next_action,
    )


def _work_surface(raw: str | None) -> OperatorSurface:
    parsed = _json_any(raw)
    if parsed is None:
        return _missing_or_malformed("autonomous-work-execution", raw)
    status = _str(parsed.get("overall_status"), "UNKNOWN")
    selected = parsed.get("selected_work")
    candidate = title = next_action = ""
    if isinstance(selected, Mapping):
        candidate = _str(selected.get("candidate_id"), "")
        title = _str(selected.get("title_ko"), "")
        next_action = _str(selected.get("next_action_ko"), "")
    if status == "BLOCKED":
        severity = SEVERITY_ACTION
        summary = "자율 작업 실행 루프가 다음 작업을 고르지 못했습니다."
    elif status == "OPERATOR_APPROVAL_REQUIRED":
        severity = SEVERITY_ACTION
        summary = f"다음 자율 작업은 운영자 승인 필요 상태입니다: {title or candidate or status}"
    elif status == "EXECUTION_READY":
        severity = SEVERITY_INFO
        summary = f"다음 자율 작업은 {title or candidate or '선택됨'}입니다."
    else:
        severity = SEVERITY_ATTENTION
        summary = f"자율 작업 실행 상태는 {status}입니다."
    return OperatorSurface(
        key="autonomous-work-execution",
        source_ref=SOURCE_REFS["autonomous-work-execution"],
        present=True,
        parse_status=PARSE_OK,
        status=status,
        severity=severity,
        summary_ko=summary,
        next_action_ko=next_action,
    )


def _released_surface(raw: str | None) -> OperatorSurface:
    parsed = _json_any(raw)
    if parsed is None:
        return _missing_or_malformed("released-work", raw)
    status = _str(parsed.get("overall_status"), "UNKNOWN")
    entries = parsed.get("released_work")
    count = len(entries) if isinstance(entries, Sequence) and not isinstance(entries, str) else 0
    severity = SEVERITY_INFO if status in {"OK", "EMPTY"} else SEVERITY_ATTENTION
    return OperatorSurface(
        key="released-work",
        source_ref=SOURCE_REFS["released-work"],
        present=True,
        parse_status=PARSE_OK,
        status=status,
        severity=severity,
        summary_ko=f"완료 후보 장부 상태는 {status}, 완료 후보 {count}개입니다.",
        next_action_ko="",
    )


def _missing_or_malformed(key: str, raw: str | None) -> OperatorSurface:
    parse_status = PARSE_MISSING if raw is None else PARSE_MALFORMED
    present = raw is not None
    source_ref = SOURCE_REFS.get(key, key)
    if key in {"pipeline-liveness", "money-path", "money-gate-alignment"}:
        severity = SEVERITY_ACTION
    else:
        severity = SEVERITY_ATTENTION
    return OperatorSurface(
        key=key,
        source_ref=source_ref,
        present=present,
        parse_status=parse_status,
        status="UNKNOWN",
        severity=severity,
        summary_ko=f"{key} 입력을 읽을 수 없습니다.",
        next_action_ko=f"{source_ref} sidecar 발행 상태를 확인한다.",
    )


def _overall_status(surfaces: Sequence[OperatorSurface]) -> str:
    if any(surface.severity == SEVERITY_CRITICAL for surface in surfaces):
        return STATUS_CRITICAL
    if any(surface.severity == SEVERITY_ACTION for surface in surfaces):
        return STATUS_ACTION_REQUIRED
    if any(surface.severity == SEVERITY_ATTENTION for surface in surfaces):
        return STATUS_ATTENTION
    return STATUS_OK


def _headline(overall: str, surfaces: Sequence[OperatorSurface]) -> str:
    if overall == STATUS_CRITICAL:
        return "핵심 자동화 정지 가능성이 있어 즉시 확인이 필요합니다."
    if overall == STATUS_ACTION_REQUIRED:
        first = _first_by_severity(surfaces, (SEVERITY_ACTION,))
        return first.summary_ko if first else "개입이 필요한 자율 루프 상태가 있습니다."
    if overall == STATUS_ATTENTION:
        first = _first_by_severity(surfaces, (SEVERITY_ATTENTION,))
        return first.summary_ko if first else "일부 보조 보고 상태를 확인하면 좋습니다."
    return "자율 루프 관측 표면이 정상 범위입니다."


def _next_action(overall: str, surfaces: Sequence[OperatorSurface]) -> str:
    if overall == STATUS_OK:
        return "대시보드만 확인하면 됩니다. 별도 개입은 필요 없습니다."
    target = _first_by_severity(
        surfaces,
        (SEVERITY_CRITICAL, SEVERITY_ACTION, SEVERITY_ATTENTION),
    )
    if target and target.next_action_ko:
        return target.next_action_ko
    if target:
        return f"{target.source_ref}를 확인한다."
    return "operator-status sidecar를 확인한다."


def _dashboard_sections(surfaces: Sequence[OperatorSurface]) -> tuple[DashboardSection, ...]:
    by_key = {surface.key: surface for surface in surfaces}
    money = by_key.get("money-path")
    work = by_key.get("autonomous-work-execution")
    alignment = by_key.get("money-gate-alignment")
    liveness = by_key.get("pipeline-liveness")
    action_items = [
        surface.summary_ko
        for surface in surfaces
        if surface.severity in {SEVERITY_ACTION, SEVERITY_CRITICAL}
    ]
    return (
        DashboardSection(
            key="money",
            title_ko="실제 돈 경로",
            status=money.status if money else "UNKNOWN",
            body_ko=money.summary_ko if money else "money-path 입력이 없습니다.",
        ),
        DashboardSection(
            key="autonomous-work",
            title_ko="다음 자율 작업",
            status=work.status if work else "UNKNOWN",
            body_ko=work.summary_ko if work else "autonomous-work 입력이 없습니다.",
        ),
        DashboardSection(
            key="alignment",
            title_ko="돈 경로 정렬",
            status=alignment.status if alignment else "UNKNOWN",
            body_ko=alignment.summary_ko if alignment else "money-gate-alignment 입력이 없습니다.",
        ),
        DashboardSection(
            key="action-needed",
            title_ko="개입 필요",
            status=liveness.status if liveness and action_items else STATUS_OK,
            body_ko=" / ".join(action_items) if action_items else "개입 필요 항목이 없습니다.",
        ),
    )


def _alert_decision(
    *,
    overall: str,
    headline: str,
    next_action: str,
    surfaces: Sequence[OperatorSurface],
    dashboard_url: str | None,
) -> MobileAlertDecision:
    if overall == STATUS_CRITICAL:
        level = ALERT_CRITICAL
    elif overall == STATUS_ACTION_REQUIRED:
        level = ALERT_ACTION_REQUIRED
    elif overall == STATUS_ATTENTION:
        level = ALERT_ATTENTION_ONLY
    else:
        level = ALERT_SILENT_OK
    should_send = level in {ALERT_ACTION_REQUIRED, ALERT_CRITICAL}
    reasons = [
        surface
        for surface in surfaces
        if surface.severity in {SEVERITY_ACTION, SEVERITY_CRITICAL}
    ]
    if should_send:
        reason = f"개입 필요 표면 {len(reasons)}개가 있습니다."
    elif level == ALERT_ATTENTION_ONLY:
        reason = "보조 확인 항목만 있어 모바일 알림은 보내지 않습니다."
    else:
        reason = "정상 상태라 모바일 알림은 보내지 않습니다."
    message = _message(
        overall=overall,
        headline=headline,
        next_action=next_action,
        surfaces=reasons,
        dashboard_url=dashboard_url,
    )
    clean_message = _mask_alert_text(message)
    return MobileAlertDecision(
        alert_level=level,
        should_send=should_send,
        reason_ko=reason,
        message_ko=_truncate_alert_message(clean_message, limit=1800),
    )


def _message(
    *,
    overall: str,
    headline: str,
    next_action: str,
    surfaces: Sequence[OperatorSurface],
    dashboard_url: str | None,
) -> str:
    lines = [
        f"auto-invest 운영자 알림: {overall}",
        headline,
        "",
        f"다음 행동: {next_action}",
    ]
    if surfaces:
        lines += ["", "개입 필요 표면:"]
        for surface in surfaces[:5]:
            lines.append(f"- {surface.key}: {surface.summary_ko}")
    if dashboard_url:
        lines += ["", f"상태판: {dashboard_url}"]
    lines += ["", "읽기 전용 알림입니다. 주문, 자본, live 설정은 변경하지 않았습니다."]
    return "\n".join(lines)


def _mask_alert_text(text: str) -> str:
    """Mask token/account-like fragments that arrived as plain text."""

    def _mask_pair(match: re.Match[str]) -> str:
        return f"{match.group(1)} ***"

    masked = re.sub(
        r"(?i)\b(token|secret|chat_id|bot_token|telegram_chat_id)\b[:=\s]+([^\s]+)",
        _mask_pair,
        text,
    )
    return re.sub(r"\b\d{6,}\b", lambda m: "*" * (len(m.group(0)) - 2) + m.group(0)[-2:], masked)


def _truncate_alert_message(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>"


def _json_any(raw: str | None) -> Any | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    blocks = _FENCED_JSON_RE.findall(text)
    for block in reversed(blocks):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue
    return None


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _str(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value)
    return text if text else default


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list | tuple):
        return []
    return [item for item in value if isinstance(item, dict)]


def _first_by_severity(
    surfaces: Sequence[OperatorSurface],
    severities: Sequence[str],
) -> OperatorSurface | None:
    severity_rank = {severity: index for index, severity in enumerate(severities)}
    candidates = [surface for surface in surfaces if surface.severity in severity_rank]
    if not candidates:
        return None
    return sorted(candidates, key=lambda surface: severity_rank[surface.severity])[0]


__all__ = [
    "ALERT_ACTION_REQUIRED",
    "ALERT_ATTENTION_ONLY",
    "ALERT_CRITICAL",
    "ALERT_SILENT_OK",
    "CONSUMED_SIDECARS",
    "OperatorStatusReport",
    "SEND_FAILED",
    "SEND_NOT_ATTEMPTED",
    "SEND_SENT",
    "SEND_SKIPPED_MISSING_SECRETS",
    "STATUS_ACTION_REQUIRED",
    "STATUS_ATTENTION",
    "STATUS_CRITICAL",
    "STATUS_OK",
    "build_operator_status",
    "parse_operator_status",
    "report_from_dict",
]
