"""스펙 101 — 데이터 증거 생존성 계약.

기존 sidecar 스냅샷만 읽어 `collect-public-data`와 `regime-stratify`
생존 상태를 데이터 품질 후보 관점의 PASS/WAIT/FAIL 계약으로 분리한다.
읽기 전용이며 브로커, 주문, 자본 배분, live 설정, whitelist/caps,
비밀값, 외부 유료 서비스를 건드리지 않는다.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.pipeline_liveness import OK, default_specs, parse_timestamp_utc

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

COMPLETED_CANDIDATE_ID = "candidate-data-evidence-liveness-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "candidate-execution-quality-frontier-map"

DATA_CHECK_SOURCE_KEYS: Mapping[str, str] = {
    "collect-public-data": "public-data-last-run",
    "regime-stratify": "regime-stratify",
}
REQUIRED_DATA_CHECKS: tuple[str, ...] = tuple(DATA_CHECK_SOURCE_KEYS)

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("public-data-last-run", "automation/public-data:LAST_RUN.md"),
    ("public-data-summary", "automation/public-data:summary.json"),
    ("public-data-regime", "automation/public-data:regime.json"),
    ("public-data-regime-timeline", "automation/public-data:regime_timeline.csv"),
    ("regime-stratify", "automation/regime-stratify-last-run:LAST_RUN.md"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run:LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
    (
        "capital-path-readiness",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
    ),
)

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
    "read-only data evidence liveness contract only",
)

_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(?P<body>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_JSON_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)
_DEFAULT_SPECS = {spec.key: spec for spec in default_specs()}
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
    """생존성 조건 하나의 판정."""

    key: str
    status: str
    summary_ko: str
    evidence_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status,
            "summary_ko": self.summary_ko,
            "evidence_keys": list(self.evidence_keys),
        }


@dataclass(frozen=True)
class SourceSidecarObservation:
    """pipeline-liveness check를 뒷받침하는 직접 source sidecar 관측."""

    key: str
    check_key: str
    present: bool
    parse_status: str
    timestamp_utc: str | None
    age_hours: float | None
    max_age_hours: float
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "check_key": self.check_key,
            "present": self.present,
            "parse_status": self.parse_status,
            "timestamp_utc": self.timestamp_utc,
            "age_hours": (
                round(self.age_hours, 2) if self.age_hours is not None else None
            ),
            "max_age_hours": self.max_age_hours,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class DataLivenessCheck:
    """데이터 sidecar 한 개의 생존성 계약 관측."""

    key: str
    status: str
    critical: bool
    age_hours: float | None
    max_age_hours: float
    pipeline_timestamp_utc: str | None
    source_timestamp_utc: str | None
    source_matches_pipeline: bool | None
    summary_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status,
            "critical": self.critical,
            "age_hours": (
                round(self.age_hours, 2) if self.age_hours is not None else None
            ),
            "max_age_hours": self.max_age_hours,
            "pipeline_timestamp_utc": self.pipeline_timestamp_utc,
            "source_timestamp_utc": self.source_timestamp_utc,
            "source_matches_pipeline": self.source_matches_pipeline,
            "summary_ko": self.summary_ko,
        }


@dataclass(frozen=True)
class DataEvidenceLivenessReport:
    """데이터 증거 생존성 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    data_liveness_checks: tuple[DataLivenessCheck, ...]
    source_observations: tuple[SourceSidecarObservation, ...]
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
            "data_liveness_checks": [
                check.to_dict() for check in self.data_liveness_checks
            ],
            "source_observations": [
                observation.to_dict() for observation in self.source_observations
            ],
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "capital_path_summary": self.capital_path_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 데이터 증거 생존성 계약 (as of {self.timestamp_utc})",
            "",
            (
                "기존 sidecar 스냅샷만 읽는 보고입니다. 주문, 자본 배분, live 설정, "
                "외부 데이터 새 수집은 하지 않습니다."
            ),
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| next_candidate_id | {self.next_candidate_id} |",
        ]

        lines += ["", "## 검증 게이트", ""]
        lines += ["| 게이트 | 상태 | 요약 |", "|--------|------|------|"]
        for gate in self.quality_gates:
            lines.append(
                f"| {_table(gate.key)} | {gate.status} | {_table(gate.summary_ko)} |"
            )

        lines += ["", "## 데이터 생존성 체크", ""]
        lines += [
            "| 체크 | 상태 | 나이(h) | 한계(h) | pipeline timestamp | source timestamp |",
            "|------|------|--------:|--------:|--------------------|------------------|",
        ]
        for check in self.data_liveness_checks:
            age = f"{check.age_hours:.2f}" if check.age_hours is not None else ""
            lines.append(
                f"| {_table(check.key)} | {check.status} | {age} | "
                f"{check.max_age_hours:.0f} | {_table(check.pipeline_timestamp_utc)} | "
                f"{_table(check.source_timestamp_utc)} |"
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


def build_data_evidence_liveness_report(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> DataEvidenceLivenessReport:
    """수집된 sidecar 원문으로 데이터 증거 생존성 계약을 만든다."""

    now = _as_utc(now)
    parsed = {key: _parse_for_key(key, evidence_texts.get(key)) for key, _ in REQUIRED_INPUTS}
    surfaces = tuple(
        _surface_for(key, source_ref, evidence_texts.get(key), parsed[key])
        for key, source_ref in REQUIRED_INPUTS
    )

    pipeline_checks = _pipeline_checks(parsed["pipeline-liveness"])
    source_observations = tuple(
        _source_observation(
            source_key=source_key,
            check_key=check_key,
            raw=evidence_texts.get(source_key),
            now=now,
        )
        for check_key, source_key in DATA_CHECK_SOURCE_KEYS.items()
    )
    observations_by_check = {
        observation.check_key: observation for observation in source_observations
    }
    data_liveness_checks = tuple(
        _data_liveness_check(
            check_key,
            pipeline_checks.get(check_key),
            observations_by_check[check_key],
        )
        for check_key in REQUIRED_DATA_CHECKS
    )
    released_work_summary = _released_work_summary(parsed["released-work"])
    capital_path_summary = _capital_path_summary(parsed["capital-path-readiness"])

    gates = (
        _pipeline_report_gate(parsed["pipeline-liveness"]),
        _data_check_registration_gate(pipeline_checks),
        _data_liveness_status_gate(data_liveness_checks),
        _source_timestamp_consistency_gate(data_liveness_checks),
        _source_freshness_gate(data_liveness_checks, source_observations),
        _safety_boundary_gate(),
    )

    return DataEvidenceLivenessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=_overall_status(gates),
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_AUTONOMOUS_CANDIDATE_ID,
        evidence_surfaces=surfaces,
        data_liveness_checks=data_liveness_checks,
        source_observations=source_observations,
        quality_gates=gates,
        released_work_summary=released_work_summary,
        capital_path_summary=capital_path_summary,
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

    paths = {
        "public-data-last-run": "automation/public-data/LAST_RUN.md",
        "public-data-summary": "automation/public-data/summary.json",
        "public-data-regime": "automation/public-data/regime.json",
        "public-data-regime-timeline": "automation/public-data/regime_timeline.csv",
        "regime-stratify": "automation/regime-stratify-last-run/LAST_RUN.md",
        "pipeline-liveness": "automation/pipeline-liveness-last-run/LAST_RUN.md",
        "released-work": "automation/released-work-last-run/released_work.json",
        "capital-path-readiness": (
            "automation/capital-path-readiness-last-run/capital_path_readiness.json"
        ),
    }
    return {key: _read_optional(repo_root / path) for key, path in paths.items()}


def _parse_for_key(key: str, raw: str | None) -> Any:
    if raw is None:
        return None
    if key == "public-data-regime-timeline":
        return _parse_csv_rows(raw)
    if key in {"public-data-last-run", "regime-stratify"}:
        timestamp = parse_timestamp_utc(raw)
        return {"timestamp_utc": timestamp} if timestamp is not None else None
    if key == "pipeline-liveness":
        return _parse_markdown_json(raw)
    return _parse_json(raw)


def _surface_for(
    key: str,
    source_ref: str,
    raw: str | None,
    parsed: Any,
) -> EvidenceSurface:
    if raw is None:
        return EvidenceSurface(
            key=key,
            source_ref=source_ref,
            present=False,
            parse_status=PARSE_MISSING,
            summary_ko="sidecar 파일 없음",
        )
    if parsed is None:
        return EvidenceSurface(
            key=key,
            source_ref=source_ref,
            present=True,
            parse_status=PARSE_MALFORMED,
            summary_ko="원문은 있으나 구조화 파싱 실패",
        )
    return EvidenceSurface(
        key=key,
        source_ref=source_ref,
        present=True,
        parse_status=PARSE_OK if isinstance(parsed, (dict, list)) else PARSE_PRESENT,
        summary_ko=_summary_for(key, parsed),
    )


def _pipeline_checks(parsed: Any) -> dict[str, Mapping[str, Any]]:
    if not isinstance(parsed, dict):
        return {}
    checks: dict[str, Mapping[str, Any]] = {}
    for item in _items(parsed, "checks"):
        key = str(item.get("key") or item.get("name") or "")
        if key:
            checks[key] = item
    return checks


def _source_observation(
    *,
    source_key: str,
    check_key: str,
    raw: str | None,
    now: datetime,
) -> SourceSidecarObservation:
    spec = _DEFAULT_SPECS[check_key]
    if raw is None:
        return SourceSidecarObservation(
            key=source_key,
            check_key=check_key,
            present=False,
            parse_status=PARSE_MISSING,
            timestamp_utc=None,
            age_hours=None,
            max_age_hours=spec.max_age_hours,
            summary_ko="source LAST_RUN 파일 없음",
        )
    timestamp = parse_timestamp_utc(raw)
    if timestamp is None:
        return SourceSidecarObservation(
            key=source_key,
            check_key=check_key,
            present=True,
            parse_status=PARSE_MALFORMED,
            timestamp_utc=None,
            age_hours=None,
            max_age_hours=spec.max_age_hours,
            summary_ko="source LAST_RUN timestamp를 파싱할 수 없음",
        )
    age_hours = _age_hours(timestamp, now)
    return SourceSidecarObservation(
        key=source_key,
        check_key=check_key,
        present=True,
        parse_status=PARSE_OK,
        timestamp_utc=timestamp,
        age_hours=age_hours,
        max_age_hours=spec.max_age_hours,
        summary_ko=f"timestamp={timestamp}, age_hours={age_hours:.2f}",
    )


def _data_liveness_check(
    check_key: str,
    item: Mapping[str, Any] | None,
    source_observation: SourceSidecarObservation,
) -> DataLivenessCheck:
    spec = _DEFAULT_SPECS[check_key]
    if item is None:
        return DataLivenessCheck(
            key=check_key,
            status="MISSING_CHECK",
            critical=spec.critical,
            age_hours=None,
            max_age_hours=spec.max_age_hours,
            pipeline_timestamp_utc=None,
            source_timestamp_utc=source_observation.timestamp_utc,
            source_matches_pipeline=None,
            summary_ko="pipeline-liveness에 필수 데이터 check가 없음",
        )

    pipeline_timestamp = _check_timestamp(item)
    source_timestamp = source_observation.timestamp_utc
    source_matches = (
        pipeline_timestamp == source_timestamp
        if pipeline_timestamp is not None and source_timestamp is not None
        else None
    )
    status = str(item.get("status") or "")
    age_hours = _float_or_none(item.get("age_hours"))
    max_age_hours = _float_or_none(item.get("max_age_hours")) or spec.max_age_hours
    if status == OK and source_matches is True:
        summary_ko = f"{check_key} OK, source timestamp 일치"
    elif status == OK:
        summary_ko = f"{check_key} OK이나 source timestamp 감사 불가"
    else:
        summary_ko = f"{check_key} 상태 {status or '(없음)'}"
    return DataLivenessCheck(
        key=check_key,
        status=status,
        critical=bool(item.get("critical", spec.critical)),
        age_hours=age_hours,
        max_age_hours=max_age_hours,
        pipeline_timestamp_utc=pipeline_timestamp,
        source_timestamp_utc=source_timestamp,
        source_matches_pipeline=source_matches,
        summary_ko=summary_ko,
    )


def _pipeline_report_gate(parsed: Any) -> QualityGate:
    if not isinstance(parsed, dict):
        return QualityGate(
            key="pipeline_report_parse",
            status=GATE_FAIL,
            summary_ko="pipeline-liveness 결정 JSON을 파싱할 수 없다.",
            evidence_keys=("pipeline-liveness",),
        )
    return QualityGate(
        key="pipeline_report_parse",
        status=GATE_PASS,
        summary_ko=(
            "pipeline-liveness "
            f"overall={parsed.get('overall') or parsed.get('overall_status')}"
        ),
        evidence_keys=("pipeline-liveness",),
    )


def _data_check_registration_gate(
    pipeline_checks: Mapping[str, Mapping[str, Any]],
) -> QualityGate:
    missing = [key for key in REQUIRED_DATA_CHECKS if key not in pipeline_checks]
    if missing:
        return QualityGate(
            key="data_check_registration",
            status=GATE_FAIL,
            summary_ko=f"pipeline-liveness 필수 check 누락: {', '.join(missing)}",
            evidence_keys=("pipeline-liveness",),
        )
    return QualityGate(
        key="data_check_registration",
        status=GATE_PASS,
        summary_ko="collect-public-data와 regime-stratify check가 등록돼 있다.",
        evidence_keys=("pipeline-liveness",),
    )


def _data_liveness_status_gate(
    checks: tuple[DataLivenessCheck, ...],
) -> QualityGate:
    missing = [check.key for check in checks if check.status == "MISSING_CHECK"]
    if missing:
        return QualityGate(
            key="data_liveness_status",
            status=GATE_FAIL,
            summary_ko=f"생존성 판정에 필요한 check가 없다: {', '.join(missing)}",
            evidence_keys=("pipeline-liveness",),
        )
    non_ok = [check.key for check in checks if check.status != OK]
    if non_ok:
        return QualityGate(
            key="data_liveness_status",
            status=GATE_WAIT,
            summary_ko=f"데이터 sidecar 생존성 대기: {', '.join(non_ok)}",
            evidence_keys=("pipeline-liveness",),
        )
    return QualityGate(
        key="data_liveness_status",
        status=GATE_PASS,
        summary_ko="collect-public-data와 regime-stratify check가 모두 OK다.",
        evidence_keys=("pipeline-liveness",),
    )


def _source_timestamp_consistency_gate(
    checks: tuple[DataLivenessCheck, ...],
) -> QualityGate:
    failures: list[str] = []
    waits: list[str] = []
    for check in checks:
        if check.status == "MISSING_CHECK":
            failures.append(f"{check.key}: pipeline check 없음")
            continue
        if check.pipeline_timestamp_utc and check.source_timestamp_utc:
            if check.pipeline_timestamp_utc != check.source_timestamp_utc:
                failures.append(f"{check.key}: pipeline/source timestamp 불일치")
            continue
        if check.status == OK:
            if check.pipeline_timestamp_utc is None:
                failures.append(f"{check.key}: OK check timestamp 없음")
            if check.source_timestamp_utc is None:
                failures.append(f"{check.key}: OK source timestamp 없음")
        else:
            waits.append(check.key)

    if failures:
        return QualityGate(
            key="source_timestamp_consistency",
            status=GATE_FAIL,
            summary_ko="; ".join(failures),
            evidence_keys=("pipeline-liveness", "public-data-last-run", "regime-stratify"),
        )
    if waits:
        return QualityGate(
            key="source_timestamp_consistency",
            status=GATE_WAIT,
            summary_ko=(
                "비 OK check는 source timestamp 완전 일치를 요구하지 않고 "
                f"관측 대기로 둔다: {', '.join(waits)}"
            ),
            evidence_keys=("pipeline-liveness", "public-data-last-run", "regime-stratify"),
        )
    return QualityGate(
        key="source_timestamp_consistency",
        status=GATE_PASS,
        summary_ko="데이터 check timestamp가 source LAST_RUN timestamp와 일치한다.",
        evidence_keys=("pipeline-liveness", "public-data-last-run", "regime-stratify"),
    )


def _source_freshness_gate(
    checks: tuple[DataLivenessCheck, ...],
    observations: tuple[SourceSidecarObservation, ...],
) -> QualityGate:
    checks_by_key = {check.key: check for check in checks}
    failures: list[str] = []
    waits: list[str] = []
    for observation in observations:
        check = checks_by_key[observation.check_key]
        if observation.timestamp_utc is None:
            if check.status == OK:
                failures.append(f"{observation.key}: OK source timestamp 없음")
            else:
                waits.append(observation.key)
            continue
        if (
            observation.age_hours is not None
            and observation.age_hours > observation.max_age_hours
        ):
            waits.append(observation.key)

    if failures:
        return QualityGate(
            key="source_freshness",
            status=GATE_FAIL,
            summary_ko="; ".join(failures),
            evidence_keys=("public-data-last-run", "regime-stratify"),
        )
    if waits:
        return QualityGate(
            key="source_freshness",
            status=GATE_WAIT,
            summary_ko=f"source sidecar freshness 대기: {', '.join(waits)}",
            evidence_keys=("public-data-last-run", "regime-stratify"),
        )
    return QualityGate(
        key="source_freshness",
        status=GATE_PASS,
        summary_ko="직접 source LAST_RUN timestamp도 기대 주기 안에 있다.",
        evidence_keys=("public-data-last-run", "regime-stratify"),
    )


def _safety_boundary_gate() -> QualityGate:
    return QualityGate(
        key="safety_boundary",
        status=GATE_PASS,
        summary_ko="읽기 전용 계약이며 브로커, 주문, 자본, live 설정, 비밀값을 건드리지 않는다.",
        evidence_keys=(),
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
        "parseable": isinstance(parsed, dict),
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "completed_candidate_released": COMPLETED_CANDIDATE_ID in released,
        "released_count": len(released),
    }


def _capital_path_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
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


def _check_timestamp(item: Mapping[str, Any]) -> str | None:
    for key in ("timestamp_utc", "last_success_utc"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


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
    for body in reversed(matches):
        parsed = _parse_json(body.strip())
        if parsed is not None:
            return parsed
        match = _JSON_OBJECT_RE.search(body)
        if match:
            parsed = _parse_json(match.group(1))
            if parsed is not None:
                return parsed
    return None


def _parse_csv_rows(raw: str) -> list[dict[str, str]] | None:
    try:
        return list(csv.DictReader(io.StringIO(raw)))
    except csv.Error:
        return None


def _items(parsed: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(parsed, dict):
        return []
    raw = parsed.get(key)
    if isinstance(raw, dict):
        if all(isinstance(value, dict) for value in raw.values()):
            return [
                {"key": str(item_key), **value}
                for item_key, value in raw.items()
                if isinstance(value, dict)
            ]
        return [raw]
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _lookup(parsed: Any, key: str, default: Any) -> Any:
    if isinstance(parsed, dict):
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


def _summary_for(key: str, parsed: Any) -> str:
    if key == "public-data-regime-timeline" and isinstance(parsed, list):
        return f"timeline_rows={len(parsed)}"
    if key in {"public-data-last-run", "regime-stratify"} and isinstance(parsed, dict):
        return f"timestamp_utc={parsed.get('timestamp_utc')}"
    if isinstance(parsed, list):
        return f"목록 {len(parsed)}개"
    if not isinstance(parsed, dict):
        return "구조화 값 존재"
    if key == "public-data-summary":
        return (
            f"overall_ok={parsed.get('overall_ok')}, "
            f"published={parsed.get('published')}/{parsed.get('total_items')}"
        )
    if key == "public-data-regime":
        return (
            f"label={_lookup(parsed, 'overall_label', _lookup(parsed, 'label', None))}, "
            f"indicators={len(_items(parsed, 'indicators'))}"
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


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _age_hours(ts_str: str, now: datetime) -> float:
    parsed = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (now - parsed).total_seconds() / 3600.0


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


__all__ = [
    "BLOCKED",
    "COMPLETED_CANDIDATE_ID",
    "CONTRACT_READY",
    "DataEvidenceLivenessReport",
    "DataLivenessCheck",
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
    "SourceSidecarObservation",
    "build_data_evidence_liveness_report",
    "read_evidence_manifest",
    "read_repo_sidecars",
]
