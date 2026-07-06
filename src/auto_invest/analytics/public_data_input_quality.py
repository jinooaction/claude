"""스펙 099 — 공개 데이터 입력 품질 계약.

기존 sidecar 스냅샷만 읽어 공개 데이터 입력이 다음 투자 연구 후보의 입력으로
쓸 수 있는지 판정한다. 읽기 전용이며 브로커, 주문, 자본 배분, live 설정,
whitelist/caps, 비밀값, 외부 유료 서비스를 건드리지 않는다.
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

COMPLETED_CANDIDATE_ID = "candidate-public-data-input-quality-contract"
NEXT_DATA_EVIDENCE_CANDIDATE_ID = "candidate-regime-timeline-coverage-contract"

MIN_REGIME_TIMELINE_ROWS = 20
MIN_STRATIFIED_RETURN_DAYS = 20
MIN_CROSS_CHECK_OVERLAP = 1

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
    "read-only input-quality contract only",
)

_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*(?P<body>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_JSON_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)


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
class PublicDataInputQualityReport:
    """공개 데이터 입력 품질 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    quality_gates: tuple[QualityGate, ...]
    public_data_summary: dict[str, Any]
    regime_coverage_summary: dict[str, Any]
    liveness_summary: dict[str, Any]
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
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "public_data_summary": self.public_data_summary,
            "regime_coverage_summary": self.regime_coverage_summary,
            "liveness_summary": self.liveness_summary,
            "released_work_summary": self.released_work_summary,
            "capital_path_summary": self.capital_path_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 공개 데이터 입력 품질 계약 (as of {self.timestamp_utc})",
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


