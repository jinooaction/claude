"""스펙 100 — 레짐 타임라인 커버리지 계약.

기존 sidecar 스냅샷만 읽어 레짐 타임라인 라벨 커버리지, 레짐별 joined
return 관측 수, d+1 전망적 조인 품질을 판정한다. 읽기 전용이며 브로커,
주문, 자본 배분, live 설정, whitelist/caps, 비밀값, 외부 유료 서비스를
건드리지 않는다.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from auto_invest.analytics.regime_stratified import MIN_OBS_FOR_RATIOS

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

COMPLETED_CANDIDATE_ID = "candidate-regime-timeline-coverage-contract"
NEXT_DATA_EVIDENCE_CANDIDATE_ID = "candidate-data-evidence-liveness-contract"

MIN_TIMELINE_ROWS = 20
CANONICAL_LABELS = ("RISK_ON", "CAUTION", "RISK_OFF")
ALLOWED_DIAGNOSTIC_LABELS = ("UNLABELED",)

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("public-data-regime-timeline", "automation/public-data:regime_timeline.csv"),
    ("regime-stratify", "automation/regime-stratify-last-run:LAST_RUN.md"),
    ("pipeline-liveness", "automation/pipeline-liveness-last-run:LAST_RUN.md"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
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
    "read-only regime timeline coverage contract only",
)

_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(?P<body>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_STRATIFIED_MARKER = "--- stratified json ---"
_HEADING_RE = re.compile(r"^##\s+(?P<title>.+)$", re.MULTILINE)


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
    """입력 품질 조건 하나의 판정."""

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
class RegimeTimelineCoverageReport:
    """레짐 타임라인 커버리지 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    quality_gates: tuple[QualityGate, ...]
    timeline_summary: dict[str, Any]
    stratified_summary: dict[str, Any]
    liveness_summary: dict[str, Any]
    released_work_summary: dict[str, Any]
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
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "timeline_summary": self.timeline_summary,
            "stratified_summary": self.stratified_summary,
            "liveness_summary": self.liveness_summary,
            "released_work_summary": self.released_work_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 레짐 타임라인 커버리지 계약 (as of {self.timestamp_utc})",
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


def build_regime_timeline_coverage_report(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> RegimeTimelineCoverageReport:
    """수집된 sidecar 원문으로 레짐 타임라인 커버리지 계약을 만든다."""

    now = _as_utc(now)
    parsed = {key: _parse_for_key(key, evidence_texts.get(key)) for key, _ in REQUIRED_INPUTS}
    surfaces = tuple(
        _surface_for(key, source_ref, evidence_texts.get(key), parsed[key])
        for key, source_ref in REQUIRED_INPUTS
    )
    timeline_summary = _timeline_summary(parsed["public-data-regime-timeline"])
    stratified_summary = _stratified_summary(
        parsed["regime-stratify"],
        timeline_labels=timeline_summary.get("label_counts", {}),
    )
    liveness_summary = _liveness_summary(parsed["pipeline-liveness"])
    released_work_summary = _released_work_summary(parsed["released-work"])
    gates = (
        _timeline_shape_gate(timeline_summary),
        _timeline_label_coverage_gate(timeline_summary),
        _stratified_observation_gate(stratified_summary),
        _forward_join_gate(stratified_summary),
        _liveness_gate(liveness_summary),
    )

    return RegimeTimelineCoverageReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=_overall_status(gates),
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_DATA_EVIDENCE_CANDIDATE_ID,
        evidence_surfaces=surfaces,
        quality_gates=gates,
        timeline_summary=timeline_summary,
        stratified_summary=stratified_summary,
        liveness_summary=liveness_summary,
        released_work_summary=released_work_summary,
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
        "public-data-regime-timeline": "automation/public-data/regime_timeline.csv",
        "regime-stratify": "automation/regime-stratify-last-run/LAST_RUN.md",
        "pipeline-liveness": "automation/pipeline-liveness-last-run/LAST_RUN.md",
        "released-work": "automation/released-work-last-run/released_work.json",
    }
    return {key: _read_optional(repo_root / path) for key, path in paths.items()}


def _parse_for_key(key: str, raw: str | None) -> Any:
    if raw is None:
        return None
    if key == "public-data-regime-timeline":
        return _parse_csv_rows(raw)
    if key == "regime-stratify":
        return _parse_regime_stratify_sections(raw)
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
    if parsed is None or (key == "regime-stratify" and not parsed):
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
        parse_status=PARSE_OK,
        summary_ko=_summary_for(key, parsed),
    )


