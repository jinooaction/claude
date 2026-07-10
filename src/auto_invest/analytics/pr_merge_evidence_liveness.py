"""스펙 108 - PR/머지 증거 생존성 계약.

PR 본문 품질 관문, main 머지 커밋, released-work 장부, deploy-status 관측을
하나의 PASS/WAIT/FAIL 보고서로 묶는다. 읽기 전용이며 브로커, 주문, 자본
배분, live 설정, whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스를
건드리지 않는다.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_pr_quality_gate  # noqa: E402

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

COMPLETED_CANDIDATE_ID = "candidate-pr-merge-evidence-liveness-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "candidate-worktree-concurrency-liveness-contract"
EXPECTED_RISK_GRADE = 2

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("pr-body", "supplied:pull_request_body.md"),
    ("pr-template", ".github/pull_request_template.md"),
    ("pr-quality-script", "scripts/check_pr_quality_gate.py"),
    ("pr-quality-workflow", ".github/workflows/pr-quality-gate.yml"),
    ("deploy-workflow", ".github/workflows/deploy-on-merge.yml"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
    ("deploy-status", "supplied:deploy-status observation"),
    ("autonomous-work", "automation/autonomous-work-execution-last-run:LAST_RUN.md"),
)

REPO_SIDECAR_PATHS: Mapping[str, str] = {
    "released-work": "automation/released-work-last-run/released_work.json",
    "autonomous-work": "automation/autonomous-work-execution-last-run/LAST_RUN.md",
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
    "no GitHub API call from report module",
    "no SSH/server access from report module",
    "no external paid service",
    "read-only PR/merge evidence liveness contract only",
)

_RELEASED_STATUSES = {"released", "release", "complete", "completed", "done"}
_MERGE_PR_RE = re.compile(r"Merge pull request #(?P<number>\d+)")
_DEPLOY_FAIL_RE = re.compile(
    r"(deploy\s+failed|deployment\s+failed|배포\s*실패|롤백|rollback|rolled[_ -]?back|❌)",
    re.IGNORECASE,
)
_DEPLOY_WAIT_RE = re.compile(
    r"(in[- ]?progress|queued|pending|not[- ]?found|장중\s*연기|타이머|대기)",
    re.IGNORECASE,
)
_DEPLOY_PASS_RE = re.compile(
    r"(deploy on merge to main|배포).*(success|성공|✅)|"
    r"(배포\s*트리거\s*없음|workflow\s*skipped|paths-ignore)",
    re.IGNORECASE | re.DOTALL,
)


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
    """PR/머지 증거 조건 하나."""

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
class PRMergeEvidenceLivenessReport:
    """PR/머지 증거 생존성 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    merge_summary: dict[str, Any]
    deploy_summary: dict[str, Any]
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
            "merge_summary": self.merge_summary,
            "deploy_summary": self.deploy_summary,
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# PR/머지 증거 생존성 계약 (as of {self.timestamp_utc})",
            "",
            (
                "기존 저장소 증거와 supplied observation만 읽는 보고입니다. PR 생성, "
                "머지, 배포, 주문, 자본 배분, live 설정 변경은 하지 않습니다."
            ),
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| next_candidate_id | {self.next_candidate_id} |",
            f"| merge_pr_number | {_table(self.merge_summary.get('pr_number'))} |",
            f"| deploy_state | {_table(self.deploy_summary.get('state'))} |",
        ]

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


