"""스펙 107 — HANDOFF 사실성 생존성 계약.

기존 `check_handoff_facts.py`의 HANDOFF 사실성 판정을 자율 후보가 소비할 수
있는 JSON/Markdown 계약으로 감싼다. 읽기 전용이며 브로커, 주문, 자본 배분,
live 설정, whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스를 건드리지 않는다.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_handoff_facts  # noqa: E402

SCHEMA_VERSION = "1.0"

CONTRACT_READY = "CONTRACT_READY"
BLOCKED = "BLOCKED"

PARSE_OK = "ok"
PARSE_PRESENT = "present"
PARSE_MISSING = "missing"

GATE_PASS = "PASS"
GATE_FAIL = "FAIL"

COMPLETED_CANDIDATE_ID = "candidate-handoff-truth-liveness-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "candidate-pr-merge-evidence-liveness-contract"

EVIDENCE_REFS: tuple[tuple[str, str], ...] = (
    ("handoff", "HANDOFF.md"),
    ("check-handoff-facts", "scripts/check_handoff_facts.py"),
    ("agent-harness-probe", "scripts/agent_harness_probe.py"),
    ("pr-quality-gate", ".github/workflows/pr-quality-gate.yml"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
    ("autonomous-work", "automation/autonomous-work-execution-last-run:LAST_RUN.md"),
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
    "read-only HANDOFF truth liveness contract only",
)

_RELEASED_STATUSES = {"released", "release", "complete", "completed", "done"}


@dataclass(frozen=True)
class EvidenceSurface:
    """보고서가 참조한 저장소 운영 증거."""

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
class AllowedMainBaseline:
    """HANDOFF 마지막 main 커밋 행에 허용되는 git 기준."""

    kind: str
    short_commit: str
    subject: str
    reason_ko: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "short_commit": self.short_commit,
            "subject": self.subject,
            "reason_ko": self.reason_ko,
        }


@dataclass(frozen=True)
class QualityGate:
    """HANDOFF 사실성 생존성 조건 하나."""

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
class HandoffTruthLivenessReport:
    """HANDOFF 사실성 생존성 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    allowed_baselines: tuple[AllowedMainBaseline, ...]
    handoff_summary: dict[str, Any]
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
            "allowed_baselines": [
                baseline.to_dict() for baseline in self.allowed_baselines
            ],
            "handoff_summary": self.handoff_summary,
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# HANDOFF 사실성 생존성 계약 (as of {self.timestamp_utc})",
            "",
            (
                "기존 저장소 사실만 읽는 보고입니다. PR 생성, 머지, 배포, 주문, "
                "자본 배분, live 설정 변경은 하지 않습니다."
            ),
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            "| matched_baseline_kind | "
            f"{_table(self.handoff_summary.get('matched_baseline_kind'))} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| next_candidate_id | {self.next_candidate_id} |",
        ]

        lines += ["", "## HANDOFF 기준", ""]
        lines += ["| 종류 | 커밋 | 제목 | 이유 |", "|------|------|------|------|"]
        for baseline in self.allowed_baselines:
            lines.append(
                f"| {_table(baseline.kind)} | {_table(baseline.short_commit)} | "
                f"{_table(baseline.subject)} | {_table(baseline.reason_ko)} |"
            )

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


def build_handoff_truth_liveness_report(
    repo_root: Path,
    *,
    now: datetime,
    handoff_path: Path | None = None,
    expect_pytest: str | None = None,
    expect_ruff: str | None = None,
    expect_open_pr: str | None = None,
    run_id: str = "local",
    commit: str = "unknown",
) -> HandoffTruthLivenessReport:
    """저장소의 HANDOFF 사실성 계약 보고서를 만든다."""

    repo = repo_root.resolve()
    handoff = handoff_path.resolve() if handoff_path else repo / "HANDOFF.md"
    now = _as_utc(now)

    baselines = _allowed_baselines(repo)
    fact_report = check_handoff_facts.evaluate(
        repo,
        handoff_path=handoff,
        expect_pytest=expect_pytest,
        expect_ruff=expect_ruff,
        expect_open_pr=expect_open_pr,
    )
    summary = _handoff_summary(handoff, baselines, fact_report)
    gates = (
        _checker_available_gate(repo),
        *(_gate_from_fact(fact) for fact in fact_report.facts),
        _safety_boundary_gate(),
    )
    overall = CONTRACT_READY if all(gate.status == GATE_PASS for gate in gates) else BLOCKED

    return HandoffTruthLivenessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=overall,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_AUTONOMOUS_CANDIDATE_ID,
        evidence_surfaces=_evidence_surfaces(repo, handoff),
        allowed_baselines=baselines,
        handoff_summary=summary,
        quality_gates=gates,
        released_work_summary=_released_work_summary(repo),
        safety_invariants=SAFETY_INVARIANTS,
    )


def _allowed_baselines(repo: Path) -> tuple[AllowedMainBaseline, ...]:
    baselines: list[AllowedMainBaseline] = []
    for baseline in check_handoff_facts._main_baselines(repo):  # noqa: SLF001
        kind = _baseline_kind(baseline.reason)
        subject = _subject_for_log(baseline.log)
        baselines.append(
            AllowedMainBaseline(
                kind=kind,
                short_commit=baseline.short,
                subject=subject,
                reason_ko=_baseline_reason_ko(kind),
            )
        )
    return tuple(baselines)