def _timeline_summary(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list):
        return _empty_timeline_summary(parseable=False)
    if not rows:
        return _empty_timeline_summary(parseable=True)

    labels: Counter[str] = Counter()
    dates: list[str] = []
    missing_label_rows: list[int] = []
    invalid_date_rows: list[int] = []
    duplicate_dates: list[str] = []
    out_of_order_dates: list[str] = []
    seen_dates: set[str] = set()
    previous_date: str | None = None

    for index, row in enumerate(rows, start=2):
        raw_date = str(row.get("date") or "").strip()
        raw_label = str(row.get("label") or "").strip()
        if not raw_label:
            missing_label_rows.append(index)
        else:
            labels[raw_label] += 1

        if not raw_date:
            invalid_date_rows.append(index)
            continue
        try:
            date.fromisoformat(raw_date)
        except ValueError:
            invalid_date_rows.append(index)
        if raw_date in seen_dates:
            duplicate_dates.append(raw_date)
        seen_dates.add(raw_date)
        if previous_date is not None and raw_date < previous_date:
            out_of_order_dates.append(raw_date)
        previous_date = raw_date
        dates.append(raw_date)

    canonical_present = [label for label in CANONICAL_LABELS if labels.get(label, 0) > 0]
    canonical_missing = [label for label in CANONICAL_LABELS if labels.get(label, 0) <= 0]
    return {
        "parseable": True,
        "row_count": len(rows),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "label_counts": dict(sorted(labels.items())),
        "canonical_labels_present": canonical_present,
        "canonical_labels_missing": canonical_missing,
        "missing_label_rows": missing_label_rows,
        "duplicate_dates": duplicate_dates,
        "invalid_date_rows": invalid_date_rows,
        "out_of_order_dates": out_of_order_dates,
        "out_of_order": bool(out_of_order_dates),
    }


def _empty_timeline_summary(*, parseable: bool) -> dict[str, Any]:
    return {
        "parseable": parseable,
        "row_count": 0,
        "first_date": None,
        "last_date": None,
        "label_counts": {},
        "canonical_labels_present": [],
        "canonical_labels_missing": list(CANONICAL_LABELS),
        "missing_label_rows": [],
        "duplicate_dates": [],
        "invalid_date_rows": [],
        "out_of_order_dates": [],
        "out_of_order": False,
    }


def _stratified_summary(sections: Any, *, timeline_labels: Mapping[str, int]) -> dict[str, Any]:
    if not isinstance(sections, list) or not sections:
        return {
            "parseable": False,
            "section_count": 0,
            "sections": [],
            "sparse_labels": [],
            "missing_labels": [],
            "unknown_labels": [],
            "count_mismatches": [],
            "non_forward_sections": [],
            "unlabeled_days": 0,
        }

    timeline_label_set = set(timeline_labels)
    section_summaries = [
        _stratified_section_summary(section, timeline_label_set=timeline_label_set)
        for section in sections
    ]
    sparse = [
        f"{section['section_name']}:{label}"
        for section in section_summaries
        for label in section["sparse_labels"]
    ]
    missing = [
        f"{section['section_name']}:{label}"
        for section in section_summaries
        for label in section["missing_labels"]
    ]
    unknown = [
        f"{section['section_name']}:{label}"
        for section in section_summaries
        for label in section["unknown_labels"]
    ]
    mismatches = [
        section["section_name"]
        for section in section_summaries
        if not section["count_matches_total"]
    ]
    non_forward = [
        section["section_name"]
        for section in section_summaries
        if not section["forward_join"]
    ]
    return {
        "parseable": True,
        "section_count": len(section_summaries),
        "sections": section_summaries,
        "sparse_labels": sparse,
        "missing_labels": missing,
        "unknown_labels": unknown,
        "count_mismatches": mismatches,
        "non_forward_sections": non_forward,
        "unlabeled_days": sum(int(section["unlabeled_days"]) for section in section_summaries),
    }