def build_public_data_input_quality_report(
    evidence_texts: Mapping[str, str | None],
    *,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> PublicDataInputQualityReport:
    """수집된 sidecar 원문으로 공개 데이터 입력 품질 계약을 만든다."""

    now = _as_utc(now)
    parsed = {key: _parse_for_key(key, evidence_texts.get(key)) for key, _ in REQUIRED_INPUTS}
    surfaces = tuple(
        _surface_for(key, source_ref, evidence_texts.get(key), parsed[key])
        for key, source_ref in REQUIRED_INPUTS
    )
    public_data_summary = _public_data_summary(parsed["public-data-summary"])
    regime_coverage_summary = _regime_coverage_summary(
        parsed["public-data-regime"],
        parsed["public-data-regime-timeline"],
        parsed["regime-stratify"],
    )
    liveness_summary = _liveness_summary(parsed["pipeline-liveness"])
    released_work_summary = _released_work_summary(parsed["released-work"])
    capital_path_summary = _capital_path_summary(parsed["capital-path-readiness"])

    gates = (
        _publication_gate(parsed["public-data-summary"], public_data_summary),
        _cross_check_gate(parsed["public-data-summary"], public_data_summary),
        _regime_coverage_gate(regime_coverage_summary),
        _liveness_gate(liveness_summary),
    )
    overall_status = _overall_status(gates)

    return PublicDataInputQualityReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=overall_status,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_DATA_EVIDENCE_CANDIDATE_ID,
        evidence_surfaces=surfaces,
        quality_gates=gates,
        public_data_summary=public_data_summary,
        regime_coverage_summary=regime_coverage_summary,
        liveness_summary=liveness_summary,
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
    return {
        key: _read_optional(repo_root / path)
        for key, path in paths.items()
    }


def _parse_for_key(key: str, raw: str | None) -> Any:
    if raw is None:
        return None
    if key == "public-data-regime-timeline":
        return _parse_csv_rows(raw)
    if key in {"public-data-last-run", "regime-stratify", "pipeline-liveness"}:
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


def _public_data_summary(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {
            "parseable": False,
            "overall_ok": False,
            "published": 0,
            "total_items": 0,
            "failed_items": [],
            "cross_check_count": 0,
            "failed_cross_checks": [],
            "minimum_cross_check_overlap": 0,
        }

    items = list(_items(parsed, "items"))
    cross_checks = list(_items(parsed, "cross_checks"))
    failed_items = [
        str(item.get("key") or item.get("symbol") or item.get("name") or index)
        for index, item in enumerate(items)
        if not bool(item.get("ok"))
    ]
    failed_cross_checks = [
        str(check.get("name") or check.get("key") or index)
        for index, check in enumerate(cross_checks)
        if str(check.get("status", "")).upper() != GATE_PASS
    ]
    overlaps = [
        int(check.get("overlap_days", check.get("overlap", 0)) or 0)
        for check in cross_checks
        if isinstance(check, dict)
    ]
    return {
        "parseable": True,
        "as_of": parsed.get("as_of"),
        "overall_ok": bool(parsed.get("overall_ok")),
        "published": int(parsed.get("published") or 0),
        "total_items": int(parsed.get("total_items") or len(items)),
        "item_count": len(items),
        "failed_items": failed_items,
        "cross_check_count": len(cross_checks),
        "failed_cross_checks": failed_cross_checks,
        "minimum_cross_check_overlap": min(overlaps) if overlaps else 0,
    }


def _regime_coverage_summary(
    regime: Any,
    timeline_rows: Any,
    stratify: Any,
) -> dict[str, Any]:
    indicators = _items(regime, "indicators") if isinstance(regime, dict) else []
    bad_indicators = [
        str(item.get("key") or item.get("name") or index)
        for index, item in enumerate(indicators)
        if str(item.get("status", "")).upper() not in {"OK", GATE_PASS}
    ]
    rows = timeline_rows if isinstance(timeline_rows, list) else []
    labels = _labels_from_stratify(stratify)
    total_return_days = int(_lookup(stratify, "total_return_days", 0) or 0)
    available_indicators = int(_lookup(regime, "available_indicators", len(indicators)) or 0)
    total_indicators = int(_lookup(regime, "total_indicators", len(indicators)) or 0)
    return {
        "regime_parseable": isinstance(regime, dict),
        "timeline_parseable": isinstance(timeline_rows, list),
        "stratify_parseable": isinstance(stratify, dict),
        "regime_label": _lookup(regime, "overall_label", _lookup(regime, "label", None)),
        "available_indicators": available_indicators,
        "total_indicators": total_indicators,
        "bad_indicators": bad_indicators,
        "timeline_rows": len(rows),
        "timeline_first_date": _row_value(rows[0], "date") if rows else None,
        "timeline_last_date": _row_value(rows[-1], "date") if rows else None,
        "total_return_days": total_return_days,
        "labels": labels,
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


def _publication_gate(parsed: Any, summary: Mapping[str, Any]) -> QualityGate:
    if not isinstance(parsed, dict):
        return QualityGate(
            key="public_data_publication_completeness",
            status=GATE_FAIL,
            summary_ko="public-data summary가 없거나 파싱되지 않아 발행 완전성을 확인할 수 없다.",
            evidence_keys=("public-data-summary",),
        )
    published = int(summary.get("published") or 0)
    total_items = int(summary.get("total_items") or 0)
    failed_items = summary.get("failed_items") or []
    if (
        summary.get("overall_ok")
        and total_items > 0
        and published == total_items
        and not failed_items
    ):
        return QualityGate(
            key="public_data_publication_completeness",
            status=GATE_PASS,
            summary_ko=f"{published}/{total_items}개 공개 데이터 항목이 모두 발행됐다.",
            evidence_keys=("public-data-summary", "public-data-last-run"),
        )
    return QualityGate(
        key="public_data_publication_completeness",
        status=GATE_FAIL,
        summary_ko=(
            f"발행 항목이 완전하지 않다: published={published}, total={total_items}, "
            f"failed_items={len(failed_items)}"
        ),
        evidence_keys=("public-data-summary", "public-data-last-run"),
    )


def _cross_check_gate(parsed: Any, summary: Mapping[str, Any]) -> QualityGate:
    if not isinstance(parsed, dict):
        return QualityGate(
            key="public_data_cross_check_quality",
            status=GATE_FAIL,
            summary_ko="public-data summary가 없어 교차검증을 확인할 수 없다.",
            evidence_keys=("public-data-summary",),
        )
    failed = summary.get("failed_cross_checks") or []
    count = int(summary.get("cross_check_count") or 0)
    min_overlap = int(summary.get("minimum_cross_check_overlap") or 0)
    if failed:
        return QualityGate(
            key="public_data_cross_check_quality",
            status=GATE_FAIL,
            summary_ko=f"교차검증 실패 {len(failed)}개: {', '.join(failed[:3])}",
            evidence_keys=("public-data-summary",),
        )
    if count <= 0 or min_overlap < MIN_CROSS_CHECK_OVERLAP:
        return QualityGate(
            key="public_data_cross_check_quality",
            status=GATE_WAIT,
            summary_ko=(
                f"교차검증 overlap이 부족하다: count={count}, min_overlap={min_overlap}"
            ),
            evidence_keys=("public-data-summary",),
        )
    return QualityGate(
        key="public_data_cross_check_quality",
        status=GATE_PASS,
        summary_ko=f"교차검증 {count}개가 통과했고 최소 overlap은 {min_overlap}일이다.",
        evidence_keys=("public-data-summary",),
    )


def _regime_coverage_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("regime_parseable") or not summary.get("timeline_parseable"):
        return QualityGate(
            key="regime_timeline_coverage",
            status=GATE_FAIL,
            summary_ko="regime summary 또는 regime timeline을 파싱할 수 없다.",
            evidence_keys=("public-data-regime", "public-data-regime-timeline"),
        )
    if summary.get("bad_indicators"):
        return QualityGate(
            key="regime_timeline_coverage",
            status=GATE_FAIL,
            summary_ko=f"레짐 지표 실패가 있다: {', '.join(summary['bad_indicators'][:3])}",
            evidence_keys=("public-data-regime", "public-data-regime-timeline"),
        )
    if (
        int(summary.get("total_indicators") or 0) <= 0
        or int(summary.get("available_indicators") or 0) < int(summary.get("total_indicators") or 0)
    ):
        return QualityGate(
            key="regime_timeline_coverage",
            status=GATE_WAIT,
            summary_ko=(
                "레짐 지표 관측 수가 부족하다: "
                f"{summary.get('available_indicators')}/{summary.get('total_indicators')}"
            ),
            evidence_keys=("public-data-regime",),
        )
    if int(summary.get("timeline_rows") or 0) < MIN_REGIME_TIMELINE_ROWS:
        return QualityGate(
            key="regime_timeline_coverage",
            status=GATE_WAIT,
            summary_ko=f"regime_timeline 행 수가 부족하다: {summary.get('timeline_rows')}",
            evidence_keys=("public-data-regime-timeline",),
        )
    if (
        not summary.get("stratify_parseable")
        or int(summary.get("total_return_days") or 0) < MIN_STRATIFIED_RETURN_DAYS
    ):
        return QualityGate(
            key="regime_timeline_coverage",
            status=GATE_WAIT,
            summary_ko=(
                "regime-stratify 관측 수가 부족하다: "
                f"total_return_days={summary.get('total_return_days')}"
            ),
            evidence_keys=("regime-stratify",),
        )
    return QualityGate(
        key="regime_timeline_coverage",
        status=GATE_PASS,
        summary_ko=(
            f"timeline {summary.get('timeline_rows')}행, "
            f"stratified return {summary.get('total_return_days')}일을 확인했다."
        ),
        evidence_keys=("public-data-regime", "public-data-regime-timeline", "regime-stratify"),
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
        marker_index = body.lower().rfind("stratified json")
        if marker_index >= 0:
            match = _JSON_OBJECT_RE.search(body[marker_index:])
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


def _labels_from_stratify(parsed: Any) -> dict[str, int]:
    raw = _lookup(parsed, "labels", None)
    if isinstance(raw, dict):
        return {str(key): int(value or 0) for key, value in raw.items()}
    raw = _lookup(parsed, "label_counts", None)
    if isinstance(raw, dict):
        return {str(key): int(value or 0) for key, value in raw.items()}
    raw = _lookup(parsed, "by_label", None)
    if isinstance(raw, dict):
        return {
            str(key): int(value.get("n_days") or 0)
            for key, value in raw.items()
            if isinstance(value, dict)
        }
    return {}


def _row_value(row: Mapping[str, str], key: str) -> str | None:
    return row.get(key)


def _summary_for(key: str, parsed: Any) -> str:
    if key == "public-data-regime-timeline" and isinstance(parsed, list):
        return f"timeline_rows={len(parsed)}"
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
    if key == "regime-stratify":
        return f"total_return_days={_lookup(parsed, 'total_return_days', '-')}"
    if key == "pipeline-liveness":
        return f"overall={parsed.get('overall') or parsed.get('overall_status')}"
    if key == "released-work":
        return f"released_count={len(_items(parsed, 'released_work'))}"
    if key == "capital-path-readiness":
        return (
            f"readiness={parsed.get('readiness_state')}, "
            f"live={parsed.get('live_money_status')}"
        )
    if parsed.get("overall") or parsed.get("overall_status"):
        overall = parsed.get("overall") or parsed.get("overall_status")
        if isinstance(overall, dict):
            label = overall.get("label") or overall.get("status") or "present"
            return f"overall={label}"
        return f"overall={overall}"
    return "구조화 JSON 존재"


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
    "COMPLETED_CANDIDATE_ID",
    "CONTRACT_READY",
    "GATE_FAIL",
    "GATE_PASS",
    "GATE_WAIT",
    "NEXT_DATA_EVIDENCE_CANDIDATE_ID",
    "OBSERVATION_WAIT",
    "PublicDataInputQualityReport",
    "QualityGate",
    "REQUIRED_INPUTS",
    "SAFETY_INVARIANTS",
    "SCHEMA_VERSION",
    "build_public_data_input_quality_report",
    "read_evidence_manifest",
    "read_repo_sidecars",
]