def build_pr_merge_evidence_liveness_report(
    evidence_texts: Mapping[str, str | None],
    *,
    repo_root: Path,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> PRMergeEvidenceLivenessReport:
    """수집된 증거 원문으로 PR/머지 증거 생존성 보고서를 만든다."""

    repo = repo_root.resolve()
    now = _as_utc(now)
    merge_summary = _merge_summary(repo)
    deploy_summary = _deploy_summary(evidence_texts.get("deploy-status"))
    released_summary = _released_work_summary(evidence_texts.get("released-work"))
    gates = (
        _static_surface_gate(repo),
        _pr_body_gate(evidence_texts.get("pr-body")),
        _merge_gate(merge_summary),
        _released_work_gate(released_summary),
        _deploy_status_gate(deploy_summary),
        _safety_boundary_gate(),
    )
    overall = _overall_status(gates)

    return PRMergeEvidenceLivenessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=overall,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_AUTONOMOUS_CANDIDATE_ID,
        evidence_surfaces=_evidence_surfaces(repo, evidence_texts, released_summary),
        merge_summary=merge_summary,
        deploy_summary=deploy_summary,
        quality_gates=gates,
        released_work_summary=released_summary,
        safety_invariants=SAFETY_INVARIANTS,
    )


def collect_repo_evidence(
    repo_root: Path,
    *,
    pr_body_path: Path | None = None,
    released_work_path: Path | None = None,
    deploy_status_path: Path | None = None,
    evidence_dir: Path | None = None,
) -> dict[str, str | None]:
    """probe 인수와 로컬 checkout에서 읽을 수 있는 증거를 모은다."""

    repo = repo_root.resolve()
    paths: dict[str, Path | None] = {
        "pr-body": pr_body_path,
        "released-work": released_work_path,
        "deploy-status": deploy_status_path,
    }
    if evidence_dir is not None:
        paths = {
            **paths,
            "pr-body": paths["pr-body"] or evidence_dir / "pr-body.md",
            "released-work": paths["released-work"] or evidence_dir / "released-work.json",
            "deploy-status": paths["deploy-status"] or evidence_dir / "deploy-status.md",
        }
    paths["released-work"] = paths["released-work"] or (
        repo / REPO_SIDECAR_PATHS["released-work"]
    )
    return {key: _read_text(path) for key, path in paths.items()}


def _static_surface_gate(repo: Path) -> QualityGate:
    missing = [
        source
        for key, source in REQUIRED_INPUTS
        if key
        in {
            "pr-template",
            "pr-quality-script",
            "pr-quality-workflow",
            "deploy-workflow",
        }
        and not (repo / source).exists()
    ]
    if missing:
        return QualityGate(
            "static_operating_surfaces",
            GATE_FAIL,
            "필수 운영 표면을 읽을 수 없다: " + ", ".join(missing),
            ("pr-template", "pr-quality-script", "pr-quality-workflow", "deploy-workflow"),
        )
    return QualityGate(
        "static_operating_surfaces",
        GATE_PASS,
        "PR 템플릿, 품질 관문, deploy workflow를 저장소에서 읽을 수 있다.",
        ("pr-template", "pr-quality-script", "pr-quality-workflow", "deploy-workflow"),
    )


def _pr_body_gate(body: str | None) -> QualityGate:
    if body is None or not body.strip():
        return QualityGate(
            "pr_body_quality",
            GATE_WAIT,
            "PR 본문 증거가 아직 제공되지 않았다.",
            ("pr-body", "pr-quality-script"),
        )

    errors: list[str] = []
    missing = [
        heading
        for heading in check_pr_quality_gate.REQUIRED_HEADINGS
        if heading not in body
    ]
    if missing:
        errors.append("필수 섹션 누락: " + ", ".join(missing))

    selected_grade = check_pr_quality_gate._selected_risk_grade(body)  # noqa: SLF001
    if selected_grade is None:
        errors.append("위험 등급 하나를 선택해야 한다.")
    elif selected_grade != EXPECTED_RISK_GRADE:
        errors.append(f"이번 후보의 위험 등급은 {EXPECTED_RISK_GRADE}이어야 한다.")

    for field in check_pr_quality_gate.REQUIRED_FIELDS:
        if not check_pr_quality_gate._line_value(body, field):  # noqa: SLF001
            errors.append(f"문제 정의의 '{field}' 값을 채워야 한다.")

    harness_value = check_pr_quality_gate._line_value(body, "하네스 평가")  # noqa: SLF001
    if not harness_value or "agent_harness_probe.py --strict" not in harness_value:
        errors.append("하네스 평가에 strict agent harness 결과를 남겨야 한다.")

    handoff_value = check_pr_quality_gate._line_value(body, "HANDOFF 검증")  # noqa: SLF001
    if not handoff_value or "check_handoff_facts.py" not in handoff_value:
        errors.append("HANDOFF 검증에 check_handoff_facts.py 결과를 남겨야 한다.")

    if "없음 / 있음" in body:
        errors.append("안전 경계 선택지를 실제 값으로 바꿔야 한다.")

    if errors:
        return QualityGate(
            "pr_body_quality",
            GATE_FAIL,
            "; ".join(errors),
            ("pr-body", "pr-quality-script"),
        )
    return QualityGate(
        "pr_body_quality",
        GATE_PASS,
        "PR 본문이 등급 2 품질 관문 필수 증거를 포함한다.",
        ("pr-body", "pr-quality-script"),
    )


