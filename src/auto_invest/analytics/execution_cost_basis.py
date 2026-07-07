"""스펙 104 - 체결 비용 기준 계약.

이미 발행된 sidecar 스냅샷만 읽어 accepted/fill 비용 기준이 실제로 평가
가능한지 판정한다. 브로커 API, 주문, 자본 배분, live 설정, whitelist/caps,
비밀값, 헌법/커널, 외부 유료 서비스는 건드리지 않는다.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

CONTRACT_READY = "CONTRACT_READY"
OBSERVATION_WAIT = "OBSERVATION_WAIT"
BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_PRESENT = "present"
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

GATE_PASS = "PASS"
GATE_WAIT = "WAIT"
GATE_FAIL = "FAIL"

COST_BASIS_READY = "COST_BASIS_READY"
COST_BASIS_OBSERVATION_WAIT = "COST_BASIS_OBSERVATION_WAIT"
COST_BASIS_BLOCKED = "COST_BASIS_BLOCKED"

COMPLETED_CANDIDATE_ID = "candidate-execution-cost-basis-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "candidate-broker-diagnostic-liveness-contract"

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("execution-quality", "automation/execution-quality-last-run:LAST_RUN.md"),
    ("kis-smoke", "automation/kis-smoke-last-run:LAST_RUN.md"),
    ("rebalance-micro-gtaa", "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md"),
    ("money-path", "automation/money-path-last-run:LAST_RUN.md"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run:LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
    (
        "capital-path-readiness",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
    ),
)

_REPO_SIDECAR_PATHS: Mapping[str, str] = {
    "execution-quality": "automation/execution-quality-last-run/LAST_RUN.md",
    "kis-smoke": "automation/kis-smoke-last-run/LAST_RUN.md",
    "rebalance-micro-gtaa": "automation/rebalance-micro-gtaa-last-run/LAST_RUN.md",
    "money-path": "automation/money-path-last-run/LAST_RUN.md",
    "pipeline-liveness": "automation/pipeline-liveness-last-run/LAST_RUN.md",
    "released-work": "automation/released-work-last-run/released_work.json",
    "capital-path-readiness": (
        "automation/capital-path-readiness-last-run/capital_path_readiness.json"
    ),
}

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no constitution/kernel modification",
    "no fresh external collection",
    "no external paid service",
    "read-only execution cost basis contract only",
)

_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(?P<body>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_JSON_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)
_RELEASED_STATUSES = {"released", "release", "complete", "completed", "done"}


@dataclass(frozen=True)
class EvidenceSurface:
    """보고서가 소비한 sidecar 입력 하나."""

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
class QualityGate:
    """체결 비용 기준 계약 조건 하나의 판정."""

    gate_id: str
    status: str
    summary_ko: str
    evidence_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "summary_ko": self.summary_ko,
            "evidence_keys": list(self.evidence_keys),
        }


@dataclass(frozen=True)
class ExecutionCostBasisReport:
    """체결 비용 기준 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    execution_quality_summary: dict[str, Any]
    money_path_summary: dict[str, Any]
    cost_basis_summary: dict[str, Any]
    quality_gates: tuple[QualityGate, ...]
    released_work_summary: dict[str, Any]
    capital_path_summary: dict[str, Any]
    safety_invariants: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "commit": self.commit,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "completed_candidate_id": self.completed_candidate_id,
            "next_candidate_id": self.next_candidate_id,
            "evidence_surfaces": [surface.to_dict() for surface in self.evidence_surfaces],
            "execution_quality_summary": self.execution_quality_summary,
            "money_path_summary": self.money_path_summary,
            "cost_basis_summary": self.cost_basis_summary,
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "capital_path_summary": self.capital_path_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 체결 비용 기준 계약 (as of {self.timestamp_utc})",
            "",
            (
                "기존 sidecar 스냅샷만 읽는 보고입니다. 주문, 자본 배분, live 설정, "
                "브로커 호출, 새 외부 수집은 하지 않습니다."
            ),
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| cost_basis_state | {self.cost_basis_summary.get('cost_basis_state')} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| next_candidate_id | {self.next_candidate_id} |",
        ]

        lines += ["", "## 비용 기준 요약", ""]
        lines += ["| 항목 | 값 |", "|------|-----|"]
        for key in (
            "execution_quality_has_cost_basis",
            "basis_complete",
            "accepted_or_filled_orders",
            "measurable_fills",
            "turnover_observed",
            "live_money_status",
            "can_submit_real_orders",
            "summary_ko",
        ):
            lines.append(f"| {key} | {_table(self.cost_basis_summary.get(key))} |")

        lines += ["", "## 검증 게이트", ""]
        lines += ["| 게이트 | 상태 | 요약 |", "|--------|------|------|"]
        for gate in self.quality_gates:
            lines.append(
                f"| {_table(gate.gate_id)} | {gate.status} | {_table(gate.summary_ko)} |"
            )

        lines += ["", "## 입력 증거", ""]
        lines += ["| 입력 | 파싱 | 출처 | 요약 |", "|------|------|------|------|"]
        for surface in self.evidence_surfaces:
            lines.append(
                f"| {_table(surface.key)} | {surface.parse_status} | "
                f"{_table(surface.source_ref)} | {_table(surface.summary_ko)} |"
            )

        lines += ["", "## 안전 경계", ""]
        for invariant in self.safety_invariants:
            lines.append(f"- {invariant}")
        lines += ["", "## 결정 JSON", "", "```json"]
        lines.append(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        return "\n".join(lines)


def build_execution_cost_basis_report(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> ExecutionCostBasisReport:
    """수집된 sidecar 원문으로 체결 비용 기준 계약을 만든다."""

    now = _as_utc(now)
    parsed = {key: _parse_for_key(key, evidence_texts.get(key)) for key, _ in REQUIRED_INPUTS}
    surfaces = tuple(
        _surface_for(key, source_ref, evidence_texts.get(key), parsed[key])
        for key, source_ref in REQUIRED_INPUTS
    )
    execution_summary = _execution_quality_summary(parsed["execution-quality"])
    money_summary = _money_path_summary(parsed["money-path"])
    cost_basis = _cost_basis_summary(
        parsed["execution-quality"],
        money_summary=money_summary,
    )
    gates = (
        _required_evidence_gate(surfaces),
        _cost_basis_observability_gate(cost_basis),
        _accepted_fill_cost_basis_gate(cost_basis),
        _money_path_context_gate(money_summary),
        _safety_boundary_gate(),
    )

    return ExecutionCostBasisReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=_overall_status(gates),
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_AUTONOMOUS_CANDIDATE_ID,
        evidence_surfaces=surfaces,
        execution_quality_summary=execution_summary,
        money_path_summary=money_summary,
        cost_basis_summary=cost_basis,
        quality_gates=gates,
        released_work_summary=_released_work_summary(parsed["released-work"]),
        capital_path_summary=_capital_path_summary(parsed["capital-path-readiness"]),
        safety_invariants=SAFETY_INVARIANTS,
    )


def read_evidence_manifest(manifest_path: Path, *, repo_root: Path) -> dict[str, str | None]:
    """탭 구분 manifest를 읽어 probe 입력 원문을 만든다."""

    evidence: dict[str, str | None] = {key: None for key, _ in REQUIRED_INPUTS}
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"manifest line must be key<TAB>branch<TAB>path: {raw_line}")
        key, branch, path = parts
        if key not in evidence:
            raise ValueError(f"unknown manifest key: {key}")
        local_path = repo_root / branch / path
        evidence[key] = local_path.read_text(encoding="utf-8") if local_path.exists() else None
    return evidence


