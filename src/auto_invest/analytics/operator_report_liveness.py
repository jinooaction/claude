"""스펙 118 - 운영자 이해 가능 보고 생존성 계약.

최종 보고가 운영자가 이해할 수 있는 의미, 검증, 남은 위험을 담는지
로컬 규칙 표면과 supplied final-report observation만 읽어 판정한다.
브로커, 주문, 자본, live 설정, 비밀값, 네트워크, 저장소 변경은 하지 않는다.
"""

from __future__ import annotations

import json
import re
import tomllib
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

COMPLETED_CANDIDATE_ID = "candidate-operator-report-liveness-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "none"

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("agents-doc", "AGENTS.md"),
    ("quality-gate-doc", ".codex/quality-gate.md"),
    ("pr-template", ".github/pull_request_template.md"),
    ("quality-suite", ".codex/harness/quality_tasks.toml"),
    ("handoff-entrypoint", "HANDOFF.md"),
    ("final-report", "supplied:final report text"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
)

REPO_SIDECAR_PATHS: Mapping[str, str] = {
    "released-work": "automation/released-work-last-run/released_work.json",
}

SAFETY_INVARIANTS: tuple[str, ...] = (
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no constitution/kernel modification",
    "no network or GitHub API call from report module",
    "no SSH/server access from report module",
    "no external paid service",
    "read-only operator report liveness contract only",
)

_RELEASED_STATUSES = {"released", "release", "complete", "completed", "done"}
_QUALITY_006_REQUIRED_CATEGORIES = {
    "honest_reporting",
    "operator_readability",
    "problem_definition",
    "safety_boundary",
    "handoff_awareness",
}
_FINAL_REPORT_CATEGORY_LABELS: Mapping[str, str] = {
    "conclusion": "첫 문장 운영 상태 결론",
    "work_summary": "무엇을 만들었거나 고쳤는가",
    "meaning": "돈 경로, 안전 경계, 자동화, 인계 의미",
    "verification": "무엇으로 확인했는가",
    "remaining_risk": "남은 위험 또는 다음 관찰 지점",
    "not_evidence_only": "증거 나열만으로 결론을 대신하지 않음",
}