def _handoff_summary(
    handoff: Path,
    baselines: tuple[AllowedMainBaseline, ...],
    fact_report: check_handoff_facts.HandoffFactReport,
) -> dict[str, Any]:
    try:
        text = handoff.read_text(encoding="utf-8")
    except OSError:
        main_row = None
    else:
        main_row = check_handoff_facts._row_value(text, "마지막 main 커밋")  # noqa: SLF001
    matched = next(
        (
            baseline
            for baseline in baselines
            if baseline.short_commit and main_row and baseline.short_commit in main_row
        ),
        None,
    )
    failed = [fact.id for fact in fact_report.facts if fact.status != "PASS"]
    return {
        "checker_status": fact_report.status,
        "handoff_path": str(handoff),
        "main_row": main_row,
        "matched_baseline_kind": matched.kind if matched else None,
        "matched_baseline_commit": matched.short_commit if matched else None,
        "failed_facts": failed,
        "fact_count": len(fact_report.facts),
        "facts": [
            {
                "id": fact.id,
                "status": fact.status,
                "message": fact.message,
                "evidence": fact.evidence,
            }
            for fact in fact_report.facts
        ],
    }


def _evidence_surfaces(repo: Path, handoff: Path) -> tuple[EvidenceSurface, ...]:
    surfaces: list[EvidenceSurface] = []
    for key, ref in EVIDENCE_REFS:
        local_path = _local_path_for(repo, handoff, key, ref)
        present = local_path.exists() if local_path is not None else False
        surfaces.append(
            EvidenceSurface(
                key=key,
                source_ref=ref,
                present=present,
                parse_status=PARSE_PRESENT if key.startswith("automation-") else (
                    PARSE_OK if present else PARSE_MISSING
                ),
                summary_ko=_surface_summary(key, present),
            )
        )
    return tuple(surfaces)


def _local_path_for(repo: Path, handoff: Path, key: str, ref: str) -> Path | None:
    if key == "handoff":
        return handoff
    if ":" in ref:
        branch_or_dir, filename = ref.split(":", 1)
        return repo / branch_or_dir / filename
    return repo / ref


def _surface_summary(key: str, present: bool) -> str:
    if present:
        return "저장소에서 읽을 수 있다."
    if key in {"released-work", "autonomous-work"}:
        return "sidecar branch reference이며 로컬 checkout에는 없을 수 있다."
    return "저장소에서 읽을 수 없다."


def _checker_available_gate(repo: Path) -> QualityGate:
    path = repo / "scripts" / "check_handoff_facts.py"
    if path.exists():
        return QualityGate(
            "checker_available",
            GATE_PASS,
            "`check_handoff_facts.py`를 저장소에서 읽을 수 있다.",
            ("check-handoff-facts",),
        )
    return QualityGate(
        "checker_available",
        GATE_FAIL,
        "`check_handoff_facts.py`가 없어 HANDOFF 사실성 기준을 재현할 수 없다.",
        ("check-handoff-facts",),
    )


def _gate_from_fact(fact: check_handoff_facts.FactResult) -> QualityGate:
    return QualityGate(
        gate_id=f"handoff_fact_{fact.id}",
        status=GATE_PASS if fact.status == "PASS" else GATE_FAIL,
        summary_ko=fact.message,
        evidence_keys=("handoff", "check-handoff-facts"),
    )


def _safety_boundary_gate() -> QualityGate:
    return QualityGate(
        "safety_boundary",
        GATE_PASS,
        "읽기 전용 계약이며 브로커, 주문, 자본, live 설정, 비밀값을 건드리지 않는다.",
        (),
    )


def _released_work_summary(repo: Path) -> dict[str, Any]:
    path = repo / "automation" / "released-work-last-run" / "released_work.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {
            "parseable": False,
            "source_ref": "automation/released-work-last-run:released_work.json",
            "completed_candidate_id": COMPLETED_CANDIDATE_ID,
            "completed_candidate_released": False,
            "released_count": 0,
        }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "parseable": False,
            "source_ref": "automation/released-work-last-run:released_work.json",
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
        "parseable": True,
        "source_ref": "automation/released-work-last-run:released_work.json",
        "completed_candidate_id": COMPLETED_CANDIDATE_ID,
        "completed_candidate_released": COMPLETED_CANDIDATE_ID in released,
        "released_count": len(released),
    }


def _baseline_kind(reason: str) -> str:
    if reason == "origin/main":
        return "origin_main"
    if reason == "previous main before handoff-only merge":
        return "handoff_only_first_parent"
    return "unknown"


def _baseline_reason_ko(kind: str) -> str:
    if kind == "origin_main":
        return "최신 origin/main 커밋과 HANDOFF 행이 직접 일치한다."
    if kind == "handoff_only_first_parent":
        return (
            "최신 머지가 Markdown 또는 specs 경로만 바꾼 handoff-only 머지라 "
            "첫 부모 기준을 허용한다."
        )
    return "알 수 없는 기준이다."


def _subject_for_log(log: str) -> str:
    parts = log.split(maxsplit=1)
    return parts[1] if len(parts) == 2 else ""


def _items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


__all__ = [
    "AllowedMainBaseline",
    "BLOCKED",
    "COMPLETED_CANDIDATE_ID",
    "CONTRACT_READY",
    "EvidenceSurface",
    "GATE_FAIL",
    "GATE_PASS",
    "HandoffTruthLivenessReport",
    "NEXT_AUTONOMOUS_CANDIDATE_ID",
    "QualityGate",
    "SAFETY_INVARIANTS",
    "build_handoff_truth_liveness_report",
]