def _stratified_section_summary(
    section: Mapping[str, Any],
    *,
    timeline_label_set: set[str],
) -> dict[str, Any]:
    payload = section.get("payload") if isinstance(section.get("payload"), dict) else {}
    label_counts = _label_counts(payload)
    total_return_days = _int_value(payload.get("total_return_days"))
    if total_return_days == 0:
        total_return_days = _int_value(_lookup(payload, "n_days", 0))
    count_sum = sum(label_counts.values())
    join_rule = str(payload.get("join_rule") or "")
    sparse_labels = [
        label
        for label in CANONICAL_LABELS
        if 0 < int(label_counts.get(label, 0)) < MIN_OBS_FOR_RATIOS
    ]
    missing_labels = [label for label in CANONICAL_LABELS if label not in label_counts]
    allowed_unknown = {*ALLOWED_DIAGNOSTIC_LABELS, *CANONICAL_LABELS}
    unknown_labels = [
        label
        for label in sorted(label_counts)
        if timeline_label_set and label not in timeline_label_set and label not in allowed_unknown
    ]
    return {
        "section_name": str(section.get("section_name") or "unknown"),
        "parseable": bool(payload),
        "total_return_days": total_return_days,
        "join_rule": join_rule,
        "forward_join": _is_forward_join_rule(join_rule),
        "label_counts": dict(sorted(label_counts.items())),
        "count_sum": count_sum,
        "count_matches_total": count_sum == total_return_days and total_return_days > 0,
        "sparse_labels": sparse_labels,
        "missing_labels": missing_labels,
        "unknown_labels": unknown_labels,
        "unlabeled_days": int(label_counts.get("UNLABELED", 0)),
    }


def _liveness_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {
            "parseable": False,
            "overall": None,
            "tracked_checks": {},
            "non_ok_checks": ["collect-public-data", "regime-stratify"],
        }
    tracked: dict[str, dict[str, Any]] = {}
    for item in _items(parsed, "checks"):
        key = str(item.get("key") or item.get("name") or "")
        if key in {"collect-public-data", "regime-stratify"}:
            tracked[key] = {
                "status": str(item.get("status") or ""),
                "age_hours": item.get("age_hours"),
                "last_success_utc": item.get("last_success_utc"),
            }
    non_ok = [
        key
        for key in ("collect-public-data", "regime-stratify")
        if tracked.get(key, {}).get("status") != "OK"
    ]
    return {
        "parseable": True,
        "overall": parsed.get("overall") or parsed.get("overall_status"),
        "tracked_checks": tracked,
        "non_ok_checks": non_ok,
    }


def _released_work_summary(parsed: Any) -> dict[str, Any]:
    released = {
        str(item.get("candidate_id") or "")
        for item in _items(parsed, "released_work")
        if str(item.get("status", "")).lower() in {"released", "complete", "completed", "done"}
    }
    return {
        "parseable": isinstance(parsed, dict),
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "completed_candidate_released": COMPLETED_CANDIDATE_ID in released,
        "released_count": len(released),
    }


def _timeline_shape_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            key="timeline_shape",
            status=GATE_FAIL,
            summary_ko="regime_timeline.csv를 파싱할 수 없다.",
            evidence_keys=("public-data-regime-timeline",),
        )
    problems = []
    for field, label in (
        ("invalid_date_rows", "날짜 파싱 실패"),
        ("duplicate_dates", "중복 날짜"),
        ("out_of_order_dates", "날짜 역순"),
    ):
        if summary.get(field):
            problems.append(f"{label} {len(summary[field])}건")
    if problems:
        return QualityGate(
            key="timeline_shape",
            status=GATE_FAIL,
            summary_ko=", ".join(problems),
            evidence_keys=("public-data-regime-timeline",),
        )
    rows = int(summary.get("row_count") or 0)
    if rows < MIN_TIMELINE_ROWS:
        return QualityGate(
            key="timeline_shape",
            status=GATE_WAIT,
            summary_ko=f"timeline 행 수가 부족하다: {rows}/{MIN_TIMELINE_ROWS}",
            evidence_keys=("public-data-regime-timeline",),
        )
    return QualityGate(
        key="timeline_shape",
        status=GATE_PASS,
        summary_ko=(
            f"timeline {rows}행, {summary.get('first_date')}~{summary.get('last_date')} "
            "날짜 순서가 정상이다."
        ),
        evidence_keys=("public-data-regime-timeline",),
    )