def read_repo_sidecars(repo_root: Path) -> dict[str, str | None]:
    """저장소 checkout 안에 존재하는 automation sidecar 파일을 읽는다."""

    return {key: _read_optional(repo_root / path) for key, path in _REPO_SIDECAR_PATHS.items()}


def _parse_for_key(key: str, raw: str | None) -> Any:
    if raw is None:
        return None
    if key == "kis-smoke":
        return _kis_smoke_markdown(raw) or _parse_markdown_json(raw)
    if key == "rebalance-micro-gtaa":
        return _json_after_marker(raw, "## 라이브 전 전략 의도 게이트") or _parse_markdown_json(raw)
    if key in {"execution-quality", "money-path", "pipeline-liveness"}:
        return _parse_markdown_json(raw)
    return _parse_json(raw)


def _surface_for(
    key: str,
    source_ref: str,
    raw: str | None,
    parsed: Any,
) -> EvidenceSurface:
    if raw is None:
        return EvidenceSurface(key, source_ref, False, PARSE_MISSING, "sidecar 파일 없음")
    if parsed is None:
        return EvidenceSurface(
            key,
            source_ref,
            True,
            PARSE_MALFORMED,
            "원문은 있으나 구조화 파싱 실패",
        )
    return EvidenceSurface(
        key,
        source_ref,
        True,
        PARSE_OK if isinstance(parsed, (dict, list)) else PARSE_PRESENT,
        _summary_for(key, parsed),
    )