@dataclass(frozen=True)
class EvidenceSurface:
    """보고서가 소비한 증거 표면."""

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
    """운영자 이해 가능 보고 생존성 조건 하나."""

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
class OperatorReportLivenessReport:
    """운영자 이해 가능 보고 생존성 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    rule_surface_summary: dict[str, Any]
    final_report_summary: dict[str, Any]
    quality_gates: tuple[QualityGate, ...]
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
            "rule_surface_summary": self.rule_surface_summary,
            "final_report_summary": self.final_report_summary,
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# 운영자 이해 가능 보고 생존성 계약 (as of {self.timestamp_utc})",
            "",
            (
                "로컬 규칙 표면과 supplied final-report observation만 읽는 "
                "읽기 전용 보고입니다. 네트워크, 주문, 자본, live 설정, 저장소 변경은 "
                "하지 않습니다."
            ),
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| next_candidate_id | {self.next_candidate_id} |",
            f"| final_report_state | {_table(self.final_report_summary.get('state'))} |",
        ]

        lines += ["", "## 검증 게이트", ""]
        lines += ["| 게이트 | 상태 | 요약 |", "|--------|------|------|"]
        for gate in self.quality_gates:
            lines.append(
                f"| {_table(gate.gate_id)} | {gate.status} | {_table(gate.summary_ko)} |"
            )

        final_summary = self.final_report_summary
        lines += ["", "## 최종 보고 관찰", ""]
        lines += ["| 항목 | 값 |", "|------|-----|"]
        lines.append(f"| state | {_table(final_summary.get('state'))} |")
        lines.append(f"| evidence_only | {_table(final_summary.get('evidence_only'))} |")
        lines.append(
            "| present_categories | "
            f"{_table(', '.join(final_summary.get('present_categories', [])))} |"
        )
        lines.append(
            "| missing_categories | "
            f"{_table(', '.join(final_summary.get('missing_categories', [])))} |"
        )

        lines += ["", "## 규칙 표면", ""]
        lines += ["| 표면 | 상태 | 요약 |", "|------|------|------|"]
        for key, summary in self.rule_surface_summary.items():
            lines.append(
                f"| {_table(key)} | {_table(summary.get('status'))} | "
                f"{_table(summary.get('summary_ko'))} |"
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


def build_operator_report_liveness_report(
    evidence_texts: Mapping[str, str | None],
    *,
    repo_root: Path,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> OperatorReportLivenessReport:
    """수집된 증거 원문으로 운영자 이해 가능 보고 생존성 보고서를 만든다."""

    repo = repo_root.resolve()
    now = _as_utc(now)
    rule_summary = _rule_surface_summary(repo)
    final_summary = _final_report_summary(evidence_texts.get("final-report"))
    released_summary = _released_work_summary(evidence_texts.get("released-work"))
    gates = (
        _rule_surface_gate(rule_summary),
        _final_report_gate(final_summary),
        _released_work_gate(released_summary),
        _safety_boundary_gate(),
    )
    overall = _overall_status(gates)

    return OperatorReportLivenessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=overall,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_AUTONOMOUS_CANDIDATE_ID,
        evidence_surfaces=_evidence_surfaces(
            repo,
            evidence_texts,
            rule_summary,
            final_summary,
            released_summary,
        ),
        rule_surface_summary=rule_summary,
        final_report_summary=final_summary,
        quality_gates=gates,
        released_work_summary=released_summary,
        safety_invariants=SAFETY_INVARIANTS,
    )


def collect_repo_evidence(
    repo_root: Path,
    *,
    final_report_path: Path | None = None,
    released_work_path: Path | None = None,
    evidence_dir: Path | None = None,
) -> dict[str, str | None]:
    """probe 인수와 로컬 checkout에서 읽을 수 있는 증거를 모은다."""

    repo = repo_root.resolve()
    paths: dict[str, Path | None] = {
        "final-report": final_report_path,
        "released-work": released_work_path,
    }
    if evidence_dir is not None:
        paths = {
            **paths,
            "final-report": paths["final-report"] or evidence_dir / "final-report.md",
            "released-work": paths["released-work"] or evidence_dir / "released-work.json",
        }
    paths["released-work"] = paths["released-work"] or (
        repo / REPO_SIDECAR_PATHS["released-work"]
    )
    return {key: _read_text(path) for key, path in paths.items()}


def _rule_surface_gate(summary: Mapping[str, Any]) -> QualityGate:
    failures = [
        f"{key}: {value.get('summary_ko')}"
        for key, value in summary.items()
        if isinstance(value, Mapping) and value.get("status") == GATE_FAIL
    ]
    if failures:
        return QualityGate(
            "rule_surface_liveness",
            GATE_FAIL,
            "보고 규칙 표면이 깨졌다: " + " / ".join(failures),
            (
                "agents-doc",
                "quality-gate-doc",
                "pr-template",
                "quality-suite",
                "handoff-entrypoint",
            ),
        )
    return QualityGate(
        "rule_surface_liveness",
        GATE_PASS,
        "AGENTS, 품질 관문, PR 템플릿, QUALITY-006, HANDOFF 표면이 보고 의미 계약을 보존한다.",
        (
            "agents-doc",
            "quality-gate-doc",
            "pr-template",
            "quality-suite",
            "handoff-entrypoint",
        ),
    )


def _final_report_gate(summary: Mapping[str, Any]) -> QualityGate:
    state = summary.get("state")
    if state == GATE_PASS:
        return QualityGate(
            "final_report_observation",
            GATE_PASS,
            "supplied final report가 필수 의미 범주를 모두 포함한다.",
            ("final-report",),
        )
    if state == GATE_WAIT:
        return QualityGate(
            "final_report_observation",
            GATE_WAIT,
            "supplied final report가 아직 제공되지 않았다.",
            ("final-report",),
        )
    missing = ", ".join(str(item) for item in summary.get("missing_categories", []))
    return QualityGate(
        "final_report_observation",
        GATE_FAIL,
        "supplied final report가 보고 계약을 만족하지 못한다"
        + (f": {missing}" if missing else "."),
        ("final-report",),
    )


def _released_work_gate(summary: Mapping[str, Any]) -> QualityGate:
    if summary.get("parse_status") == PARSE_MISSING:
        return QualityGate(
            "released_work_completion",
            GATE_WAIT,
            "released-work 증거가 아직 제공되지 않았다.",
            ("released-work",),
        )
    if summary.get("parse_status") == PARSE_MALFORMED:
        return QualityGate(
            "released_work_completion",
            GATE_FAIL,
            "released-work JSON을 파싱할 수 없다.",
            ("released-work",),
        )
    if summary.get("completed_candidate_released"):
        return QualityGate(
            "released_work_completion",
            GATE_PASS,
            "released-work가 이번 완료 후보를 released로 기록했다.",
            ("released-work",),
        )
    return QualityGate(
        "released_work_completion",
        GATE_WAIT,
        "released-work가 이번 완료 후보를 아직 소비하지 않았다.",
        ("released-work",),
    )


def _safety_boundary_gate() -> QualityGate:
    return QualityGate(
        "safety_boundary",
        GATE_PASS,
        "읽기 전용 계약이며 네트워크, 저장소 변경, 돈 경로를 건드리지 않는다.",
        (),
    )


def _rule_surface_summary(repo: Path) -> dict[str, Any]:
    agents = _read_repo_text(repo, "AGENTS.md")
    quality_gate = _read_repo_text(repo, ".codex/quality-gate.md")
    pr_template = _read_repo_text(repo, ".github/pull_request_template.md")
    quality_suite = _quality_006_summary(
        _read_repo_text(repo, ".codex/harness/quality_tasks.toml")
    )
    handoff = _read_repo_text(repo, "HANDOFF.md")
    return {
        "agents_report_rules": _text_rule_summary(
            agents,
            (
                "최종 답변의 첫 문단",
                "무엇을 만들었거나 고쳤는가",
                "돈 경로",
                "무엇으로 확인했는가",
                "남은 위험",
                "어떤 기능을 없앴고 무엇을 남겼는지",
            ),
            "AGENTS.md 보고 기준이 필수 의미 범주를 포함한다.",
        ),
        "quality_gate_report_rules": _text_rule_summary(
            quality_gate,
            (
                "운영자 이해 가능 보고",
                "실제로 바뀐 운영 상태",
                "무엇은 여전히 안 되는가",
                "남은 위험",
            ),
            ".codex/quality-gate.md가 운영자 이해 가능 보고 관문을 포함한다.",
        ),
        "pr_template_evidence": _text_rule_summary(
            pr_template,
            (
                "## 문제 정의",
                "## 검증",
                "## 하네스 검증",
                "## 안전 경계",
                "## 인계",
                "## 자동 머지 준비",
            ),
            "PR 템플릿이 완료 보고 증거와 인계 표면을 보존한다.",
        ),
        "quality_006": quality_suite,
        "handoff_entrypoint": _text_rule_summary(
            handoff,
            ("git_ground_truth", "/sync", "AGENTS.md", "운영자 응대 핵심 규칙"),
            "HANDOFF가 다음 세션을 live truth와 AGENTS 운영 규칙으로 보낸다.",
        ),
    }


def _text_rule_summary(
    raw: str | None,
    needles: tuple[str, ...],
    ok_summary: str,
) -> dict[str, Any]:
    if raw is None:
        return {
            "status": GATE_FAIL,
            "parse_status": PARSE_MISSING,
            "summary_ko": "파일을 읽을 수 없다.",
            "missing": list(needles),
        }
    missing = [needle for needle in needles if needle not in raw]
    return {
        "status": GATE_PASS if not missing else GATE_FAIL,
        "parse_status": PARSE_PRESENT if not missing else PARSE_MALFORMED,
        "summary_ko": ok_summary if not missing else "필수 문구 누락: " + ", ".join(missing),
        "missing": missing,
    }


def _quality_006_summary(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {
            "status": GATE_FAIL,
            "parse_status": PARSE_MISSING,
            "summary_ko": "quality_tasks.toml을 읽을 수 없다.",
            "missing_categories": sorted(_QUALITY_006_REQUIRED_CATEGORIES),
        }
    try:
        parsed = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        return {
            "status": GATE_FAIL,
            "parse_status": PARSE_MALFORMED,
            "summary_ko": f"quality_tasks.toml 파싱 실패: {exc}",
            "missing_categories": sorted(_QUALITY_006_REQUIRED_CATEGORIES),
        }
    quality_006 = None
    for task in _items(parsed.get("tasks")):
        if task.get("id") == "QUALITY-006":
            quality_006 = task
            break
    if quality_006 is None:
        return {
            "status": GATE_FAIL,
            "parse_status": PARSE_MALFORMED,
            "summary_ko": "QUALITY-006 과제가 없다.",
            "missing_categories": sorted(_QUALITY_006_REQUIRED_CATEGORIES),
        }
    categories = {
        str(item)
        for item in quality_006.get("required_categories", [])
        if isinstance(item, str)
    }
    missing = sorted(_QUALITY_006_REQUIRED_CATEGORIES - categories)
    return {
        "status": GATE_PASS if not missing else GATE_FAIL,
        "parse_status": PARSE_OK if not missing else PARSE_MALFORMED,
        "summary_ko": (
            "QUALITY-006이 완료 보고 이해 실패 범주를 보존한다."
            if not missing
            else "QUALITY-006 필수 범주 누락: " + ", ".join(missing)
        ),
        "required_categories": sorted(categories),
        "missing_categories": missing,
    }


def _final_report_summary(raw: str | None) -> dict[str, Any]:
    if raw is None or not raw.strip():
        return {
            "state": GATE_WAIT,
            "parse_status": PARSE_MISSING,
            "present_categories": [],
            "missing_categories": list(_FINAL_REPORT_CATEGORY_LABELS),
            "evidence_only": False,
            "summary_ko": "final report observation이 없다.",
        }

    normalized = _normalize(raw)
    categories = {
        "conclusion": _has_conclusion(raw),
        "work_summary": _contains_any(
            normalized,
            ("무엇을", "만들", "고쳤", "변경", "추가", "구현", "수정"),
        ),
        "meaning": _contains_any(
            normalized,
            ("돈 경로", "안전 경계", "자동화", "다음 세션", "인계", "운영 상태"),
        ),
        "verification": _contains_any(
            normalized,
            ("검증", "확인", "pytest", "ruff", "하네스", "handoff", "테스트", "린트"),
        ),
        "remaining_risk": _contains_any(
            normalized,
            ("남은 위험", "아직", "다음 관찰", "관찰 지점", "범위 밖", "실행하지 못"),
        ),
    }
    evidence_only = _evidence_only(raw, normalized)
    categories["not_evidence_only"] = not evidence_only
    present = [
        _FINAL_REPORT_CATEGORY_LABELS[key]
        for key, passed in categories.items()
        if passed
    ]
    missing = [
        _FINAL_REPORT_CATEGORY_LABELS[key]
        for key, passed in categories.items()
        if not passed
    ]
    passed = not missing
    return {
        "state": GATE_PASS if passed else GATE_FAIL,
        "parse_status": PARSE_PRESENT if passed else PARSE_MALFORMED,
        "present_categories": present,
        "missing_categories": missing,
        "evidence_only": evidence_only,
        "summary_ko": (
            "필수 의미 범주를 모두 포함한다."
            if passed
            else "필수 의미 범주가 부족하다: " + ", ".join(missing)
        ),
    }


def _released_work_summary(raw: str | None) -> dict[str, Any]:
    if raw is None or not raw.strip():
        return {
            "parse_status": PARSE_MISSING,
            "completed_candidate_id": COMPLETED_CANDIDATE_ID,
            "completed_candidate_released": False,
            "released_count": 0,
        }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "parse_status": PARSE_MALFORMED,
            "completed_candidate_id": COMPLETED_CANDIDATE_ID,
            "completed_candidate_released": False,
            "released_count": 0,
        }
    released = {
        str(item.get("candidate_id") or "")
        for item in _items(parsed.get("released_work"))
        if str(item.get("status", "")).lower() in _RELEASED_STATUSES
    }
    return {
        "parse_status": PARSE_OK,
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "completed_candidate_released": COMPLETED_CANDIDATE_ID in released,
        "released_count": len(released),
    }


def _evidence_surfaces(
    repo: Path,
    evidence_texts: Mapping[str, str | None],
    rule_summary: Mapping[str, Any],
    final_summary: Mapping[str, Any],
    released_summary: Mapping[str, Any],
) -> tuple[EvidenceSurface, ...]:
    surfaces: list[EvidenceSurface] = []
    rule_status = {
        "agents-doc": rule_summary.get("agents_report_rules", {}).get("status"),
        "quality-gate-doc": rule_summary.get("quality_gate_report_rules", {}).get("status"),
        "pr-template": rule_summary.get("pr_template_evidence", {}).get("status"),
        "quality-suite": rule_summary.get("quality_006", {}).get("status"),
        "handoff-entrypoint": rule_summary.get("handoff_entrypoint", {}).get("status"),
    }
    for key, source_ref in REQUIRED_INPUTS:
        if key == "final-report":
            raw = evidence_texts.get(key)
            surfaces.append(
                EvidenceSurface(
                    key,
                    source_ref,
                    bool(raw and raw.strip()),
                    str(final_summary.get("parse_status")),
                    str(final_summary.get("summary_ko")),
                )
            )
            continue
        if key == "released-work":
            raw = evidence_texts.get(key)
            surfaces.append(
                EvidenceSurface(
                    key,
                    source_ref,
                    bool(raw and raw.strip()),
                    str(released_summary.get("parse_status")),
                    (
                        "이번 후보 released 완료"
                        if released_summary.get("completed_candidate_released")
                        else "이번 후보 released 미확인"
                    ),
                )
            )
            continue
        surface = _path_surface(key, source_ref, repo / source_ref)
        status = rule_status.get(key)
        if surface.present and status is not None:
            surface = EvidenceSurface(
                key,
                source_ref,
                True,
                PARSE_OK if status == GATE_PASS else PARSE_MALFORMED,
                f"rule surface status={status}",
            )
        surfaces.append(surface)
    return tuple(surfaces)


def _path_surface(key: str, source_ref: str, path: Path) -> EvidenceSurface:
    if path.exists():
        return EvidenceSurface(
            key,
            source_ref,
            True,
            PARSE_PRESENT,
            "저장소 파일을 읽을 수 있다.",
        )
    return EvidenceSurface(key, source_ref, False, PARSE_MISSING, "파일이 없다.")


def _overall_status(gates: tuple[QualityGate, ...]) -> str:
    if any(gate.status == GATE_FAIL for gate in gates):
        return BLOCKED
    if any(gate.status == GATE_WAIT for gate in gates):
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _has_conclusion(raw: str) -> bool:
    first = _first_nonempty_line(raw)
    if not first:
        return False
    if _line_is_evidence_only(first):
        return False
    return _contains_any(
        _normalize(first),
        (
            "들어갔다",
            "가능",
            "불가능",
            "닫혔다",
            "바뀌었다",
            "검사가",
            "상태",
            "완료",
        ),
    )


def _evidence_only(raw: str, normalized: str) -> bool:
    lines = [_normalize(line) for line in raw.splitlines() if line.strip()]
    evidence_lines = sum(_line_is_evidence_only(line) for line in lines)
    semantic = _contains_any(
        normalized,
        (
            "돈 경로",
            "안전 경계",
            "다음 세션",
            "남은 위험",
            "운영 상태",
            "무엇을",
            "만들",
            "고쳤",
        ),
    )
    return bool(lines) and evidence_lines >= max(1, len(lines) - 1) and not semantic


def _line_is_evidence_only(line: str) -> bool:
    normalized = _normalize(line)
    has_evidence = _contains_any(
        normalized,
        ("pr #", "커밋", "commit", "pytest", "ruff", "해시", "run ", "통과"),
    )
    has_meaning = _contains_any(
        normalized,
        ("돈 경로", "안전 경계", "자동화", "다음 세션", "남은 위험", "운영 상태"),
    )
    return has_evidence and not has_meaning


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _first_nonempty_line(raw: str) -> str:
    for line in raw.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _normalize(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().lower())


def _read_repo_text(repo: Path, rel: str) -> str | None:
    return _read_text(repo / rel)


def _read_text(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


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
    "NEXT_AUTONOMOUS_CANDIDATE_ID",
    "OBSERVATION_WAIT",
    "build_operator_report_liveness_report",
    "collect_repo_evidence",
]
