"""스펙 105 - 브로커 진단 생존성 계약.

이미 발행된 sidecar 스냅샷만 읽어 KIS smoke, execution-quality, pipeline
liveness가 브로커 진단 증거를 살아 있게 유지하는지 판정한다. 브로커 API,
주문, 자본 배분, live 설정, whitelist/caps, 비밀값, 헌법/커널, 외부 유료
서비스는 건드리지 않는다.
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
PARSE_MISSING = "missing"
PARSE_MALFORMED = "malformed"

GATE_PASS = "PASS"
GATE_WAIT = "WAIT"
GATE_FAIL = "FAIL"

BROKER_DIAGNOSTIC_LIVE = "BROKER_DIAGNOSTIC_LIVE"
BROKER_DIAGNOSTIC_OBSERVATION_WAIT = "BROKER_DIAGNOSTIC_OBSERVATION_WAIT"
BROKER_DIAGNOSTIC_BLOCKED = "BROKER_DIAGNOSTIC_BLOCKED"

COMPLETED_CANDIDATE_ID = "candidate-broker-diagnostic-liveness-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "candidate-agent-ops-frontier-map"

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("kis-smoke", "automation/kis-smoke-last-run:LAST_RUN.md"),
    ("execution-quality", "automation/execution-quality-last-run:LAST_RUN.md"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run:LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
    (
        "capital-path-readiness",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
    ),
)

_REPO_SIDECAR_PATHS: Mapping[str, str] = {
    "kis-smoke": "automation/kis-smoke-last-run/LAST_RUN.md",
    "execution-quality": "automation/execution-quality-last-run/LAST_RUN.md",
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
    "read-only broker diagnostic liveness contract only",
)

_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(?P<body>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_JSON_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)
_RELEASED_STATUSES = {"released", "release", "complete", "completed", "done"}
_READY_PIPELINE_STATUSES = {"OK", "PASS", "PASSED", "SUCCESS"}
_FAIL_PIPELINE_STATUSES = {
    "CRITICAL",
    "FAIL",
    "FAILED",
    "ERROR",
    "STALE",
    "MISSING",
    "BLOCKED",
}
_RELEVANT_PIPELINE_KEYS = {"kis-smoke", "execution-quality"}


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
    """브로커 진단 생존성 계약 조건 하나의 판정."""

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
class BrokerDiagnosticLivenessReport:
    """브로커 진단 생존성 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    kis_smoke_summary: dict[str, Any]
    execution_quality_summary: dict[str, Any]
    pipeline_liveness_summary: dict[str, Any]
    diagnostic_summary: dict[str, Any]
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
            "kis_smoke_summary": self.kis_smoke_summary,
            "execution_quality_summary": self.execution_quality_summary,
            "pipeline_liveness_summary": self.pipeline_liveness_summary,
            "diagnostic_summary": self.diagnostic_summary,
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "capital_path_summary": self.capital_path_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 브로커 진단 생존성 계약 (as of {self.timestamp_utc})",
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
            f"| diagnostic_state | {self.diagnostic_summary.get('diagnostic_state')} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| next_candidate_id | {self.next_candidate_id} |",
        ]

        lines += ["", "## 브로커 진단 생존성 요약", ""]
        lines += ["| 항목 | 값 |", "|------|-----|"]
        for key in (
            "kis_smoke_success",
            "key_valid",
            "smoke_exit",
            "tests_total",
            "tests_failed",
            "execution_quality_has_broker_smoke",
            "execution_quality_smoke_success",
            "pipeline_overall",
            "summary_ko",
        ):
            lines.append(f"| {key} | {_table(self.diagnostic_summary.get(key))} |")

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