def _execution_quality_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, Mapping):
        return {
            "parseable": False,
            "overall_status": None,
            "has_execution_cost_basis": False,
            "rejected_orders": 0,
            "latest_signal": None,
            "monitor_verdict": None,
        }
    rejections = _mapping_value(parsed, "broker_rejections")
    live_gate = _mapping_value(parsed, "live_gate")
    return {
        "parseable": True,
        "overall_status": parsed.get("overall_status"),
        "has_execution_cost_basis": isinstance(
            parsed.get("execution_cost_basis"),
            Mapping,
        ),
        "rejected_orders": _int(_mapping_value(rejections, "rejected_orders"), 0),
        "latest_signal": _none_if_blank(_mapping_value(live_gate, "latest_signal")),
        "monitor_verdict": _none_if_blank(_mapping_value(live_gate, "verdict")),
    }


def _money_path_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, Mapping):
        return {
            "parseable": False,
            "live_money_status": None,
            "can_submit_real_orders": None,
            "armed": None,
            "accepted_or_filled_count": 0,
            "broker_rejected_count": 0,
            "last_run_status": None,
        }
    live_state = _mapping_value(parsed, "live_money_state")
    return {
        "parseable": True,
        "live_money_status": _lookup(parsed, "status", None)
        if not isinstance(live_state, Mapping)
        else live_state.get("status"),
        "can_submit_real_orders": _bool_or_none(_lookup(parsed, "can_submit_real_orders", None)),
        "armed": _bool_or_none(_lookup(parsed, "armed", None)),
        "accepted_or_filled_count": _int(_lookup(parsed, "accepted_or_filled_count", 0), 0),
        "broker_rejected_count": _int(_lookup(parsed, "broker_rejected_count", 0), 0),
        "last_run_status": _none_if_blank(_lookup(parsed, "last_run_status", None)),
    }


def _cost_basis_summary(
    execution_doc: Any,
    *,
    money_summary: Mapping[str, Any],
) -> dict[str, Any]:
    raw_basis = _mapping_value(execution_doc, "execution_cost_basis")
    has_cost_basis = isinstance(raw_basis, Mapping)
    basis = raw_basis if isinstance(raw_basis, Mapping) else {}
    accepted_or_filled = max(
        _int(basis.get("accepted_or_filled_orders"), 0),
        _int(basis.get("accepted_or_filled_count"), 0),
        _int(money_summary.get("accepted_or_filled_count"), 0),
    )
    measurable = max(
        _int(basis.get("measurable_fills"), 0),
        _int(basis.get("measurable_fill_count"), 0),
    )
    unmeasurable = max(
        _int(basis.get("unmeasurable_fills"), 0),
        _int(basis.get("unmeasurable_fill_count"), 0),
    )
    turnover_observed = _bool_or_none(basis.get("turnover_observed")) is True
    basis_complete = _bool_or_none(basis.get("basis_complete")) is True
    has_measurable_basis = basis_complete and (
        accepted_or_filled > 0 or measurable > 0 or turnover_observed
    )
    if has_measurable_basis:
        state = COST_BASIS_READY
        summary = "accepted/fill 체결 비용 기준이 구조화되어 비용 충분성을 판단할 수 있다."
    elif not has_cost_basis:
        state = COST_BASIS_OBSERVATION_WAIT
        summary = (
            "execution-quality에 execution_cost_basis 블록이 없어 "
            "실제 비용 기준 판단은 관측 대기다."
        )
    elif accepted_or_filled > 0:
        state = COST_BASIS_OBSERVATION_WAIT
        summary = "accepted/fill 표본은 있으나 측정 가능한 체결 비용 기준이 아직 완성되지 않았다."
    else:
        state = COST_BASIS_OBSERVATION_WAIT
        summary = "accepted/fill 표본이 없어 실제 체결 비용 기준을 아직 평가할 수 없다."

    return {
        "cost_basis_state": state,
        "execution_quality_has_cost_basis": has_cost_basis,
        "basis_complete": has_measurable_basis,
        "raw_basis_complete": basis_complete,
        "accepted_or_filled_orders": accepted_or_filled,
        "measurable_fills": measurable,
        "unmeasurable_fills": unmeasurable,
        "turnover_observed": turnover_observed,
        "avg_slippage_bps": _float_or_none(
            basis.get("avg_slippage_bps") or basis.get("average_slippage_bps")
        ),
        "median_slippage_bps": _float_or_none(basis.get("median_slippage_bps")),
        "total_cost_usd": _float_or_none(basis.get("total_cost_usd")),
        "live_money_status": money_summary.get("live_money_status"),
        "can_submit_real_orders": money_summary.get("can_submit_real_orders"),
        "summary_ko": summary,
    }


