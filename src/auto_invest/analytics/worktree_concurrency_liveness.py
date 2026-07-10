"""스펙 109 - worktree 동시 작업 생존성 계약.

local concurrency guard, session-start hook, pre-commit/pre-push hook, 복구
스냅샷 표면을 하나의 PASS/WAIT/FAIL 보고서로 묶는다. 읽기 전용이며 브로커,
주문, 자본 배분, live 설정, whitelist/caps, 비밀값, 헌법/커널, 외부 유료
서비스를 건드리지 않는다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
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

COMPLETED_CANDIDATE_ID = "candidate-worktree-concurrency-liveness-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "candidate-agent-harness-regression-liveness-contract"

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("guard-script", "scripts/local_concurrency_guard.py"),
    ("codex-hooks", ".codex/hooks.json"),
    ("pre-commit-hook", ".githooks/pre-commit"),
    ("pre-push-hook", ".githooks/pre-push"),
    ("runtime-state-dir", ".codex/state/concurrency"),
    ("agent-harness", "scripts/agent_harness_probe.py"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
    ("autonomous-work", "automation/autonomous-work-execution-last-run:LAST_RUN.md"),
    ("guard-check", "supplied:local_concurrency_guard --mode check output"),
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
    "no worktree creation",
    "no lease or snapshot write",
    "no fresh external collection",
    "no GitHub API call from report module",
    "no SSH/server access from report module",
    "no external paid service",
    "read-only worktree concurrency liveness contract only",
)

_RELEASED_STATUSES = {"released", "release", "complete", "completed", "done"}
_SESSION_GUARD = "scripts/local_concurrency_guard.py --mode session-start"
_GIT_GROUND_TRUTH = ".codex/hooks/git_ground_truth.py"
_PRE_COMMIT_GUARD = "scripts/local_concurrency_guard.py --mode pre-commit"
_PRE_PUSH_GUARD = "scripts/local_concurrency_guard.py --mode pre-push"
_SNAPSHOT_TOKENS = (
    "def write_snapshot",
    "SNAPSHOT_DIR",
    "metadata.json",
    "worktree.diff",
    "index.diff",
    "untracked",
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
    """동시 작업 생존성 조건 하나."""

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
class WorktreeConcurrencyLivenessReport:
    """worktree 동시 작업 생존성 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    guard_behavior_summary: dict[str, Any]
    runtime_state_summary: dict[str, Any]
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
            "guard_behavior_summary": self.guard_behavior_summary,
            "runtime_state_summary": self.runtime_state_summary,
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# worktree 동시 작업 생존성 계약 (as of {self.timestamp_utc})",
            "",
            (
                "저장소 훅과 supplied observation만 읽는 보고입니다. worktree 생성, "
                "lease 쓰기, snapshot 쓰기, 커밋, 푸시, 주문, 자본 배분, live 설정 "
                "변경은 하지 않습니다."
            ),
            "",
            "## 종합 판정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| overall_status | {self.overall_status} |",
            f"| completed_candidate_id | {self.completed_candidate_id} |",
            f"| next_candidate_id | {self.next_candidate_id} |",
            f"| runtime_guard_state | {_table(self.runtime_state_summary.get('state'))} |",
        ]

        lines += ["", "## 검증 게이트", ""]
        lines += ["| 게이트 | 상태 | 요약 |", "|--------|------|------|"]
        for gate in self.quality_gates:
            lines.append(
                f"| {_table(gate.gate_id)} | {gate.status} | {_table(gate.summary_ko)} |"
            )

        lines += ["", "## guard synthetic behavior", ""]
        lines += ["| 시나리오 | 기대 | 실제 |", "|----------|------|------|"]
        for key, outcome in self.guard_behavior_summary.items():
            if not isinstance(outcome, Mapping):
                continue
            lines.append(
                f"| {_table(key)} | {_table(outcome.get('expected'))} | "
                f"{_table(outcome.get('actual'))} |"
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


def build_worktree_concurrency_liveness_report(
    evidence_texts: Mapping[str, str | None],
    *,
    repo_root: Path,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> WorktreeConcurrencyLivenessReport:
    """수집된 증거 원문으로 worktree 동시 작업 생존성 보고서를 만든다."""

    repo = repo_root.resolve()
    now = _as_utc(now)
    guard_behavior = _guard_behavior_summary(repo)
    runtime_summary = _runtime_state_summary(repo, evidence_texts.get("guard-check"))
    released_summary = _released_work_summary(evidence_texts.get("released-work"))
    gates = (
        _static_surface_gate(repo),
        _session_start_hook_gate(repo),
        _git_hooks_gate(repo),
        _guard_behavior_gate(guard_behavior),
        _snapshot_surface_gate(repo),
        _runtime_guard_output_gate(runtime_summary),
        _released_work_gate(released_summary),
        _safety_boundary_gate(),
    )
    overall = _overall_status(gates)

    return WorktreeConcurrencyLivenessReport(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit=commit,
        timestamp_utc=now.isoformat().replace("+00:00", "Z"),
        overall_status=overall,
        completed_candidate_id=COMPLETED_CANDIDATE_ID,
        next_candidate_id=NEXT_AUTONOMOUS_CANDIDATE_ID,
        evidence_surfaces=_evidence_surfaces(repo, evidence_texts, released_summary),
        guard_behavior_summary=guard_behavior,
        runtime_state_summary=runtime_summary,
        quality_gates=gates,
        released_work_summary=released_summary,
        safety_invariants=SAFETY_INVARIANTS,
    )


def collect_repo_evidence(
    repo_root: Path,
    *,
    guard_check_path: Path | None = None,
    released_work_path: Path | None = None,
    evidence_dir: Path | None = None,
) -> dict[str, str | None]:
    """probe 인수와 로컬 checkout에서 읽을 수 있는 증거를 모은다."""

    repo = repo_root.resolve()
    paths: dict[str, Path | None] = {
        "guard-check": guard_check_path,
        "released-work": released_work_path,
    }
    if evidence_dir is not None:
        paths = {
            **paths,
            "guard-check": paths["guard-check"] or evidence_dir / "guard-check.txt",
            "released-work": paths["released-work"] or evidence_dir / "released-work.json",
        }
    paths["released-work"] = paths["released-work"] or (
        repo / REPO_SIDECAR_PATHS["released-work"]
    )
    return {key: _read_text(path) for key, path in paths.items()}


def _static_surface_gate(repo: Path) -> QualityGate:
    required = {
        "guard-script",
        "codex-hooks",
        "pre-commit-hook",
        "pre-push-hook",
        "agent-harness",
    }
    missing = [
        source
        for key, source in REQUIRED_INPUTS
        if key in required and not (repo / source).exists()
    ]
    if missing:
        return QualityGate(
            "static_operating_surfaces",
            GATE_FAIL,
            "필수 운영 표면을 읽을 수 없다: " + ", ".join(missing),
            tuple(sorted(required)),
        )
    return QualityGate(
        "static_operating_surfaces",
        GATE_PASS,
        "guard script, Codex hook, git hook, agent harness를 저장소에서 읽을 수 있다.",
        tuple(sorted(required)),
    )


def _session_start_hook_gate(repo: Path) -> QualityGate:
    raw = _read_text(repo / ".codex/hooks.json")
    if raw is None:
        return QualityGate(
            "session_start_guard_registration",
            GATE_FAIL,
            ".codex/hooks.json을 읽을 수 없다.",
            ("codex-hooks",),
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return QualityGate(
            "session_start_guard_registration",
            GATE_FAIL,
            ".codex/hooks.json이 JSON으로 파싱되지 않는다.",
            ("codex-hooks",),
        )
    commands = _session_start_commands(parsed)
    guard_index = _first_index(commands, _SESSION_GUARD)
    ground_truth_index = _first_index(commands, _GIT_GROUND_TRUTH)
    if guard_index is None:
        return QualityGate(
            "session_start_guard_registration",
            GATE_FAIL,
            "SessionStart가 local_concurrency_guard를 호출하지 않는다.",
            ("codex-hooks", "guard-script"),
        )
    if ground_truth_index is not None and guard_index > ground_truth_index:
        return QualityGate(
            "session_start_guard_registration",
            GATE_FAIL,
            "local_concurrency_guard가 git ground truth 뒤에 실행된다.",
            ("codex-hooks", "guard-script"),
        )
    return QualityGate(
        "session_start_guard_registration",
        GATE_PASS,
        "SessionStart가 local_concurrency_guard를 git ground truth보다 먼저 실행한다.",
        ("codex-hooks", "guard-script"),
    )


def _git_hooks_gate(repo: Path) -> QualityGate:
    pre_commit = _read_text(repo / ".githooks/pre-commit") or ""
    pre_push = _read_text(repo / ".githooks/pre-push") or ""
    errors: list[str] = []
    if _PRE_COMMIT_GUARD not in pre_commit:
        errors.append("pre-commit hook이 guard pre-commit 모드를 호출하지 않는다")
    if _PRE_PUSH_GUARD not in pre_push:
        errors.append("pre-push hook이 guard pre-push 모드를 호출하지 않는다")
    if errors:
        return QualityGate(
            "git_hook_blocking_registration",
            GATE_FAIL,
            "; ".join(errors),
            ("pre-commit-hook", "pre-push-hook", "guard-script"),
        )
    return QualityGate(
        "git_hook_blocking_registration",
        GATE_PASS,
        "pre-commit과 pre-push 훅이 guard의 쓰기 차단 모드를 호출한다.",
        ("pre-commit-hook", "pre-push-hook", "guard-script"),
    )


def _guard_behavior_gate(summary: Mapping[str, Any]) -> QualityGate:
    if summary.get("load_status") != PARSE_OK:
        return QualityGate(
            "guard_behavior_contract",
            GATE_FAIL,
            str(summary.get("error") or "guard script를 로드할 수 없다."),
            ("guard-script",),
        )
    failures = [
        key
        for key, value in summary.items()
        if isinstance(value, Mapping) and value.get("expected") != value.get("actual")
    ]
    if failures:
        return QualityGate(
            "guard_behavior_contract",
            GATE_FAIL,
            "synthetic guard 기대값과 다른 시나리오: " + ", ".join(failures),
            ("guard-script",),
        )
    return QualityGate(
        "guard_behavior_contract",
        GATE_PASS,
        "check WARN, pre-commit/pre-push BLOCK, main 차단 계약이 synthetic 평가에서 살아 있다.",
        ("guard-script",),
    )


def _snapshot_surface_gate(repo: Path) -> QualityGate:
    raw = _read_text(repo / "scripts/local_concurrency_guard.py") or ""
    missing = [token for token in _SNAPSHOT_TOKENS if token not in raw]
    if missing:
        return QualityGate(
            "recovery_snapshot_surface",
            GATE_FAIL,
            "복구 스냅샷 표면 토큰이 없다: " + ", ".join(missing),
            ("guard-script", "runtime-state-dir"),
        )
    return QualityGate(
        "recovery_snapshot_surface",
        GATE_PASS,
        "metadata, worktree/index diff, untracked 복구 표면이 guard source에 남아 있다.",
        ("guard-script", "runtime-state-dir"),
    )


def _runtime_guard_output_gate(summary: Mapping[str, Any]) -> QualityGate:
    state = summary.get("state")
    if state == GATE_PASS:
        return QualityGate(
            "runtime_guard_observation",
            GATE_PASS,
            "supplied guard output이 OK/WARN/BLOCK 관측을 제공한다.",
            ("guard-check",),
        )
    if state == GATE_FAIL:
        return QualityGate(
            "runtime_guard_observation",
            GATE_FAIL,
            "supplied guard output이 guard 실패를 나타낸다.",
            ("guard-check",),
        )
    return QualityGate(
        "runtime_guard_observation",
        GATE_WAIT,
        "runtime guard output이 없거나 판정을 확정할 수 없다.",
        ("guard-check",),
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
        "읽기 전용 계약이며 worktree 생성, lease/snapshot 쓰기, 돈 경로를 건드리지 않는다.",
        (),
    )


def _guard_behavior_summary(repo: Path) -> dict[str, Any]:
    try:
        guard = _load_guard(repo)
    except Exception as exc:  # pragma: no cover - exercised through load_status tests
        return {"load_status": PARSE_MALFORMED, "error": str(exc)}

    state = guard.CurrentState(
        repo=repo,
        worktree=repo,
        branch="Codex/feature",
        head="abc123",
        thread_id="CODEX_THREAD_ID:this",
        dirty_paths=frozenset({"src/a.py"}),
    )
    other = guard.Lease(
        path=repo / ".codex/state/concurrency/other.json",
        thread_id="CODEX_THREAD_ID:other",
        host="host",
        worktree=str(repo),
        branch="Codex/feature",
        head="def456",
        updated_at=1_800_000_000.0,
        dirty_paths=frozenset({"src/a.py"}),
    )
    main_state = guard.CurrentState(
        repo=repo,
        worktree=repo,
        branch="main",
        head="abc123",
        thread_id="CODEX_THREAD_ID:this",
        dirty_paths=frozenset(),
    )

    return {
        "load_status": PARSE_OK,
        "clean_check": _outcome(guard.evaluate(state, [], mode="check"), "OK"),
        "conflict_check": _outcome(guard.evaluate(state, [other], mode="check"), "WARN"),
        "conflict_pre_commit": _outcome(
            guard.evaluate(state, [other], mode="pre-commit"),
            "BLOCK",
        ),
        "conflict_pre_push": _outcome(
            guard.evaluate(state, [other], mode="pre-push"),
            "BLOCK",
        ),
        "main_branch_pre_commit": _outcome(
            guard.evaluate(main_state, [], mode="pre-commit"),
            "BLOCK",
        ),
        "main_push_pre_push": _outcome(
            guard.evaluate(
                state,
                [],
                mode="pre-push",
                push_stdin="refs/heads/topic abc refs/heads/main def\n",
            ),
            "BLOCK",
        ),
    }


def _runtime_state_summary(repo: Path, raw_guard_output: str | None) -> dict[str, Any]:
    state_dir = repo / ".codex/state/concurrency"
    if raw_guard_output is None or not raw_guard_output.strip():
        state = GATE_WAIT
        summary = "guard check output이 제공되지 않았다."
    else:
        lowered = raw_guard_output.lower()
        if "local multi-session guard failed" in lowered:
            state = GATE_FAIL
            summary = "guard 실패 텍스트가 있다."
        elif any(marker in raw_guard_output for marker in ("- OK:", "- WARN:", "- BLOCK:")):
            state = GATE_PASS
            summary = "guard output이 OK/WARN/BLOCK finding을 제공한다."
        else:
            state = GATE_WAIT
            summary = "guard output은 있으나 finding을 확정할 수 없다."
    return {
        "state": state,
        "summary_ko": summary,
        "runtime_state_dir_present": state_dir.exists(),
        "runtime_state_dir": ".codex/state/concurrency",
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
    released_summary: Mapping[str, Any],
) -> tuple[EvidenceSurface, ...]:
    surfaces: list[EvidenceSurface] = []
    for key, source_ref in REQUIRED_INPUTS:
        if key == "guard-check":
            text = evidence_texts.get(key)
            surfaces.append(
                EvidenceSurface(
                    key,
                    source_ref,
                    bool(text and text.strip()),
                    PARSE_PRESENT if text and text.strip() else PARSE_MISSING,
                    "supplied guard output이다." if text else "guard output이 없다.",
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
        optional_runtime = key == "runtime-state-dir"
        surfaces.append(
            EvidenceSurface(
                key,
                source_ref,
                present,
                PARSE_PRESENT if optional_runtime and present else (
                    PARSE_MISSING if optional_runtime else PARSE_OK if present else PARSE_MISSING
                ),
                _surface_summary(key, present),
            )
        )
    return tuple(surfaces)


def _released_surface_summary(status: str, released_summary: Mapping[str, Any]) -> str:
    if status == PARSE_MISSING:
        return "released-work 증거가 없다."
    if status == PARSE_MALFORMED:
        return "released-work JSON이 malformed 상태다."
    if released_summary.get("completed_candidate_released"):
        return "이번 완료 후보가 released로 기록됐다."
    return "released-work는 읽혔지만 이번 완료 후보는 아직 없다."


def _surface_summary(key: str, present: bool) -> str:
    if key == "runtime-state-dir":
        return (
            "gitignored runtime 상태 디렉터리가 있다."
            if present
            else "gitignored runtime 상태 디렉터리는 현재 checkout에 없다."
        )
    return "저장소에서 읽을 수 있다." if present else "저장소에서 읽을 수 없다."


def _session_start_commands(parsed: Any) -> list[str]:
    commands: list[str] = []
    if not isinstance(parsed, dict):
        return commands
    hooks = parsed.get("hooks")
    if not isinstance(hooks, dict):
        return commands
    for group in _items(hooks.get("SessionStart")):
        for hook in _items(group.get("hooks")):
            command = hook.get("command")
            if isinstance(command, str):
                commands.append(command)
    return commands


def _first_index(values: list[str], needle: str) -> int | None:
    for index, value in enumerate(values):
        if needle in value:
            return index
    return None


def _outcome(findings: Any, expected: str) -> dict[str, Any]:
    levels = [str(getattr(finding, "level", "")) for finding in findings]
    actual = expected if expected in levels else (levels[0] if levels else "")
    return {"expected": expected, "actual": actual, "levels": levels}


def _overall_status(gates: tuple[QualityGate, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if GATE_FAIL in statuses:
        return BLOCKED
    if GATE_WAIT in statuses:
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _load_guard(repo: Path) -> Any:
    path = repo / "scripts/local_concurrency_guard.py"
    spec = importlib.util.spec_from_file_location("local_concurrency_guard_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load local_concurrency_guard.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
    "QualityGate",
    "SAFETY_INVARIANTS",
    "WorktreeConcurrencyLivenessReport",
    "build_worktree_concurrency_liveness_report",
    "collect_repo_evidence",
]
