"""스펙 078 — 돈 경로 게이트 정렬 루프.

돈 경로 관련 sidecar를 한 번에 읽어 같은 상태를 말하는지 대조한다.

안전 경계: 읽기 전용·순수·결정론. 브로커, 주문, 계좌, 라이브 설정,
whitelist/caps, 헌법/커널을 변경하지 않는다. 이 루프는 기존 money-path,
edge-autoarm, reassign, capital-path-readiness 게이트를 대체하지 않고
불일치와 다음 자동 작업 후보를 드러내는 보고 표면이다.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from auto_invest.analytics.evolution_loop import mask_sensitive_values
from auto_invest.analytics.pipeline_liveness import parse_timestamp_utc

SCHEMA_VERSION = "1.0"

PARSE_OK = "ok"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

SEVERITY_INFO = "INFO"
SEVERITY_WAITING = "WAITING"
SEVERITY_SNAPSHOT_SKEW = "SNAPSHOT_SKEW"
SEVERITY_MISALIGNED = "MISALIGNED"
SEVERITY_BLOCKED = "BLOCKED"

STATUS_ALIGNED_WAITING = "ALIGNED_WAITING"
STATUS_ALIGNED_READY = "ALIGNED_READY"
STATUS_MISALIGNED = "MISALIGNED"
STATUS_BLOCKED = "BLOCKED"
STATUS_UNKNOWN = "UNKNOWN"

LIVE_STATUS_UNKNOWN = "UNKNOWN"
LIVE_STATUS_PREVIEW = "PREVIEW_ONLY"
STAGE_UNKNOWN = "UNKNOWN"
STAGE_ACCUMULATING = "ACCUMULATING_EDGE"
VERDICT_INSUFFICIENT = "INSUFFICIENT_DATA"

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "report-only; existing money gates remain authoritative",
)

SOURCE_REFS: dict[str, str] = {
    "money-path": "automation/money-path-last-run:LAST_RUN.md",
    "capital-path-readiness": (
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
    ),
    "edge-autoarm": "automation/edge-autoarm-last-run:LAST_RUN.md",
    "reassign": "automation/reassign-last-run:LAST_RUN.md",
    "rebalance-paper-forward": "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
    "pipeline-liveness": "automation/pipeline-liveness-last-run:LAST_RUN.md",
    "autonomous-work-execution": (
        "automation/autonomous-work-execution-last-run:autonomous_work_execution.json"
    ),
    "kis-smoke": "automation/kis-smoke-last-run:LAST_RUN.md",
}

_HEADERS: dict[str, tuple[str, ...]] = {
    "money-path": ("결정 JSON", "decision JSON"),
    "capital-path-readiness": ("결정 JSON", "decision JSON"),
    "edge-autoarm": ("결정 JSON", "decision JSON"),
    "reassign": ("5중 게이트 결정 JSON", "결정 JSON", "decision JSON"),
    "rebalance-paper-forward": ("리더보드 결정 JSON", "결정 JSON", "decision JSON"),
    "pipeline-liveness": ("결정 JSON", "decision JSON"),
    "autonomous-work-execution": ("결정 JSON", "decision JSON"),
    "kis-smoke": ("결정 JSON", "decision JSON"),
}


@dataclass(frozen=True)
class GateSurface:
    """입력 sidecar 한 개의 상태."""

    key: str
    source_ref: str
    present: bool
    parse_status: str
    status: str
    timestamp_utc: str | None
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source_ref": self.source_ref,
            "present": self.present,
            "parse_status": self.parse_status,
            "status": self.status,
            "timestamp_utc": self.timestamp_utc,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class GateAlignmentIssue:
    """게이트 간 정렬 이슈."""

    issue_id: str
    severity: str
    gate_key: str
    expected: str
    observed: str
    reason_ko: str
    next_action_ko: str
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "severity": self.severity,
            "gate_key": self.gate_key,
            "expected": self.expected,
            "observed": self.observed,
            "reason_ko": self.reason_ko,
            "next_action_ko": self.next_action_ko,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class MoneyGateAlignmentReport:
    """돈 경로 게이트 정렬 최종 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    live_money_status: str
    readiness_state: str
    capital_ladder_stage: str
    blocking_gate: str
    selected_work_candidate: str | None
    next_action_ko: str
    gate_surfaces: tuple[GateSurface, ...]
    alignment_issues: tuple[GateAlignmentIssue, ...]
    safety_invariants: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "live_money_status": self.live_money_status,
            "readiness_state": self.readiness_state,
            "capital_ladder_stage": self.capital_ladder_stage,
            "blocking_gate": self.blocking_gate,
            "selected_work_candidate": self.selected_work_candidate,
            "next_action_ko": self.next_action_ko,
            "gate_surfaces": [surface.to_dict() for surface in self.gate_surfaces],
            "alignment_issues": [issue.to_dict() for issue in self.alignment_issues],
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 돈 경로 게이트 정렬 루프 (as of {self.timestamp_utc})",
            "",
            "읽기 전용 보고입니다. 주문, 자본 배분, live 설정 변경은 하지 않습니다.",
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| live_money_status | {_table(self.live_money_status)} |",
            f"| readiness_state | {_table(self.readiness_state)} |",
            f"| capital_ladder_stage | {_table(self.capital_ladder_stage)} |",
            f"| blocking_gate | {_table(self.blocking_gate)} |",
            f"| selected_work_candidate | {_table(self.selected_work_candidate or '(없음)')} |",
            f"| next_action_ko | {_table(self.next_action_ko)} |",
            "",
            "## 정렬 이슈",
            "",
        ]
        if self.alignment_issues:
            lines += [
                "| 심각도 | 게이트 | 기대 | 관측 | 이유 | 다음 행동 |",
                "|--------|--------|------|------|------|-----------|",
            ]
            for issue in self.alignment_issues:
                lines.append(
                    f"| {issue.severity} | {_table(issue.gate_key)} | "
                    f"{_table(issue.expected)} | {_table(issue.observed)} | "
                    f"{_table(issue.reason_ko)} | {_table(issue.next_action_ko)} |"
                )
        else:
            lines.append("- 구조화된 정렬 이슈 없음.")

        lines += [
            "",
            "## 입력 증거",
            "",
            "| 증거 | 존재 | 파싱 | 상태 | 시각 | 요약 |",
            "|------|:----:|------|------|------|------|",
        ]
        for surface in self.gate_surfaces:
            present = "yes" if surface.present else "no"
            timestamp = surface.timestamp_utc or "-"
            lines.append(
                f"| {surface.key} | {present} | {surface.parse_status} | "
                f"{_table(surface.status)} | {_table(timestamp)} | "
                f"{_table(surface.summary_ko)} |"
            )

        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        return "\n".join(lines)


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _clean(value: object, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return mask_sensitive_values(text)


def _table(value: object) -> str:
    return _clean(value).replace("|", "/").replace("\n", " ")


def _json_value(text: str | None) -> Any | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _json_from_fence(text: str, headers: Sequence[str]) -> Any | None:
    lines = text.splitlines()
    starts: list[int] = []
    for i, line in enumerate(lines):
        if any(header in line for header in headers):
            starts.append(i + 1)
    starts.append(0)

    for start in starts:
        in_block = False
        buf: list[str] = []
        for line in lines[start:]:
            stripped = line.strip()
            if not in_block:
                if stripped.startswith("```"):
                    in_block = True
                continue
            if stripped.startswith("```"):
                parsed = _json_value("\n".join(buf))
                if parsed is not None:
                    return parsed
                break
            buf.append(line)
    return None


def _json_any(text: str | None, *headers: str) -> Any | None:
    parsed = _json_value(text)
    if parsed is not None:
        return parsed
    if text:
        return _json_from_fence(text, headers)
    return None


def _json_dict(text: str | None, *headers: str) -> dict[str, Any] | None:
    parsed = _json_any(text, *headers)
    return parsed if isinstance(parsed, dict) else None


def _first_json_dict(text: str | None, *headers: str) -> dict[str, Any] | None:
    value = _json_dict(text, *headers)
    return value if value is not None else None


def _header_json_dict(text: str | None, *headers: str) -> dict[str, Any] | None:
    if not text:
        return None
    parsed = _json_from_fence(text, headers)
    return parsed if isinstance(parsed, dict) else None


def _str_field(data: Mapping[str, Any] | None, key: str, default: str = "") -> str:
    if not data:
        return default
    value = data.get(key)
    return _clean(value, default) if value is not None else default


def _nested(data: Mapping[str, Any] | None, *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _items(value: Any, keys: Sequence[str]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []
    for key in keys:
        raw = value.get(key)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    return []


def _table_value(text: str | None, label: str) -> str | None:
    if not text:
        return None
    match = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|", text)
    return _clean(match.group(1)) if match else None


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", _clean(value)).strip()


def _int_value(value: object) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def _ratio_from_text(text: object) -> tuple[int | None, int | None]:
    match = re.search(r"(\d+)\s*/\s*(\d+)", str(text or ""))
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _observation_counts(
    money: Mapping[str, Any] | None,
    edge_forward: Mapping[str, Any] | None,
    forward: Mapping[str, Any] | None,
) -> dict[str, tuple[int | None, int | None]]:
    counts: dict[str, tuple[int | None, int | None]] = {}
    money_n = _int_value(_nested(money, "forward_n_obs"))
    blocker_n, blocker_min = _ratio_from_text(_money_blocking_gate(money))
    if money_n is None:
        money_n = blocker_n
    if money_n is not None:
        counts["money-path"] = (money_n, blocker_min)

    if isinstance(edge_forward, Mapping):
        edge_n = _int_value(edge_forward.get("n_obs"))
        edge_min = _int_value(edge_forward.get("min_obs_required"))
        if edge_n is not None:
            counts["edge-autoarm"] = (edge_n, edge_min)

    if isinstance(forward, Mapping):
        forward_n = _int_value(forward.get("max_n_obs"))
        if forward_n is not None:
            counts["rebalance-paper-forward"] = (forward_n, None)
    return counts


def _observation_summary(
    money: Mapping[str, Any] | None,
    edge_forward: Mapping[str, Any] | None,
    forward: Mapping[str, Any] | None,
) -> str:
    counts = _observation_counts(money, edge_forward, forward)
    values = [value for value, _ in counts.values() if value is not None]
    if not values:
        return _money_blocking_gate(money)
    min_required = next((limit for _, limit in counts.values() if limit is not None), 20)
    if len(set(values)) == 1:
        return f"{values[0]}/{min_required}"
    source_values = ", ".join(f"{key}={value}" for key, (value, _) in counts.items())
    return f"{min(values)}-{max(values)}/{min_required} ({source_values})"


def _snapshot_skew_issue(
    money: Mapping[str, Any] | None,
    edge_forward: Mapping[str, Any] | None,
    forward: Mapping[str, Any] | None,
) -> GateAlignmentIssue | None:
    counts = _observation_counts(money, edge_forward, forward)
    values = {value for value, _ in counts.values() if value is not None}
    if len(values) <= 1:
        return None
    return _issue(
        SEVERITY_SNAPSHOT_SKEW,
        "snapshot_provenance",
        "same observation snapshot",
        _observation_summary(money, edge_forward, forward),
        (
            "서로 다른 sidecar 실행 시각 때문에 관측 수가 다르지만 모든 게이트가 "
            "관측 부족 대기를 말한다."
        ),
        (
            "다음 aligned run에서 money-path, edge-autoarm, forward sidecar가 같은 "
            "관측 수로 수렴하는지 확인한다."
        ),
        (
            SOURCE_REFS["money-path"],
            SOURCE_REFS["edge-autoarm"],
            SOURCE_REFS["rebalance-paper-forward"],
        ),
    )


def _issue(
    severity: str,
    gate_key: str,
    expected: object,
    observed: object,
    reason_ko: str,
    next_action_ko: str,
    source_refs: Sequence[str],
) -> GateAlignmentIssue:
    refs = tuple(source_refs)
    digest = hashlib.sha256(
        "|".join(
            [
                severity,
                gate_key,
                _normalize(expected),
                _normalize(observed),
                *refs,
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return GateAlignmentIssue(
        issue_id=f"mga-{digest}",
        severity=severity,
        gate_key=gate_key,
        expected=_clean(expected),
        observed=_clean(observed),
        reason_ko=_clean(reason_ko),
        next_action_ko=_clean(next_action_ko),
        source_refs=refs,
    )


def _money_live_status(money: Mapping[str, Any] | None) -> str:
    live_state = _nested(money, "live_money_state")
    if isinstance(live_state, Mapping) and live_state.get("status"):
        return _clean(live_state.get("status"))
    return _str_field(money, "live_money_status", LIVE_STATUS_UNKNOWN)


def _money_stage(money: Mapping[str, Any] | None) -> str:
    return _str_field(money, "stage") or _str_field(money, "capital_ladder_stage", STAGE_UNKNOWN)


def _money_blocking_gate(money: Mapping[str, Any] | None) -> str:
    if not money:
        return "money-path evidence missing"
    for key in ("blocking_gate", "blocker", "reason"):
        if money.get(key):
            return _clean(money.get(key))
    for gate in _items(money.get("gates"), ()):
        status = _clean(gate.get("status")).upper()
        if status in {"FAIL", "PENDING", "BLOCKED"}:
            name = gate.get("name") or gate.get("gate")
            reason = gate.get("reason") or gate.get("detail") or gate.get("current")
            return _clean(f"{name}: {reason}" if reason else name)
    return ""


def _capital_live_status(capital: Mapping[str, Any] | None) -> str:
    return _str_field(capital, "live_money_status", LIVE_STATUS_UNKNOWN)


def _capital_stage(capital: Mapping[str, Any] | None) -> str:
    return _str_field(capital, "capital_ladder_stage", STAGE_UNKNOWN)


def _capital_blocking_gate(capital: Mapping[str, Any] | None) -> str:
    return _str_field(capital, "blocking_gate")


def _capital_readiness(capital: Mapping[str, Any] | None) -> str:
    return _str_field(capital, "readiness_state", STATUS_UNKNOWN)


def _edge_forward_verdict(raw: str | None) -> dict[str, Any] | None:
    return _header_json_dict(raw, "forward 판정 JSON", "forward verdict JSON")


def _selected_work_candidate(work: Mapping[str, Any] | None) -> str | None:
    selected = work.get("selected_work") if work else None
    if isinstance(selected, Mapping):
        candidate_id = selected.get("candidate_id")
        return _clean(candidate_id) if candidate_id else None
    return None


def _kis_smoke_status(raw: str | None) -> str:
    secrets_present = (_table_value(raw, "secrets_present") or "").lower()
    key_valid = (_table_value(raw, "key_valid") or "").lower()
    smoke_state = _table_value(raw, "smoke_state")
    if (smoke_state or "").lower() in {"(unset)", "unset"}:
        smoke_state = None
    if secrets_present == "false":
        return "MISSING_SECRETS"
    if key_valid == "false":
        return "INVALID_KEY"
    return smoke_state or "UNKNOWN"


def _surface_for(
    key: str,
    raw: str | None,
    parsed: Any,
    *,
    extra: Mapping[str, Any] | None = None,
) -> GateSurface:
    source_ref = SOURCE_REFS[key]
    timestamp = parse_timestamp_utc(raw)
    if raw is None:
        return GateSurface(
            key=key,
            source_ref=source_ref,
            present=False,
            parse_status=PARSE_MISSING,
            status="missing",
            timestamp_utc=None,
            summary_ko="sidecar 없음",
        )
    if parsed is None and key != "kis-smoke":
        return GateSurface(
            key=key,
            source_ref=source_ref,
            present=True,
            parse_status=PARSE_MALFORMED,
            status="malformed",
            timestamp_utc=timestamp,
            summary_ko="원문 존재, 구조화 JSON 파싱 실패",
        )
    kis_table_ok = key == "kis-smoke" and _table_value(raw, "smoke_state") is not None
    return GateSurface(
        key=key,
        source_ref=source_ref,
        present=True,
        parse_status=PARSE_OK if parsed is not None or kis_table_ok else PARSE_MALFORMED,
        status=_status_for_surface(key, parsed, raw, extra=extra),
        timestamp_utc=timestamp,
        summary_ko=_summary_for_surface(key, parsed, raw, extra=extra),
    )


def _status_for_surface(
    key: str,
    parsed: Any,
    raw: str | None,
    *,
    extra: Mapping[str, Any] | None,
) -> str:
    if key == "money-path" and isinstance(parsed, Mapping):
        return f"{_money_live_status(parsed)}/{_money_stage(parsed)}"
    if key == "capital-path-readiness" and isinstance(parsed, Mapping):
        return f"{_capital_live_status(parsed)}/{_capital_stage(parsed)}"
    if key == "edge-autoarm" and isinstance(parsed, Mapping):
        forward = extra.get("edge_forward_verdict") if extra else None
        verdict = _str_field(forward, "verdict") if isinstance(forward, Mapping) else ""
        return "/".join(value for value in (_str_field(parsed, "action"), verdict) if value)
    if key == "reassign" and isinstance(parsed, Mapping):
        return _str_field(parsed, "action", "UNKNOWN")
    if key == "rebalance-paper-forward" and isinstance(parsed, Mapping):
        return _str_field(parsed, "observation_health", "UNKNOWN")
    if key == "pipeline-liveness" and isinstance(parsed, Mapping):
        return _str_field(parsed, "overall", _str_field(parsed, "overall_status", "UNKNOWN"))
    if key == "autonomous-work-execution" and isinstance(parsed, Mapping):
        return _str_field(parsed, "overall_status", "UNKNOWN")
    if key == "kis-smoke":
        return _kis_smoke_status(raw)
    return "UNKNOWN"


def _summary_for_surface(
    key: str,
    parsed: Any,
    raw: str | None,
    *,
    extra: Mapping[str, Any] | None,
) -> str:
    if key == "money-path" and isinstance(parsed, Mapping):
        return (
            f"live={_money_live_status(parsed)}, stage={_money_stage(parsed)}, "
            f"blocker={_money_blocking_gate(parsed)}"
        )
    if key == "capital-path-readiness" and isinstance(parsed, Mapping):
        return (
            f"readiness={_capital_readiness(parsed)}, live={_capital_live_status(parsed)}, "
            f"stage={_capital_stage(parsed)}"
        )
    if key == "edge-autoarm" and isinstance(parsed, Mapping):
        forward = extra.get("edge_forward_verdict") if extra else None
        n_obs = _str_field(forward, "n_obs") if isinstance(forward, Mapping) else ""
        min_obs = _str_field(forward, "min_obs_required") if isinstance(forward, Mapping) else ""
        return (
            f"action={_str_field(parsed, 'action')}, "
            f"forward={_str_field(forward, 'verdict') if isinstance(forward, Mapping) else ''}, "
            f"obs={n_obs}/{min_obs}"
        )
    if key == "reassign" and isinstance(parsed, Mapping):
        challenger = parsed.get("challenger_key")
        gates = parsed.get("gates")
        return (
            f"action={_str_field(parsed, 'action')}, "
            f"challenger={_clean(challenger or '(없음)')}, gates={_clean(gates)}"
        )
    if key == "rebalance-paper-forward" and isinstance(parsed, Mapping):
        return (
            f"known={_str_field(parsed, 'known_count')}, "
            f"comparable={_str_field(parsed, 'comparable_count')}, "
            f"max_obs={_str_field(parsed, 'max_n_obs')}"
        )
    if key == "pipeline-liveness" and isinstance(parsed, Mapping):
        overall = _str_field(parsed, "overall", _str_field(parsed, "overall_status"))
        critical = [
            _clean(check.get("key"))
            for check in _items(parsed, ("checks",))
            if _clean(check.get("status")) in {"STALE", "MISSING"} and check.get("critical")
        ]
        return f"overall={overall}, critical={', '.join(critical) or '(없음)'}"
    if key == "autonomous-work-execution" and isinstance(parsed, Mapping):
        return f"selected={_selected_work_candidate(parsed) or '(없음)'}"
    if key == "kis-smoke":
        return (
            f"secrets_present={_table_value(raw, 'secrets_present') or 'UNKNOWN'}, "
            f"smoke_state={_table_value(raw, 'smoke_state') or 'UNKNOWN'}, "
            f"key_valid={_table_value(raw, 'key_valid') or 'UNKNOWN'}"
        )
    return "구조화 증거 없음"


def _missing_or_malformed_issues(surfaces: Sequence[GateSurface]) -> list[GateAlignmentIssue]:
    issues: list[GateAlignmentIssue] = []
    for surface in surfaces:
        if surface.parse_status == PARSE_OK:
            continue
        issues.append(
            _issue(
                SEVERITY_BLOCKED,
                surface.key,
                "fresh structured sidecar",
                surface.parse_status,
                f"{surface.key} 증거가 없어 돈 경로 정렬을 확정할 수 없다.",
                f"{surface.key} workflow와 sidecar 발행 경로를 먼저 복구한다.",
                (surface.source_ref,),
            )
        )
    return issues


def _compare_core_fields(
    money: Mapping[str, Any] | None,
    capital: Mapping[str, Any] | None,
) -> list[GateAlignmentIssue]:
    if not money or not capital:
        return []
    issues: list[GateAlignmentIssue] = []
    money_live = _money_live_status(money)
    capital_live = _capital_live_status(capital)
    if (
        money_live != LIVE_STATUS_UNKNOWN
        and capital_live != LIVE_STATUS_UNKNOWN
        and money_live != capital_live
    ):
        issues.append(
            _issue(
                SEVERITY_MISALIGNED,
                "live_money_status",
                money_live,
                capital_live,
                "money-path와 capital-path-readiness의 실거래 경로 상태가 다르다.",
                "capital-path-readiness가 money-path JSON을 같은 규칙으로 읽는지 복구한다.",
                (SOURCE_REFS["money-path"], SOURCE_REFS["capital-path-readiness"]),
            )
        )

    money_stage = _money_stage(money)
    capital_stage = _capital_stage(capital)
    if (
        money_stage != STAGE_UNKNOWN
        and capital_stage != STAGE_UNKNOWN
        and money_stage != capital_stage
    ):
        issues.append(
            _issue(
                SEVERITY_MISALIGNED,
                "capital_ladder_stage",
                money_stage,
                capital_stage,
                "money-path 단계와 capital-path-readiness 단계가 다르다.",
                "두 sidecar의 stage 추출 규칙과 최신 실행 순서를 맞춘다.",
                (SOURCE_REFS["money-path"], SOURCE_REFS["capital-path-readiness"]),
            )
        )

    money_blocker = _money_blocking_gate(money)
    capital_blocker = _capital_blocking_gate(capital)
    if (
        money_blocker
        and capital_blocker
        and _normalize(money_blocker) != _normalize(capital_blocker)
    ):
        issues.append(
            _issue(
                SEVERITY_MISALIGNED,
                "blocking_gate",
                money_blocker,
                capital_blocker,
                "현재 돈 경로를 막는 이유가 두 보고 표면에서 다르다.",
                "money-path blocker를 기준으로 자본 준비도 요약을 재생성한다.",
                (SOURCE_REFS["money-path"], SOURCE_REFS["capital-path-readiness"]),
            )
        )
    return issues


def _pipeline_issues(liveness: Mapping[str, Any] | None) -> list[GateAlignmentIssue]:
    if not liveness:
        return []
    overall = _str_field(liveness, "overall", _str_field(liveness, "overall_status"))
    if overall != "CRITICAL":
        return []
    critical = [
        _clean(check.get("key"))
        for check in _items(liveness, ("checks",))
        if _clean(check.get("status")) in {"STALE", "MISSING"} and check.get("critical")
    ]
    observed = ", ".join(critical) if critical else "CRITICAL"
    return [
        _issue(
            SEVERITY_BLOCKED,
            "pipeline-liveness",
            "OK",
            observed,
            "핵심 자동 루프가 멈췄을 가능성이 있어 돈 경로 증거가 신뢰되지 않는다.",
            "멈춘 핵심 sidecar workflow를 먼저 복구한 뒤 돈 경로를 다시 정렬한다.",
            (SOURCE_REFS["pipeline-liveness"],),
        )
    ]


def _edge_reassign_issues(
    money: Mapping[str, Any] | None,
    edge: Mapping[str, Any] | None,
    forward_verdict: Mapping[str, Any] | None,
    reassign: Mapping[str, Any] | None,
) -> list[GateAlignmentIssue]:
    if not money:
        return []
    issues: list[GateAlignmentIssue] = []
    stage = _money_stage(money)
    if stage == STAGE_ACCUMULATING:
        action = _str_field(edge, "action")
        verdict = _str_field(forward_verdict, "verdict")
        if action and action != "WAIT_EDGE":
            issues.append(
                _issue(
                    SEVERITY_MISALIGNED,
                    "edge-autoarm",
                    "WAIT_EDGE while accumulating edge",
                    action,
                    "전진 관측 누적 단계인데 자본 사다리 action이 대기 상태가 아니다.",
                    "edge-autoarm 판정과 money-path stage의 입력 forward verdict를 대조한다.",
                    (SOURCE_REFS["money-path"], SOURCE_REFS["edge-autoarm"]),
                )
            )
        if verdict and verdict != VERDICT_INSUFFICIENT:
            issues.append(
                _issue(
                    SEVERITY_MISALIGNED,
                    "forward_verdict",
                    VERDICT_INSUFFICIENT,
                    verdict,
                    "money-path는 관측 누적 중인데 edge-autoarm forward 판정이 다르다.",
                    "forward verdict 원천과 money-path가 같은 스냅샷을 읽는지 확인한다.",
                    (SOURCE_REFS["money-path"], SOURCE_REFS["edge-autoarm"]),
                )
            )
        reassign_action = _str_field(reassign, "action")
        challenger = _nested(reassign, "challenger_key")
        if reassign_action and reassign_action != "HOLD":
            issues.append(
                _issue(
                    SEVERITY_MISALIGNED,
                    "reassign",
                    "HOLD while no confirmed edge",
                    reassign_action,
                    "전진 엣지가 부족한데 전략 재지정이 유지 상태가 아니다.",
                    "reassign 5중 게이트와 forward leaderboard 입력을 재검증한다.",
                    (SOURCE_REFS["money-path"], SOURCE_REFS["reassign"]),
                )
            )
        if challenger:
            issues.append(
                _issue(
                    SEVERITY_MISALIGNED,
                    "reassign_challenger",
                    "no challenger while accumulating edge",
                    challenger,
                    "관측 부족 단계인데 재지정 도전자가 지정됐다.",
                    "forward tournament champion과 reassign 입력을 다시 생성한다.",
                    (SOURCE_REFS["money-path"], SOURCE_REFS["reassign"]),
                )
            )
    return issues


def _money_path_blocked_issue(money: Mapping[str, Any] | None) -> GateAlignmentIssue | None:
    if not money:
        return None
    live_status = _money_live_status(money)
    stage = _money_stage(money)
    if live_status != "BLOCKED" and stage != "BLOCKED":
        return None

    blocker = _money_blocking_gate(money) or "money-path reports blocked"
    return _issue(
        SEVERITY_BLOCKED,
        "money-path",
        "orders gated until existing blockers clear",
        blocker,
        "money-path 자체가 실주문 불가 또는 자본 사다리 차단을 보고한다.",
        blocker,
        (SOURCE_REFS["money-path"],),
    )


def _kis_smoke_blocked_issue(raw: str | None) -> GateAlignmentIssue | None:
    if raw is None:
        return None
    status = _kis_smoke_status(raw)
    if status == "MISSING_SECRETS":
        return _issue(
            SEVERITY_BLOCKED,
            "kis-smoke",
            "server and broker evidence available",
            "secrets_present=false",
            "KIS smoke가 서버 접속 비밀값 부재로 브로커 사전 점검까지 도달하지 못한다.",
            (
                "서버에서 deploy/repair-ssh-boundary.sh로 제한 deploy gateway를 설치한 뒤 "
                "GitHub Actions에 non-root VULTR_SSH_USER와 VULTR_SSH_PRIVATE_KEY를 등록하고 "
                "KIS smoke를 다시 실행한다."
            ),
            (SOURCE_REFS["kis-smoke"],),
        )
    if status == "INVALID_KEY":
        return _issue(
            SEVERITY_BLOCKED,
            "kis-smoke",
            "valid SSH deploy key",
            "key_valid=false",
            "KIS smoke가 유효하지 않은 SSH 키 때문에 브로커 사전 점검까지 도달하지 못한다.",
            (
                "VULTR_SSH_PRIVATE_KEY를 ed25519 개인키 전체 형식으로 다시 등록하고 "
                "KIS smoke를 다시 실행한다."
            ),
            (SOURCE_REFS["kis-smoke"],),
        )
    if status.lower() == "setup_pending":
        return _issue(
            SEVERITY_BLOCKED,
            "kis-smoke",
            "server and broker evidence available",
            "smoke_state=setup_pending",
            "KIS smoke가 SSH 또는 원격 서버 셋업 미완료로 브로커 사전 점검까지 도달하지 못한다.",
            (
                "서버에서 deploy/repair-ssh-boundary.sh에 새 deploy 공개키를 설치하고 "
                "forced-command gateway 상태를 확인한 뒤 KIS smoke를 다시 실행한다."
            ),
            (SOURCE_REFS["kis-smoke"],),
        )
    return None


def _waiting_issue(
    money: Mapping[str, Any] | None,
    edge_forward: Mapping[str, Any] | None,
    reassign: Mapping[str, Any] | None,
    forward: Mapping[str, Any] | None,
) -> GateAlignmentIssue | None:
    if not money:
        return None
    blocker = _money_blocking_gate(money)
    stage = _money_stage(money)
    verdict = _str_field(edge_forward, "verdict")
    reassign_action = _str_field(reassign, "action")
    if stage == STAGE_ACCUMULATING or verdict == VERDICT_INSUFFICIENT:
        observed = _observation_summary(money, edge_forward, forward) or blocker
        return _issue(
            SEVERITY_WAITING,
            "forward_observation",
            "EDGE_CONFIRMED",
            observed,
            "전진 관측이 아직 최소 기준에 못 미치며 기존 게이트들이 같은 대기 상태다.",
            "전진 관측을 계속 누적하고, 최소 관측 이후 기존 자본 사다리로만 승격한다.",
            (
                SOURCE_REFS["money-path"],
                SOURCE_REFS["edge-autoarm"],
                SOURCE_REFS["reassign"],
            ),
        )
    if reassign_action == "HOLD" and not _nested(reassign, "challenger_key"):
        return _issue(
            SEVERITY_WAITING,
            "reassign",
            "confirmed challenger",
            "HOLD/no challenger",
            "재지정 도전자가 없어 기존 전략 유지가 정상이다.",
            "전진 토너먼트가 비교 가능한 챔피언을 만들 때까지 기존 전략을 유지한다.",
            (SOURCE_REFS["reassign"],),
        )
    return None


def _overall_status(issues: Sequence[GateAlignmentIssue]) -> str:
    severities = {issue.severity for issue in issues}
    if SEVERITY_BLOCKED in severities:
        return STATUS_BLOCKED
    if SEVERITY_MISALIGNED in severities:
        return STATUS_MISALIGNED
    if SEVERITY_WAITING in severities:
        return STATUS_ALIGNED_WAITING
    if issues:
        return STATUS_ALIGNED_READY
    return STATUS_UNKNOWN


def _next_action(status: str, issues: Sequence[GateAlignmentIssue]) -> str:
    if status in {STATUS_BLOCKED, STATUS_MISALIGNED}:
        blocked = [issue for issue in issues if issue.severity == SEVERITY_BLOCKED]
        by_gate = {issue.gate_key: issue for issue in blocked}
        if "kis-smoke" in by_gate and "money-path" in by_gate:
            return (
                f"{by_gate['kis-smoke'].next_action_ko} 그 뒤 "
                f"{by_gate['money-path'].next_action_ko}"
            )
        ordered = sorted(
            issues,
            key=lambda issue: (
                {SEVERITY_BLOCKED: 0, SEVERITY_MISALIGNED: 1}.get(issue.severity, 9),
                issue.issue_id,
            ),
        )
        return ordered[0].next_action_ko if ordered else "증거 sidecar를 먼저 복구한다."
    if status == STATUS_ALIGNED_WAITING:
        return "전진 관측을 계속 누적하고, 최소 관측 이후 기존 자본 사다리로만 승격한다."
    if status == STATUS_ALIGNED_READY:
        return "기존 edge-autoarm/reassign/자본 사다리 게이트로만 승격 가능성을 확인한다."
    return "money-path와 자본 준비도 sidecar를 먼저 갱신한다."


def build_money_gate_alignment(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> MoneyGateAlignmentReport:
    """수집된 sidecar 원문으로 돈 경로 게이트 정렬 보고를 만든다."""

    now = _as_utc(now)
    parsed: dict[str, Any] = {
        key: _first_json_dict(evidence_texts.get(key), *_HEADERS[key])
        for key in SOURCE_REFS
    }
    edge_forward = _edge_forward_verdict(evidence_texts.get("edge-autoarm"))
    parsed["edge-forward-verdict"] = edge_forward

    money = parsed["money-path"] if isinstance(parsed["money-path"], Mapping) else None
    capital = (
        parsed["capital-path-readiness"]
        if isinstance(parsed["capital-path-readiness"], Mapping)
        else None
    )
    edge = parsed["edge-autoarm"] if isinstance(parsed["edge-autoarm"], Mapping) else None
    reassign = parsed["reassign"] if isinstance(parsed["reassign"], Mapping) else None
    forward = (
        parsed["rebalance-paper-forward"]
        if isinstance(parsed["rebalance-paper-forward"], Mapping)
        else None
    )
    liveness = (
        parsed["pipeline-liveness"]
        if isinstance(parsed["pipeline-liveness"], Mapping)
        else None
    )
    work = (
        parsed["autonomous-work-execution"]
        if isinstance(parsed["autonomous-work-execution"], Mapping)
        else None
    )

    surfaces = tuple(
        _surface_for(
            key,
            evidence_texts.get(key),
            parsed.get(key),
            extra={"edge_forward_verdict": edge_forward},
        )
        for key in SOURCE_REFS
    )

    issues: list[GateAlignmentIssue] = []
    issues.extend(_missing_or_malformed_issues(surfaces))
    issues.extend(_pipeline_issues(liveness))
    issues.extend(_compare_core_fields(money, capital))
    issues.extend(_edge_reassign_issues(money, edge, edge_forward, reassign))
    blocked = _money_path_blocked_issue(money)
    if blocked is not None:
        issues.append(blocked)
    kis_blocked = _kis_smoke_blocked_issue(evidence_texts.get("kis-smoke"))
    if kis_blocked is not None:
        issues.append(kis_blocked)

    if not any(issue.severity in {SEVERITY_BLOCKED, SEVERITY_MISALIGNED} for issue in issues):
        skew = _snapshot_skew_issue(money, edge_forward, forward)
        if skew is not None:
            issues.append(skew)
        waiting = _waiting_issue(money, edge_forward, reassign, forward)
        if waiting is not None:
            issues.append(waiting)

    ordered_issues = tuple(sorted(issues, key=lambda issue: (issue.severity, issue.issue_id)))
    overall = _overall_status(ordered_issues)
    return MoneyGateAlignmentReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        overall_status=overall,
        live_money_status=_money_live_status(money),
        readiness_state=_capital_readiness(capital),
        capital_ladder_stage=_money_stage(money),
        blocking_gate=_money_blocking_gate(money),
        selected_work_candidate=_selected_work_candidate(work),
        next_action_ko=_next_action(overall, ordered_issues),
        gate_surfaces=surfaces,
        alignment_issues=ordered_issues,
        safety_invariants=SAFETY_INVARIANTS,
    )


__all__ = [
    "LIVE_STATUS_PREVIEW",
    "PARSE_MALFORMED",
    "PARSE_MISSING",
    "PARSE_OK",
    "SCHEMA_VERSION",
    "SEVERITY_BLOCKED",
    "SEVERITY_INFO",
    "SEVERITY_MISALIGNED",
    "SEVERITY_SNAPSHOT_SKEW",
    "SEVERITY_WAITING",
    "STATUS_ALIGNED_READY",
    "STATUS_ALIGNED_WAITING",
    "STATUS_BLOCKED",
    "STATUS_MISALIGNED",
    "STATUS_UNKNOWN",
    "GateAlignmentIssue",
    "GateSurface",
    "MoneyGateAlignmentReport",
    "build_money_gate_alignment",
]