def _required_evidence_gate(surfaces: tuple[EvidenceSurface, ...]) -> QualityGate:
    bad = [
        f"{surface.key}:{surface.parse_status}"
        for surface in surfaces
        if surface.parse_status in {PARSE_MISSING, PARSE_MALFORMED}
    ]
    if bad:
        return QualityGate(
            "required_evidence_parse",
            GATE_FAIL,
            f"필수 입력 결손 또는 파싱 실패: {', '.join(bad)}",
            tuple(surface.key for surface in surfaces),
        )
    return QualityGate(
        "required_evidence_parse",
        GATE_PASS,
        "필수 sidecar가 모두 존재하고 구조화 파싱됐다.",
        tuple(surface.key for surface in surfaces),
    )


def _cost_basis_observability_gate(summary: Mapping[str, Any]) -> QualityGate:
    if summary.get("execution_quality_has_cost_basis"):
        return QualityGate(
            "execution_cost_basis_observability",
            GATE_PASS,
            "execution-quality에서 execution_cost_basis 블록을 읽었다.",
            ("execution-quality",),
        )
    return QualityGate(
        "execution_cost_basis_observability",
        GATE_WAIT,
        "execution-quality에 execution_cost_basis 블록이 아직 없다.",
        ("execution-quality",),
    )


def _accepted_fill_cost_basis_gate(summary: Mapping[str, Any]) -> QualityGate:
    if summary.get("basis_complete"):
        return QualityGate(
            "accepted_fill_cost_basis",
            GATE_PASS,
            (
                "accepted/fill 체결 비용 기준이 완성됐다: "
                f"{summary.get('accepted_or_filled_orders')}건"
            ),
            ("execution-quality", "money-path"),
        )
    accepted = _int(summary.get("accepted_or_filled_orders"), 0)
    if accepted > 0:
        return QualityGate(
            "accepted_fill_cost_basis",
            GATE_WAIT,
            "accepted/fill 표본은 있으나 측정 가능한 비용 기준이 부족하다.",
            ("execution-quality", "money-path"),
        )
    return QualityGate(
        "accepted_fill_cost_basis",
        GATE_WAIT,
        "accepted/fill 표본이 없어 실제 비용 기준을 아직 평가할 수 없다.",
        ("execution-quality", "money-path"),
    )


def _money_path_context_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            "money_path_context",
            GATE_FAIL,
            "money-path 증거를 읽을 수 없다.",
            ("money-path",),
        )
    status = summary.get("live_money_status")
    return QualityGate(
        "money_path_context",
        GATE_PASS,
        f"money-path 문맥을 읽었다: live_money_status={status}",
        ("money-path",),
    )


def _safety_boundary_gate() -> QualityGate:
    return QualityGate(
        "safety_boundary",
        GATE_PASS,
        "읽기 전용 계약이며 브로커, 주문, 자본, live 설정, 비밀값을 건드리지 않는다.",
        (),
    )