def build_broker_diagnostic_liveness_report(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> BrokerDiagnosticLivenessReport:
    """수집된 sidecar 원문으로 브로커 진단 생존성 계약을 만든다."""

    now = _as_utc(now)
    parsed = {key: _parse_for_key(key, evidence_texts.get(key)) for key, _ in REQUIRED_INPUTS}
    surfaces = tuple(
        _surface_for(key, source_ref, evidence_texts.get(key), parsed[key])
        for key, source_ref in REQUIRED_INPUTS
    )
    kis_summary = _kis_smoke_summary(parsed["kis-smoke"])
    execution_summary = _execution_quality_summary(parsed["execution-quality"])
    pipeline_summary = _pipeline_liveness_summary(parsed["pipeline-liveness"])
    gates = (
        _required_evidence_gate(surfaces),
        _kis_smoke_health_gate(kis_summary),
        _execution_quality_broker_smoke_gate(execution_summary),
        _pipeline_liveness_gate(pipeline_summary),
        _safety_boundary_gate(),
    )
    overall = _overall_status(gates)
    diagnostic = _diagnostic_summary(
        overall_status=overall,
        kis_summary=kis_summary,
        execution_summary=execution_summary,
        pipeline_summary=pipeline_summary,
    )

    return BrokerDiagnosticLivenessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=overall,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_AUTONOMOUS_CANDIDATE_ID,
        evidence_surfaces=surfaces,
        kis_smoke_summary=kis_summary,
        execution_quality_summary=execution_summary,
        pipeline_liveness_summary=pipeline_summary,
        diagnostic_summary=diagnostic,
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
    if key in {"execution-quality", "pipeline-liveness"}:
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
        PARSE_OK,
        _summary_for(key, parsed),
    )


def _kis_smoke_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, Mapping):
        return {
            "parseable": False,
            "smoke_state": None,
            "smoke_exit": None,
            "key_valid": None,
            "tests_total": 0,
            "tests_failed": 0,
            "timestamp_utc": None,
            "healthy": False,
        }
    smoke_state = _none_if_blank(parsed.get("smoke_state"))
    smoke_exit = _int_or_none(parsed.get("smoke_exit"))
    key_valid = _bool_or_none(parsed.get("key_valid"))
    tests_total = _int(parsed.get("tests_total"), 0)
    tests_failed = _int(parsed.get("tests_failed"), 0)
    healthy = (
        str(smoke_state or "").lower() == "success"
        and smoke_exit == 0
        and key_valid is True
        and tests_failed == 0
    )
    return {
        "parseable": True,
        "smoke_state": smoke_state,
        "smoke_exit": smoke_exit,
        "key_valid": key_valid,
        "tests_total": tests_total,
        "tests_failed": tests_failed,
        "timestamp_utc": _none_if_blank(parsed.get("timestamp_utc")),
        "healthy": healthy,
    }


def _execution_quality_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, Mapping):
        return {
            "parseable": False,
            "overall_status": None,
            "has_broker_smoke": False,
            "broker_smoke_success": None,
            "broker_smoke": {},
        }
    broker_smoke = _mapping_value(parsed, "broker_smoke")
    has_broker_smoke = isinstance(broker_smoke, Mapping)
    smoke = broker_smoke if isinstance(broker_smoke, Mapping) else {}
    smoke_state = _none_if_blank(smoke.get("smoke_state"))
    smoke_exit = _int_or_none(smoke.get("smoke_exit"))
    key_valid = _bool_or_none(smoke.get("key_valid"))
    tests_failed = _int(smoke.get("tests_failed"), 0)
    smoke_success = (
        str(smoke_state or "").lower() == "success"
        and smoke_exit == 0
        and key_valid is True
        and tests_failed == 0
    )
    return {
        "parseable": True,
        "overall_status": parsed.get("overall_status"),
        "has_broker_smoke": has_broker_smoke,
        "broker_smoke_success": smoke_success if has_broker_smoke else None,
        "broker_smoke": {
            "smoke_state": smoke_state,
            "smoke_exit": smoke_exit,
            "key_valid": key_valid,
            "tests_total": _int(smoke.get("tests_total"), 0),
            "tests_failed": tests_failed,
            "timestamp_utc": _none_if_blank(smoke.get("timestamp_utc")),
        },
    }