def _merge_gate(summary: Mapping[str, Any]) -> QualityGate:
    if not summary.get("present"):
        return QualityGate(
            "main_merge_evidence",
            GATE_WAIT,
            "origin/main 머지 커밋을 아직 읽을 수 없다.",
            (),
        )
    if not summary.get("is_pull_request_merge"):
        return QualityGate(
            "main_merge_evidence",
            GATE_FAIL,
            "origin/main 최신 커밋이 PR merge 형식이 아니다.",
            (),
        )
    return QualityGate(
        "main_merge_evidence",
        GATE_PASS,
        "origin/main 최신 커밋이 PR merge 증거를 제공한다.",
        (),
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


def _deploy_status_gate(summary: Mapping[str, Any]) -> QualityGate:
    state = summary.get("state")
    if state == GATE_PASS:
        return QualityGate(
            "deploy_status_observation",
            GATE_PASS,
            "deploy-status 관측이 성공 또는 의도적 skip을 나타낸다.",
            ("deploy-status",),
        )
    if state == GATE_FAIL:
        return QualityGate(
            "deploy_status_observation",
            GATE_FAIL,
            "deploy-status 관측이 실패 또는 rollback을 나타낸다.",
            ("deploy-status",),
        )
    return QualityGate(
        "deploy_status_observation",
        GATE_WAIT,
        "deploy-status 관측이 아직 없거나 대기 상태다.",
        ("deploy-status",),
    )


def _safety_boundary_gate() -> QualityGate:
    return QualityGate(
        "safety_boundary",
        GATE_PASS,
        "읽기 전용 계약이며 브로커, 주문, 자본, live 설정, 비밀값을 건드리지 않는다.",
        (),
    )


def _merge_summary(repo: Path) -> dict[str, Any]:
    raw = _git(repo, "log", "origin/main", "-1", "--pretty=%H%x09%h%x09%s")
    if raw is None or not raw.strip():
        return {
            "present": False,
            "full_commit": None,
            "short_commit": None,
            "subject": None,
            "is_pull_request_merge": False,
            "pr_number": None,
        }
    parts = raw.strip().split("\t", 2)
    full_commit = parts[0] if parts else ""
    short_commit = parts[1] if len(parts) > 1 else full_commit[:7]
    subject = parts[2] if len(parts) > 2 else ""
    match = _MERGE_PR_RE.search(subject)
    return {
        "present": True,
        "full_commit": full_commit,
        "short_commit": short_commit,
        "subject": subject,
        "is_pull_request_merge": match is not None,
        "pr_number": int(match.group("number")) if match else None,
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


def _deploy_summary(raw: str | None) -> dict[str, Any]:
    if raw is None or not raw.strip():
        return {
            "present": False,
            "state": GATE_WAIT,
            "summary_ko": "deploy-status 관측이 제공되지 않았다.",
            "container_visible": (
                "main commit check run, KIS smoke sidecar, supplied observation text"
            ),
            "operator_only": "GitHub Actions Summary and server audit_log",
        }
    text = raw.strip()
    if _DEPLOY_FAIL_RE.search(text):
        state = GATE_FAIL
        summary = "실패 또는 rollback 관측이 있다."
    elif _DEPLOY_WAIT_RE.search(text):
        state = GATE_WAIT
        summary = "진행 중이거나 장중 연기/대기 관측이다."
    elif _DEPLOY_PASS_RE.search(text):
        state = GATE_PASS
        summary = "성공 또는 의도적 skip 관측이다."
    else:
        state = GATE_WAIT
        summary = "deploy-status 텍스트는 있으나 성공/실패를 확정할 수 없다."
    return {
        "present": True,
        "state": state,
        "summary_ko": summary,
        "container_visible": (
            "main commit check run, KIS smoke sidecar, supplied observation text"
        ),
        "operator_only": "GitHub Actions Summary and server audit_log",
    }


def _evidence_surfaces(
    repo: Path,
    evidence_texts: Mapping[str, str | None],
    released_summary: Mapping[str, Any],
) -> tuple[EvidenceSurface, ...]:
    surfaces: list[EvidenceSurface] = []
    for key, source_ref in REQUIRED_INPUTS:
        if key == "pr-body":
            text = evidence_texts.get(key)
            surfaces.append(
                EvidenceSurface(
                    key,
                    source_ref,
                    bool(text and text.strip()),
                    PARSE_PRESENT if text and text.strip() else PARSE_MISSING,
                    "supplied PR 본문 증거다." if text else "PR 본문 증거가 없다.",
                )
            )
            continue
        if key == "deploy-status":
            text = evidence_texts.get(key)
            surfaces.append(
                EvidenceSurface(
                    key,
                    source_ref,
                    bool(text and text.strip()),
                    PARSE_PRESENT if text and text.strip() else PARSE_MISSING,
                    "supplied deploy-status 관측이다." if text else "deploy-status 관측이 없다.",
                )
            )
            continue
        if key == "released-work":
            status = str(released_summary.get("parse_status") or PARSE_MISSING)
            surfaces.append(
                EvidenceSurface(
                    key,
                    source_ref,
                    status != PARSE_MISSING,
                    status,
                    _released_surface_summary(status, released_summary),
                )
            )
            continue
        local = repo / source_ref
        present = local.exists()
        surfaces.append(
            EvidenceSurface(
                key,
                source_ref,
                present,
                PARSE_OK if present else PARSE_MISSING,
                "저장소에서 읽을 수 있다." if present else "저장소에서 읽을 수 없다.",
            )
        )
    return tuple(surfaces)


def _released_surface_summary(
    status: str,
    released_summary: Mapping[str, Any],
) -> str:
    if status == PARSE_MISSING:
        return "released-work 증거가 없다."
    if status == PARSE_MALFORMED:
        return "released-work JSON이 malformed 상태다."
    if released_summary.get("completed_candidate_released"):
        return "이번 완료 후보가 released로 기록됐다."
    return "released-work는 읽혔지만 이번 완료 후보는 아직 없다."


def _overall_status(gates: tuple[QualityGate, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if GATE_FAIL in statuses:
        return BLOCKED
    if GATE_WAIT in statuses:
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _read_text(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


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
    "BLOCKED",
    "COMPLETED_CANDIDATE_ID",
    "CONTRACT_READY",
    "EvidenceSurface",
    "GATE_FAIL",
    "GATE_PASS",
    "GATE_WAIT",
    "NEXT_AUTONOMOUS_CANDIDATE_ID",
    "OBSERVATION_WAIT",
    "PRMergeEvidenceLivenessReport",
    "QualityGate",
    "SAFETY_INVARIANTS",
    "build_pr_merge_evidence_liveness_report",
    "collect_repo_evidence",
]