def _timeline_label_coverage_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            key="timeline_label_coverage",
            status=GATE_FAIL,
            summary_ko="timeline label coverage를 확인할 수 없다.",
            evidence_keys=("public-data-regime-timeline",),
        )
    missing_rows = list(summary.get("missing_label_rows") or [])
    if missing_rows:
        return QualityGate(
            key="timeline_label_coverage",
            status=GATE_FAIL,
            summary_ko=f"빈 label 행이 있다: {len(missing_rows)}건",
            evidence_keys=("public-data-regime-timeline",),
        )
    missing = list(summary.get("canonical_labels_missing") or [])
    if missing:
        return QualityGate(
            key="timeline_label_coverage",
            status=GATE_WAIT,
            summary_ko=f"canonical label 관측 대기: {', '.join(missing)}",
            evidence_keys=("public-data-regime-timeline",),
        )
    counts = summary.get("label_counts") or {}
    label_text = ", ".join(f"{key}={value}" for key, value in counts.items())
    return QualityGate(
        key="timeline_label_coverage",
        status=GATE_PASS,
        summary_ko=f"canonical label이 모두 존재한다: {label_text}",
        evidence_keys=("public-data-regime-timeline",),
    )


def _stratified_observation_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            key="stratified_observation_floor",
            status=GATE_FAIL,
            summary_ko="regime-stratify stratified JSON을 파싱할 수 없다.",
            evidence_keys=("regime-stratify",),
        )
    if summary.get("unknown_labels"):
        return QualityGate(
            key="stratified_observation_floor",
            status=GATE_FAIL,
            summary_ko=f"timeline에 없는 label이 stratify에 있다: {summary['unknown_labels'][:3]}",
            evidence_keys=("public-data-regime-timeline", "regime-stratify"),
        )
    waiting = list(summary.get("sparse_labels") or []) + list(summary.get("missing_labels") or [])
    unlabeled_days = int(summary.get("unlabeled_days") or 0)
    if unlabeled_days:
        waiting.append(f"UNLABELED={unlabeled_days}")
    if waiting:
        return QualityGate(
            key="stratified_observation_floor",
            status=GATE_WAIT,
            summary_ko=f"레짐별 joined return 관측 대기: {', '.join(waiting[:5])}",
            evidence_keys=("regime-stratify",),
        )
    return QualityGate(
        key="stratified_observation_floor",
        status=GATE_PASS,
        summary_ko=(
            f"{summary.get('section_count')}개 stratify section의 canonical label "
            "관측 수가 충분하다."
        ),
        evidence_keys=("regime-stratify",),
    )


def _forward_join_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            key="forward_join_quality",
            status=GATE_FAIL,
            summary_ko="regime-stratify 결과가 없어 전망적 조인을 확인할 수 없다.",
            evidence_keys=("regime-stratify",),
        )
    non_forward = list(summary.get("non_forward_sections") or [])
    if non_forward:
        return QualityGate(
            key="forward_join_quality",
            status=GATE_FAIL,
            summary_ko=f"d+1 전망적 join_rule이 누락됐다: {', '.join(non_forward[:3])}",
            evidence_keys=("regime-stratify",),
        )
    mismatches = list(summary.get("count_mismatches") or [])
    if mismatches:
        return QualityGate(
            key="forward_join_quality",
            status=GATE_FAIL,
            summary_ko=(
                "label count 합계가 total_return_days와 맞지 않는다: "
                f"{', '.join(mismatches[:3])}"
            ),
            evidence_keys=("regime-stratify",),
        )
    return QualityGate(
        key="forward_join_quality",
        status=GATE_PASS,
        summary_ko=(
            f"{summary.get('section_count')}개 section의 d+1 전망적 조인과 "
            "count 합계가 일치한다."
        ),
        evidence_keys=("regime-stratify",),
    )


def _liveness_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("parseable"):
        return QualityGate(
            key="sidecar_liveness",
            status=GATE_WAIT,
            summary_ko="pipeline-liveness를 파싱할 수 없어 관측 대기 상태로 둔다.",
            evidence_keys=("pipeline-liveness",),
        )
    non_ok = list(summary.get("non_ok_checks") or [])
    if non_ok:
        return QualityGate(
            key="sidecar_liveness",
            status=GATE_WAIT,
            summary_ko=f"데이터 sidecar 생존성 대기: {', '.join(non_ok)}",
            evidence_keys=("pipeline-liveness",),
        )
    return QualityGate(
        key="sidecar_liveness",
        status=GATE_PASS,
        summary_ko="collect-public-data와 regime-stratify 생존성 check가 OK다.",
        evidence_keys=("pipeline-liveness",),
    )