def _pipeline_liveness_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, Mapping):
        return {
            "parseable": False,
            "overall": None,
            "relevant_checks": [],
            "missing_relevant_checks": sorted(_RELEVANT_PIPELINE_KEYS),
            "has_failure": False,
            "all_relevant_ok": False,
        }
    checks = [
        check
        for check in _items(parsed, "checks")
        if str(check.get("key") or "") in _RELEVANT_PIPELINE_KEYS
    ]
    present = {str(check.get("key") or "") for check in checks}
    missing = sorted(_RELEVANT_PIPELINE_KEYS - present)
    relevant = [_pipeline_check_summary(check) for check in checks]
    has_failure = any(check["is_failure"] for check in relevant)
    all_relevant_ok = (
        not missing
        and bool(relevant)
        and all(check["is_ok"] for check in relevant)
        and _status(parsed.get("overall") or parsed.get("overall_status"))
        in _READY_PIPELINE_STATUSES
    )
    return {
        "parseable": True,
        "overall": parsed.get("overall") or parsed.get("overall_status"),
        "relevant_checks": relevant,
        "missing_relevant_checks": missing,
        "has_failure": has_failure,
        "all_relevant_ok": all_relevant_ok,
    }


def _pipeline_check_summary(check: Mapping[str, Any]) -> dict[str, Any]:
    status = _status(check.get("status"))
    is_failure = (
        status in _FAIL_PIPELINE_STATUSES
        or _bool_or_none(check.get("critical")) is True
        and status not in _READY_PIPELINE_STATUSES
    )
    return {
        "key": str(check.get("key") or ""),
        "status": status,
        "critical": _bool_or_none(check.get("critical")),
        "age_hours": _float_or_none(check.get("age_hours")),
        "max_age_hours": _float_or_none(check.get("max_age_hours")),
        "timestamp_utc": _none_if_blank(check.get("timestamp_utc")),
        "detail": _none_if_blank(check.get("detail")),
        "is_ok": status in _READY_PIPELINE_STATUSES,
        "is_failure": is_failure,
    }


def _diagnostic_summary(
    *,
    overall_status: str,
    kis_summary: Mapping[str, Any],
    execution_summary: Mapping[str, Any],
    pipeline_summary: Mapping[str, Any],
) -> dict[str, Any]:
    if overall_status == BLOCKED:
        state = BROKER_DIAGNOSTIC_BLOCKED
        summary = "브로커 진단 증거가 실패 또는 결손 상태라 복구가 필요하다."
    elif overall_status == OBSERVATION_WAIT:
        state = BROKER_DIAGNOSTIC_OBSERVATION_WAIT
        summary = "브로커 진단의 일부 cross-surface 증거가 아직 충분히 연결되지 않았다."
    else:
        state = BROKER_DIAGNOSTIC_LIVE
        summary = "KIS smoke, execution-quality broker smoke, pipeline liveness가 모두 살아 있다."
    broker_smoke = execution_summary.get("broker_smoke")
    broker_smoke = broker_smoke if isinstance(broker_smoke, Mapping) else {}
    return {
        "diagnostic_state": state,
        "kis_smoke_success": kis_summary.get("healthy"),
        "key_valid": kis_summary.get("key_valid"),
        "smoke_exit": kis_summary.get("smoke_exit"),
        "tests_total": kis_summary.get("tests_total"),
        "tests_failed": kis_summary.get("tests_failed"),
        "execution_quality_has_broker_smoke": execution_summary.get("has_broker_smoke"),
        "execution_quality_smoke_success": execution_summary.get("broker_smoke_success"),
        "execution_quality_smoke_exit": broker_smoke.get("smoke_exit"),
        "pipeline_overall": pipeline_summary.get("overall"),
        "pipeline_relevant_checks": pipeline_summary.get("relevant_checks", []),
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


def _kis_smoke_health_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            "kis_smoke_health",
            GATE_FAIL,
            "KIS smoke를 읽을 수 없다.",
            ("kis-smoke",),
        )
    if summary.get("key_valid") is False:
        return QualityGate(
            "kis_smoke_health",
            GATE_FAIL,
            "KIS smoke가 key_valid=false를 보고했다.",
            ("kis-smoke",),
        )
    if summary.get("key_valid") is None:
        return QualityGate(
            "kis_smoke_health",
            GATE_WAIT,
            "KIS key validity가 구조화 증거에 없다.",
            ("kis-smoke",),
        )
    if summary.get("healthy"):
        return QualityGate(
            "kis_smoke_health",
            GATE_PASS,
            "KIS smoke가 success/exit 0/key valid/test 실패 0건이다.",
            ("kis-smoke",),
        )
    return QualityGate(
        "kis_smoke_health",
        GATE_FAIL,
        (
            "KIS smoke가 건강하지 않다: "
            f"state={summary.get('smoke_state')}, exit={summary.get('smoke_exit')}, "
            f"tests_failed={summary.get('tests_failed')}"
        ),
        ("kis-smoke",),
    )


