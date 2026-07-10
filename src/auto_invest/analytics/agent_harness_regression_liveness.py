"""스펙 110 - agent harness 회귀 생존성 계약.

evaluation, 첫 판단 품질, redteam 하네스 묶음과 supplied strict 실행 증거를
하나의 PASS/WAIT/FAIL 보고서로 묶는다. 읽기 전용이며 브로커, 주문, 자본
배분, live 설정, whitelist/caps, 비밀값, 헌법/커널, 외부 유료 서비스를
건드리지 않는다.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
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

COMPLETED_CANDIDATE_ID = "candidate-agent-harness-regression-liveness-contract"
NEXT_AUTONOMOUS_CANDIDATE_ID = "candidate-operator-report-liveness-contract"

REQUIRED_INPUTS: tuple[tuple[str, str], ...] = (
    ("agent-harness", "scripts/agent_harness_probe.py"),
    ("evaluation-suite", ".codex/harness/evaluation_tasks.toml"),
    ("quality-suite", ".codex/harness/quality_tasks.toml"),
    ("redteam-suite", ".codex/harness/redteam_tasks.toml"),
    ("handoff-facts-checker", "scripts/check_handoff_facts.py"),
    ("quality-gate-doc", ".codex/quality-gate.md"),
    ("pr-template", ".github/pull_request_template.md"),
    ("pr-quality-workflow", ".github/workflows/pr-quality-gate.yml"),
    ("agents-doc", "AGENTS.md"),
    ("handoff-entrypoint", "HANDOFF.md"),
    ("strict-output", "supplied:agent_harness_probe --strict output"),
    ("released-work", "automation/released-work-last-run:released_work.json"),
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
    "read-only agent harness regression liveness contract only",
)

_RELEASED_STATUSES = {"released", "release", "complete", "completed", "done"}
_HARNESS_FUNCTIONS = (
    "evaluate_task_suite",
    "evaluate_quality_suite",
    "evaluate_redteam_suite",
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
    """agent harness 회귀 생존성 조건 하나."""

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
class AgentHarnessRegressionLivenessReport:
    """agent harness 회귀 생존성 계약 보고."""

    schema_version: str
    run_id: str
    commit: str
    timestamp_utc: str
    overall_status: str
    completed_candidate_id: str
    next_candidate_id: str
    evidence_surfaces: tuple[EvidenceSurface, ...]
    harness_suite_summary: dict[str, Any]
    strict_observation_summary: dict[str, Any]
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
            "harness_suite_summary": self.harness_suite_summary,
            "strict_observation_summary": self.strict_observation_summary,
            "quality_gates": [gate.to_dict() for gate in self.quality_gates],
            "released_work_summary": self.released_work_summary,
            "safety_invariants": list(self.safety_invariants),
        }

    def as_markdown(self) -> str:
        lines = [
            f"# agent harness 회귀 생존성 계약 (as of {self.timestamp_utc})",
            "",
            (
                "저장소 하네스 source와 supplied strict observation만 읽는 보고입니다. "
                "하네스 실행, 네트워크 호출, 커밋, 푸시, 주문, 자본 배분, live 설정 "
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
            f"| strict_state | {_table(self.strict_observation_summary.get('state'))} |",
        ]

        lines += ["", "## 검증 게이트", ""]
        lines += ["| 게이트 | 상태 | 요약 |", "|--------|------|------|"]
        for gate in self.quality_gates:
            lines.append(
                f"| {_table(gate.gate_id)} | {gate.status} | {_table(gate.summary_ko)} |"
            )

        suites = self.harness_suite_summary
        lines += ["", "## 하네스 묶음", ""]
        lines += ["| 묶음 | 상태 | 과제 수 | 요약 |", "|------|------|-------:|------|"]
        for key in ("task_suite", "quality_suite", "redteam_suite"):
            suite = suites.get(key, {})
            messages = "; ".join(str(item) for item in suite.get("messages", []))
            lines.append(
                f"| {key} | {_table(suite.get('status'))} | "
                f"{_table(suite.get('task_count'))} | {_table(messages)} |"
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


def build_agent_harness_regression_liveness_report(
    evidence_texts: Mapping[str, str | None],
    *,
    repo_root: Path,
    now: datetime,
    run_id: str = "local",
    commit: str = "unknown",
) -> AgentHarnessRegressionLivenessReport:
    """수집된 증거 원문으로 agent harness 회귀 생존성 보고서를 만든다."""

    repo = repo_root.resolve()
    now = _as_utc(now)
    harness_summary = _harness_suite_summary(repo)
    strict_summary = _strict_observation_summary(evidence_texts.get("strict-output"))
    released_summary = _released_work_summary(evidence_texts.get("released-work"))
    gates = (
        _static_surface_gate(repo),
        _harness_suite_gate(harness_summary),
        _strict_observation_gate(strict_summary),
        _released_work_gate(released_summary),
        _safety_boundary_gate(),
    )
    overall = _overall_status(gates)

    return AgentHarnessRegressionLivenessReport(
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
            harness_summary,
            strict_summary,
            released_summary,
        ),
        harness_suite_summary=harness_summary,
        strict_observation_summary=strict_summary,
        quality_gates=gates,
        released_work_summary=released_summary,
        safety_invariants=SAFETY_INVARIANTS,
    )


def collect_repo_evidence(
    repo_root: Path,
    *,
    strict_output_path: Path | None = None,
    released_work_path: Path | None = None,
    evidence_dir: Path | None = None,
) -> dict[str, str | None]:
    """probe 인수와 로컬 checkout에서 읽을 수 있는 증거를 모은다."""

    repo = repo_root.resolve()
    paths: dict[str, Path | None] = {
        "strict-output": strict_output_path,
        "released-work": released_work_path,
    }
    if evidence_dir is not None:
        paths = {
            **paths,
            "strict-output": paths["strict-output"] or evidence_dir / "strict-output.txt",
            "released-work": paths["released-work"] or evidence_dir / "released-work.json",
        }
    paths["released-work"] = paths["released-work"] or (
        repo / REPO_SIDECAR_PATHS["released-work"]
    )
    return {key: _read_text(path) for key, path in paths.items()}


def _static_surface_gate(repo: Path) -> QualityGate:
    required = {
        "agent-harness",
        "evaluation-suite",
        "quality-suite",
        "redteam-suite",
        "handoff-facts-checker",
        "quality-gate-doc",
        "pr-template",
        "pr-quality-workflow",
        "agents-doc",
        "handoff-entrypoint",
    }
    missing = [
        source
        for key, source in REQUIRED_INPUTS
        if key in required and not (repo / source).exists()
    ]
    if missing:
        return QualityGate(
            "static_harness_surfaces",
            GATE_FAIL,
            "필수 하네스 표면을 읽을 수 없다: " + ", ".join(missing),
            tuple(sorted(required)),
        )

    harness_text = _read_text(repo / "scripts/agent_harness_probe.py") or ""
    missing_functions = [
        name for name in _HARNESS_FUNCTIONS if f"def {name}" not in harness_text
    ]
    if missing_functions:
        return QualityGate(
            "static_harness_surfaces",
            GATE_FAIL,
            "agent_harness_probe.py 평가 함수가 없다: " + ", ".join(missing_functions),
            tuple(sorted(required)),
        )
    return QualityGate(
        "static_harness_surfaces",
        GATE_PASS,
        "agent harness source, suite TOML, 품질 관문, 인계 표면을 저장소에서 읽을 수 있다.",
        tuple(sorted(required)),
    )


def _harness_suite_gate(summary: Mapping[str, Any]) -> QualityGate:
    if summary.get("load_status") != PARSE_OK:
        return QualityGate(
            "harness_suite_coverage",
            GATE_FAIL,
            str(summary.get("error") or "agent_harness_probe.py를 로드할 수 없다."),
            ("agent-harness",),
        )
    failures: list[str] = []
    for key in ("task_suite", "quality_suite", "redteam_suite"):
        suite = summary.get(key, {})
        if isinstance(suite, Mapping) and suite.get("status") == GATE_PASS:
            continue
        messages = suite.get("messages", []) if isinstance(suite, Mapping) else []
        failures.append(f"{key}: {'; '.join(str(item) for item in messages)}")
    if failures:
        return QualityGate(
            "harness_suite_coverage",
            GATE_FAIL,
            "하네스 묶음 coverage 실패: " + " / ".join(failures),
            ("evaluation-suite", "quality-suite", "redteam-suite", "agent-harness"),
        )
    return QualityGate(
        "harness_suite_coverage",
        GATE_PASS,
        "evaluation, 첫 판단 품질, redteam 묶음이 필수 범주를 모두 만족한다.",
        ("evaluation-suite", "quality-suite", "redteam-suite", "agent-harness"),
    )


def _strict_observation_gate(summary: Mapping[str, Any]) -> QualityGate:
    state = summary.get("state")
    if state == GATE_PASS:
        return QualityGate(
            "strict_harness_observation",
            GATE_PASS,
            "supplied strict harness output이 OK 판정을 제공한다.",
            ("strict-output",),
        )
    if state == GATE_FAIL:
        return QualityGate(
            "strict_harness_observation",
            GATE_FAIL,
            str(summary.get("summary_ko") or "strict harness output이 실패를 나타낸다."),
            ("strict-output",),
        )
    return QualityGate(
        "strict_harness_observation",
        GATE_WAIT,
        "strict harness output이 아직 제공되지 않았다.",
        ("strict-output",),
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
        "읽기 전용 계약이며 하네스 실행, 네트워크, 돈 경로를 건드리지 않는다.",
        (),
    )


def _harness_suite_summary(repo: Path) -> dict[str, Any]:
    try:
        harness = _load_harness(repo)
    except Exception as exc:  # pragma: no cover - covered through report status
        return {
            "load_status": PARSE_MALFORMED,
            "error": str(exc),
            "task_suite": _failed_suite("task_suite", str(exc)),
            "quality_suite": _failed_suite("quality_suite", str(exc)),
            "redteam_suite": _failed_suite("redteam_suite", str(exc)),
        }
    return {
        "load_status": PARSE_OK,
        "task_suite": _suite_result(harness.evaluate_task_suite(repo)),
        "quality_suite": _suite_result(harness.evaluate_quality_suite(repo)),
        "redteam_suite": _suite_result(harness.evaluate_redteam_suite(repo)),
    }


def _strict_observation_summary(raw: str | None) -> dict[str, Any]:
    if raw is None or not raw.strip():
        return {
            "state": GATE_WAIT,
            "parse_status": PARSE_MISSING,
            "status": None,
            "score": None,
            "max_score": None,
            "summary_ko": "strict harness output이 없다.",
        }

    parsed = _strict_json(raw)
    if isinstance(parsed, Mapping):
        status = str(parsed.get("status") or parsed.get("overall_status") or "").strip()
        score = _int_or_none(parsed.get("score"))
        max_score = _int_or_none(parsed.get("max_score"))
        passed = status == "OK" and (score is None or max_score is None or score == max_score)
        return {
            "state": GATE_PASS if passed else GATE_FAIL,
            "parse_status": PARSE_OK,
            "status": status or None,
            "score": score,
            "max_score": max_score,
            "summary_ko": (
                "strict harness JSON이 OK다."
                if passed
                else (
                    "strict harness JSON이 OK가 아니다: "
                    f"status={status}, score={score}/{max_score}"
                )
            ),
        }

    match = re.search(r"종합 판정:\s*([A-Z_]+)\s*\((\d+)\s*/\s*(\d+)\)", raw)
    if match:
        status = match.group(1)
        score = int(match.group(2))
        max_score = int(match.group(3))
        passed = status == "OK" and score == max_score
        return {
            "state": GATE_PASS if passed else GATE_FAIL,
            "parse_status": PARSE_OK,
            "status": status,
            "score": score,
            "max_score": max_score,
            "summary_ko": (
                "strict harness text가 OK다."
                if passed
                else (
                    "strict harness text가 OK가 아니다: "
                    f"status={status}, score={score}/{max_score}"
                )
            ),
        }

    status_match = re.search(r"종합 판정:\s*([A-Z_]+)", raw)
    if status_match:
        status = status_match.group(1)
        passed = status == "OK"
        return {
            "state": GATE_PASS if passed else GATE_FAIL,
            "parse_status": PARSE_OK,
            "status": status,
            "score": None,
            "max_score": None,
            "summary_ko": (
                "strict harness text가 OK다."
                if passed
                else f"strict harness text가 OK가 아니다: status={status}"
            ),
        }

    return {
        "state": GATE_FAIL,
        "parse_status": PARSE_MALFORMED,
        "status": None,
        "score": None,
        "max_score": None,
        "summary_ko": "strict harness output을 판독할 수 없다.",
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
    harness_summary: Mapping[str, Any],
    strict_summary: Mapping[str, Any],
    released_summary: Mapping[str, Any],
) -> tuple[EvidenceSurface, ...]:
    surfaces: list[EvidenceSurface] = []
    suite_status = {
        "evaluation-suite": harness_summary.get("task_suite", {}).get("status"),
        "quality-suite": harness_summary.get("quality_suite", {}).get("status"),
        "redteam-suite": harness_summary.get("redteam_suite", {}).get("status"),
    }
    for key, source_ref in REQUIRED_INPUTS:
        if key == "strict-output":
            surfaces.append(
                EvidenceSurface(
                    key,
                    source_ref,
                    bool(evidence_texts.get(key) and evidence_texts.get(key, "").strip()),
                    str(strict_summary.get("parse_status")),
                    str(strict_summary.get("summary_ko")),
                )
            )
            continue
        if key == "released-work":
            surfaces.append(
                EvidenceSurface(
                    key,
                    source_ref,
                    bool(evidence_texts.get(key) and evidence_texts.get(key, "").strip()),
                    str(released_summary.get("parse_status")),
                    (
                        "이번 후보 released 완료"
                        if released_summary.get("completed_candidate_released")
                        else "이번 후보 released 미확인"
                    ),
                )
            )
            continue
        if key == "autonomous-work":
            path = repo / REPO_SIDECAR_PATHS["autonomous-work"]
            surfaces.append(_path_surface(key, source_ref, path))
            continue
        path = repo / source_ref
        surface = _path_surface(key, source_ref, path)
        if key in suite_status and surface.present:
            status = suite_status[key]
            surface = EvidenceSurface(
                key,
                source_ref,
                True,
                PARSE_OK if status == GATE_PASS else PARSE_MALFORMED,
                f"harness evaluator status={status}",
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
    return EvidenceSurface(
        key,
        source_ref,
        False,
        PARSE_MISSING,
        "저장소 파일이 없다.",
    )


def _overall_status(gates: tuple[QualityGate, ...]) -> str:
    statuses = {gate.status for gate in gates}
    if GATE_FAIL in statuses:
        return BLOCKED
    if GATE_WAIT in statuses:
        return OBSERVATION_WAIT
    return CONTRACT_READY


def _load_harness(repo: Path) -> ModuleType:
    path = repo / "scripts/agent_harness_probe.py"
    spec = importlib.util.spec_from_file_location(
        f"_agent_harness_probe_{abs(hash(path))}",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    script_dir = str(path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for name in _HARNESS_FUNCTIONS:
        if not hasattr(module, name):
            raise AttributeError(f"agent_harness_probe.py missing {name}")
    return module


def _suite_result(result: Any) -> dict[str, Any]:
    if is_dataclass(result):
        data = asdict(result)
    elif isinstance(result, Mapping):
        data = dict(result)
    else:
        data = {"status": GATE_FAIL, "messages": [f"unknown result: {result!r}"]}
    data.setdefault("status", GATE_FAIL)
    data.setdefault("task_count", 0)
    data.setdefault("messages", [])
    return data


def _failed_suite(name: str, message: str) -> dict[str, Any]:
    return {"status": GATE_FAIL, "task_count": 0, "messages": [f"{name}: {message}"]}


def _strict_json(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    if "```" not in raw:
        return None
    buf: list[str] = []
    in_block = False
    for line in raw.splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```"):
                in_block = True
            continue
        if stripped.startswith("```"):
            try:
                return json.loads("\n".join(buf))
            except json.JSONDecodeError:
                return None
        buf.append(line)
    return None


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_text(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _as_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _table(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")