def _overall_status(gates: tuple[QualityGate, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if GATE_FAIL in statuses:
        return BLOCKED
    if GATE_WAIT in statuses:
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _parse_csv_rows(raw: str) -> list[dict[str, str]] | None:
    try:
        reader = csv.DictReader(io.StringIO(raw))
        if (
            not reader.fieldnames
            or "date" not in reader.fieldnames
            or "label" not in reader.fieldnames
        ):
            return None
        return [dict(row) for row in reader]
    except csv.Error:
        return None


def _parse_regime_stratify_sections(raw: str) -> list[dict[str, Any]] | None:
    direct = _parse_json(raw)
    if isinstance(direct, dict) and _looks_like_stratified_result(direct):
        return [{"section_name": "direct-json", "payload": direct}]

    sections: list[dict[str, Any]] = []
    lower = raw.lower()
    marker = _STRATIFIED_MARKER.lower()
    start = 0
    while True:
        marker_index = lower.find(marker, start)
        if marker_index < 0:
            break
        parsed = _json_object_after(raw, marker_index + len(marker))
        if isinstance(parsed, dict):
            sections.append(
                {
                    "section_name": _section_name_before(raw, marker_index, len(sections) + 1),
                    "payload": parsed,
                }
            )
        start = marker_index + len(marker)

    if sections:
        return sections

    for index, body in enumerate(_FENCED_JSON_RE.findall(raw), start=1):
        parsed = _parse_json(body.strip())
        if isinstance(parsed, dict) and _looks_like_stratified_result(parsed):
            sections.append({"section_name": f"section-{index}", "payload": parsed})
    return sections


def _json_object_after(raw: str, start: int) -> Any:
    decoder = json.JSONDecoder()
    brace = raw.find("{", start)
    while brace >= 0:
        try:
            obj, _ = decoder.raw_decode(raw[brace:])
            return obj
        except json.JSONDecodeError:
            brace = raw.find("{", brace + 1)
    return None


def _section_name_before(raw: str, marker_index: int, fallback_index: int) -> str:
    headings = list(_HEADING_RE.finditer(raw[:marker_index]))
    if headings:
        return headings[-1].group("title").strip()
    return f"section-{fallback_index}"


def _looks_like_stratified_result(parsed: Mapping[str, Any]) -> bool:
    return "total_return_days" in parsed and any(
        key in parsed for key in ("by_label", "labels", "label_counts")
    )


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
    return None


def _label_counts(parsed: Mapping[str, Any]) -> dict[str, int]:
    raw = parsed.get("by_label")
    if isinstance(raw, dict):
        return {
            str(key): _int_value(value.get("n_days")) if isinstance(value, dict) else 0
            for key, value in raw.items()
        }
    for key in ("labels", "label_counts"):
        raw = parsed.get(key)
        if isinstance(raw, dict):
            return {str(label): _int_value(value) for label, value in raw.items()}
    return {}


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


def _is_forward_join_rule(join_rule: str) -> bool:
    normalized = join_rule.lower()
    return "d+1" in normalized or ("전망적" in join_rule and "미래 누출" in join_rule)


def _summary_for(key: str, parsed: Any) -> str:
    if key == "public-data-regime-timeline" and isinstance(parsed, list):
        return f"timeline_rows={len(parsed)}"
    if key == "regime-stratify" and isinstance(parsed, list):
        totals = [
            _int_value(section.get("payload", {}).get("total_return_days"))
            for section in parsed
            if isinstance(section.get("payload"), dict)
        ]
        return f"sections={len(parsed)}, total_return_days={totals}"
    if not isinstance(parsed, dict):
        return "구조화 값 존재"
    if key == "pipeline-liveness":
        return f"overall={parsed.get('overall') or parsed.get('overall_status')}"
    if key == "released-work":
        return f"released_count={len(_items(parsed, 'released_work'))}"
    return "구조화 JSON 존재"


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


__all__ = [
    "BLOCKED",
    "CANONICAL_LABELS",
    "COMPLETED_CANDIDATE_ID",
    "CONTRACT_READY",
    "GATE_FAIL",
    "GATE_PASS",
    "GATE_WAIT",
    "MIN_TIMELINE_ROWS",
    "NEXT_DATA_EVIDENCE_CANDIDATE_ID",
    "OBSERVATION_WAIT",
    "QualityGate",
    "REQUIRED_INPUTS",
    "RegimeTimelineCoverageReport",
    "SAFETY_INVARIANTS",
    "SCHEMA_VERSION",
    "build_regime_timeline_coverage_report",
    "read_evidence_manifest",
    "read_repo_sidecars",
]