def _overall_status(gates: tuple[QualityGate, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if GATE_FAIL in statuses:
        return BLOCKED
    if GATE_WAIT in statuses:
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _released_work_summary(parsed: Any) -> dict[str, Any]:
    released = {
        str(item.get("candidate_id") or "")
        for item in _items(parsed, "released_work")
        if str(item.get("status", "")).lower() in _RELEASED_STATUSES
    }
    return {
        "parseable": isinstance(parsed, Mapping),
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "completed_candidate_released": COMPLETED_CANDIDATE_ID in released,
        "released_count": len(released),
    }


def _capital_path_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, Mapping):
        return {
            "parseable": False,
            "live_money_status": None,
            "readiness_state": None,
            "money_path_mutation": False,
        }
    return {
        "parseable": True,
        "live_money_status": parsed.get("live_money_status"),
        "readiness_state": parsed.get("readiness_state"),
        "capital_ladder_status": _lookup(parsed, "capital_ladder_status", None),
        "money_path_mutation": False,
    }


def _summary_for(key: str, parsed: Any) -> str:
    if isinstance(parsed, list):
        return f"목록 {len(parsed)}개"
    if not isinstance(parsed, Mapping):
        return "구조화 값 존재"
    if key == "execution-quality":
        basis = parsed.get("execution_cost_basis")
        return (
            f"overall={parsed.get('overall_status')}, "
            f"cost_basis_present={isinstance(basis, Mapping)}"
        )
    if key == "money-path":
        status = _lookup(parsed, "status", None)
        accepted = _lookup(parsed, "accepted_or_filled_count", 0)
        return f"status={status}, accepted_or_filled={accepted}"
    if key == "kis-smoke":
        return f"state={parsed.get('smoke_state')}, exit={parsed.get('smoke_exit')}"
    if key == "rebalance-micro-gtaa":
        return f"signal={parsed.get('latest_signal')}, reason={parsed.get('reason')}"
    if key == "pipeline-liveness":
        return f"overall={parsed.get('overall') or parsed.get('overall_status')}"
    if key == "released-work":
        return f"released_count={len(_items(parsed, 'released_work'))}"
    if key == "capital-path-readiness":
        return (
            f"readiness={parsed.get('readiness_state')}, "
            f"live={parsed.get('live_money_status')}"
        )
    return "구조화 JSON 존재"


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _parse_markdown_json(raw: str) -> Any:
    parsed = _parse_json(raw)
    if parsed is not None:
        return parsed
    matches = _FENCED_JSON_RE.findall(raw)
    for body in matches:
        parsed = _parse_json(body.strip())
        if parsed is not None:
            return parsed
        match = _JSON_OBJECT_RE.search(body)
        if match:
            parsed = _parse_json(match.group(1))
            if parsed is not None:
                return parsed
    return None


def _json_after_marker(raw: str, marker: str) -> Any:
    marker_index = raw.find(marker)
    if marker_index < 0:
        return None
    object_index = raw.find("{", marker_index)
    if object_index < 0:
        return None
    try:
        parsed, _ = json.JSONDecoder().raw_decode(raw[object_index:])
    except json.JSONDecodeError:
        return None
    return parsed


def _kis_smoke_markdown(raw: str) -> dict[str, Any] | None:
    keys = (
        "run_id",
        "commit",
        "trigger",
        "timestamp_utc",
        "secrets_present",
        "key_valid",
        "smoke_state",
        "smoke_exit",
    )
    parsed = {
        key: value
        for key in keys
        if (value := _markdown_table_value(raw, key)) is not None
    }
    return parsed or None


def _markdown_table_value(text: str, key: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "|" not in stripped[1:]:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == key:
            return cells[1]
    return None


def _items(parsed: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(parsed, Mapping):
        return []
    raw = parsed.get(key)
    if isinstance(raw, Mapping):
        if all(isinstance(value, Mapping) for value in raw.values()):
            return [
                {"key": str(item_key), **value}
                for item_key, value in raw.items()
                if isinstance(value, Mapping)
            ]
        return [dict(raw)]
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _mapping_value(parsed: Any, key: str) -> Any:
    return parsed.get(key) if isinstance(parsed, Mapping) else None


def _lookup(parsed: Any, key: str, default: Any) -> Any:
    if isinstance(parsed, Mapping):
        if key in parsed:
            return parsed[key]
        for value in parsed.values():
            found = _lookup(value, key, None)
            if found is not None:
                return found
    elif isinstance(parsed, list):
        for value in parsed:
            found = _lookup(value, key, None)
            if found is not None:
                return found
    return default


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _none_if_blank(value: object) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _int(value: Any, default: int) -> int:
    parsed = _int_or_none(value)
    return parsed if parsed is not None else default


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return None


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


__all__ = [
    "BLOCKED",
    "COMPLETED_CANDIDATE_ID",
    "CONTRACT_READY",
    "COST_BASIS_BLOCKED",
    "COST_BASIS_OBSERVATION_WAIT",
    "COST_BASIS_READY",
    "ExecutionCostBasisReport",
    "EvidenceSurface",
    "GATE_FAIL",
    "GATE_PASS",
    "GATE_WAIT",
    "NEXT_AUTONOMOUS_CANDIDATE_ID",
    "OBSERVATION_WAIT",
    "QualityGate",
    "REQUIRED_INPUTS",
    "SAFETY_INVARIANTS",
    "SCHEMA_VERSION",
    "build_execution_cost_basis_report",
    "read_evidence_manifest",
    "read_repo_sidecars",
]