def _execution_quality_broker_smoke_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            "execution_quality_broker_smoke",
            GATE_FAIL,
            "execution-quality를 읽을 수 없다.",
            ("execution-quality",),
        )
    if not summary.get("has_broker_smoke"):
        return QualityGate(
            "execution_quality_broker_smoke",
            GATE_WAIT,
            "execution-quality에 broker_smoke 요약이 아직 없다.",
            ("execution-quality",),
        )
    if summary.get("broker_smoke_success"):
        return QualityGate(
            "execution_quality_broker_smoke",
            GATE_PASS,
            "execution-quality 안의 broker_smoke가 성공 상태다.",
            ("execution-quality",),
        )
    return QualityGate(
        "execution_quality_broker_smoke",
        GATE_FAIL,
        "execution-quality 안의 broker_smoke가 실패 상태다.",
        ("execution-quality",),
    )


def _pipeline_liveness_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            "pipeline_broker_diagnostic_liveness",
            GATE_FAIL,
            "pipeline-liveness를 읽을 수 없다.",
            ("pipeline-liveness",),
        )
    if summary.get("has_failure"):
        return QualityGate(
            "pipeline_broker_diagnostic_liveness",
            GATE_FAIL,
            "pipeline-liveness가 KIS smoke 또는 execution-quality 장애를 보고했다.",
            ("pipeline-liveness",),
        )
    missing = summary.get("missing_relevant_checks") or []
    if missing:
        return QualityGate(
            "pipeline_broker_diagnostic_liveness",
            GATE_WAIT,
            f"pipeline-liveness 관련 체크가 부족하다: {', '.join(missing)}",
            ("pipeline-liveness",),
        )
    if summary.get("all_relevant_ok"):
        return QualityGate(
            "pipeline_broker_diagnostic_liveness",
            GATE_PASS,
            "pipeline-liveness가 KIS smoke와 execution-quality를 OK로 보고했다.",
            ("pipeline-liveness",),
        )
    return QualityGate(
        "pipeline_broker_diagnostic_liveness",
        GATE_WAIT,
        f"pipeline-liveness overall={summary.get('overall')} 상태라 추가 관측이 필요하다.",
        ("pipeline-liveness",),
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
    if not isinstance(parsed, Mapping):
        return "구조화 값 존재"
    if key == "kis-smoke":
        return f"state={parsed.get('smoke_state')}, exit={parsed.get('smoke_exit')}"
    if key == "execution-quality":
        smoke = _mapping_value(parsed, "broker_smoke")
        return (
            f"overall={parsed.get('overall_status')}, "
            f"broker_smoke_present={isinstance(smoke, Mapping)}"
        )
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


def _kis_smoke_markdown(raw: str) -> dict[str, Any] | None:
    values: dict[str, Any] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= {"-"}:
            continue
        key, value = cells[0], cells[1]
        if key in {"항목", "변수"}:
            continue
        if key:
            values[key] = value
    if not values:
        return None
    return values


def _read_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _mapping_value(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, Mapping) else None


def _items(value: Any, key: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    items = value.get(key)
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, Mapping)]


def _lookup(value: Any, key: str, default: Any) -> Any:
    if isinstance(value, Mapping):
        if key in value:
            return value[key]
        for child in value.values():
            found = _lookup(child, key, None)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _lookup(child, key, None)
            if found is not None:
                return found
    return default


def _int(value: Any, default: int) -> int:
    parsed = _int_or_none(value)
    return default if parsed is None else parsed


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "ok", "success", "설정됨"}:
            return True
        if lowered in {"false", "no", "n", "0", "fail", "failed", "none", "없음"}:
            return False
    return None


def _none_if_blank(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _status(value: Any) -> str:
    return str(value or "").strip().upper()


def _table(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")
