#!/usr/bin/env python3
"""Evaluate the local Codex agent harness.

The probe is deliberately static and read-only. It checks that the operating
controls around Codex work are still wired together: session-start truth,
concurrency isolation, SDD pointers, PR quality gates, and the regression task
suite that makes future harness changes comparable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_handoff_facts  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TASK_SUITE_REL = Path(".codex/harness/evaluation_tasks.toml")
QUALITY_SUITE_REL = Path(".codex/harness/quality_tasks.toml")
REDTEAM_SUITE_REL = Path(".codex/harness/redteam_tasks.toml")
REQUIRED_TASK_COUNT = 12
REQUIRED_QUALITY_COUNT = 6
REQUIRED_REDTEAM_COUNT = 6
REQUIRED_RISK_GRADES = {0, 1, 2, 3, 4}
REQUIRED_CONTROL_CATEGORIES = {
    "context_truth",
    "concurrency",
    "worktree_isolation",
    "sdd",
    "pr_quality",
    "validation",
    "safety_boundary",
    "handoff",
    "rollback",
    "external_effects",
}
REQUIRED_QUALITY_CATEGORIES = {
    "problem_definition",
    "self_deepening",
    "risk_grading",
    "verification_plan",
    "redteam_awareness",
    "handoff_awareness",
    "operator_readability",
}
REQUIRED_REDTEAM_ATTACK_TYPES = {
    "skip_validation",
    "false_completion",
    "stale_document",
    "context_injection",
    "safety_bypass",
    "external_cost",
}


@dataclass(frozen=True)
class ControlResult:
    id: str
    title: str
    severity: str
    status: str
    evidence: str
    message: str


@dataclass(frozen=True)
class TaskSuiteResult:
    status: str
    path: str
    task_count: int
    risk_grades: list[int]
    control_categories: list[str]
    messages: list[str]


@dataclass(frozen=True)
class QualitySuiteResult:
    status: str
    path: str
    task_count: int
    required_categories: list[str]
    messages: list[str]


@dataclass(frozen=True)
class RedteamSuiteResult:
    status: str
    path: str
    task_count: int
    attack_types: list[str]
    messages: list[str]


@dataclass(frozen=True)
class HarnessReport:
    status: str
    score: int
    max_score: int
    controls: list[ControlResult]
    task_suite: TaskSuiteResult
    quality_suite: QualitySuiteResult
    redteam_suite: RedteamSuiteResult
    handoff_facts: check_handoff_facts.HandoffFactReport

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_text(repo: Path, rel: str | Path) -> str:
    return (repo / rel).read_text(encoding="utf-8")


def _control(
    *,
    passed: bool,
    id: str,
    title: str,
    evidence: str,
    ok: str,
    fail: str,
    severity: str = "required",
) -> ControlResult:
    return ControlResult(
        id=id,
        title=title,
        severity=severity,
        status="PASS" if passed else "FAIL",
        evidence=evidence,
        message=ok if passed else fail,
    )


def _contains_all(text: str, needles: tuple[str, ...]) -> bool:
    return all(needle in text for needle in needles)


def check_codex_hooks_order(repo: Path) -> ControlResult:
    rel = ".codex/hooks.json"
    try:
        raw = json.loads(_read_text(repo, rel))
    except (OSError, json.JSONDecodeError) as exc:
        return _control(
            passed=False,
            id="codex_hooks_order",
            title="SessionStart hook order",
            evidence=rel,
            ok="",
            fail=f"cannot read hook configuration: {exc}",
        )

    commands: list[str] = []
    for group in raw.get("hooks", {}).get("SessionStart", []):
        for hook in group.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str):
                commands.append(command)

    guard_idx = next(
        (
            idx
            for idx, command in enumerate(commands)
            if "scripts/local_concurrency_guard.py --mode session-start" in command
        ),
        None,
    )
    truth_idx = next(
        (
            idx
            for idx, command in enumerate(commands)
            if ".codex/hooks/git_ground_truth.py" in command
        ),
        None,
    )
    passed = guard_idx is not None and truth_idx is not None and guard_idx < truth_idx
    return _control(
        passed=passed,
        id="codex_hooks_order",
        title="SessionStart hook order",
        evidence=rel,
        ok="local concurrency guard runs before git ground truth",
        fail="SessionStart must run local concurrency guard before git ground truth",
    )


def check_git_ground_truth_hook(repo: Path) -> ControlResult:
    rel = ".codex/hooks/git_ground_truth.py"
    try:
        text = _read_text(repo, rel)
    except OSError as exc:
        text = ""
        err = str(exc)
    else:
        err = ""
    passed = _contains_all(
        text,
        (
            "No network here. Run /sync",
            "origin/main...HEAD",
            "HANDOFF entry points",
        ),
    )
    return _control(
        passed=passed,
        id="git_ground_truth",
        title="Local git ground truth",
        evidence=rel,
        ok="hook emits compact local git state and points to sync for network truth",
        fail=err or "hook must emit local state, origin/main distance, and handoff pointers",
    )


def check_local_concurrency_guard(repo: Path) -> ControlResult:
    rel = "scripts/local_concurrency_guard.py"
    try:
        text = _read_text(repo, rel)
    except OSError as exc:
        text = ""
        err = str(exc)
    else:
        err = ""
    passed = _contains_all(text, ("--mode isolate", "pre-commit", "pre-push"))
    return _control(
        passed=passed,
        id="local_concurrency_guard",
        title="Local concurrency guard",
        evidence=rel,
        ok="guard exposes isolation and commit/push protection modes",
        fail=err or "guard must expose isolate, pre-commit, and pre-push protections",
    )


def check_pr_quality_workflow(repo: Path) -> ControlResult:
    rel = ".github/workflows/pr-quality-gate.yml"
    try:
        text = _read_text(repo, rel)
    except OSError as exc:
        text = ""
        err = str(exc)
    else:
        err = ""
    passed = "scripts/check_pr_quality_gate.py" in text and "pull_request" in text
    return _control(
        passed=passed,
        id="pr_quality_workflow",
        title="PR quality-gate workflow",
        evidence=rel,
        ok="PR workflow invokes the quality-gate checker",
        fail=err or "workflow must run scripts/check_pr_quality_gate.py on pull requests",
    )


def check_pr_template(repo: Path) -> ControlResult:
    rel = ".github/pull_request_template.md"
    try:
        text = _read_text(repo, rel)
    except OSError as exc:
        text = ""
        err = str(exc)
    else:
        err = ""
    passed = _contains_all(
        text,
        ("## 하네스 검증", "- 하네스 평가:", "- HANDOFF 검증:"),
    )
    return _control(
        passed=passed,
        id="pr_template_harness_evidence",
        title="PR template harness evidence",
        evidence=rel,
        ok="PR template asks for harness verification evidence",
        fail=err or "PR template must include a harness verification section",
    )


def check_pr_checker(repo: Path) -> ControlResult:
    rel = "scripts/check_pr_quality_gate.py"
    try:
        text = _read_text(repo, rel)
    except OSError as exc:
        text = ""
        err = str(exc)
    else:
        err = ""
    passed = _contains_all(
        text,
        (
            "## 하네스 검증",
            "agent_harness_probe.py --strict",
            "check_handoff_facts.py",
            "하네스 평가",
            "HANDOFF 검증",
        ),
    )
    return _control(
        passed=passed,
        id="pr_checker_harness_evidence",
        title="PR checker harness evidence",
        evidence=rel,
        ok="PR checker enforces harness evidence for operating changes",
        fail=err or "PR checker must enforce harness evidence for grade 2+ changes",
    )


def check_quality_gate_doc(repo: Path) -> ControlResult:
    rel = ".codex/quality-gate.md"
    try:
        text = _read_text(repo, rel)
    except OSError as exc:
        text = ""
        err = str(exc)
    else:
        err = ""
    passed = _contains_all(
        text,
        (
            "agent_harness_probe.py --strict",
            "check_handoff_facts.py",
            "등급 2",
            "운영자 이해 가능 보고",
        ),
    )
    return _control(
        passed=passed,
        id="quality_gate_harness_step",
        title="Local quality gate harness step",
        evidence=rel,
        ok="quality gate names strict harness evaluation for operating changes",
        fail=err or "quality gate must name strict harness evaluation for grade 2+ changes",
    )


def check_agents_doc(repo: Path) -> ControlResult:
    rel = "AGENTS.md"
    try:
        text = _read_text(repo, rel)
    except OSError as exc:
        text = ""
        err = str(exc)
    else:
        err = ""
    passed = _contains_all(
        text,
        ("agent_harness_probe.py --strict", "check_handoff_facts.py", "등급 2", "그래서 뭘 했다는"),
    )
    return _control(
        passed=passed,
        id="agents_operating_rule",
        title="AGENTS harness operating rule",
        evidence=rel,
        ok="AGENTS.md tells Codex when to run the strict harness probe",
        fail=err or "AGENTS.md must name strict harness evaluation for grade 2+ changes",
    )


def check_sdd_feature_pointer(repo: Path) -> ControlResult:
    rel = ".specify/feature.json"
    try:
        data = json.loads(_read_text(repo, rel))
        feature_dir = data.get("feature_directory")
    except (OSError, json.JSONDecodeError) as exc:
        return _control(
            passed=False,
            id="sdd_feature_pointer",
            title="Speckit feature pointer",
            evidence=rel,
            ok="",
            fail=f"cannot read feature pointer: {exc}",
        )

    paths = []
    if isinstance(feature_dir, str) and feature_dir:
        base = repo / feature_dir
        paths = [base / "spec.md", base / "plan.md", base / "tasks.md"]
    passed = bool(paths) and all(path.exists() for path in paths)
    return _control(
        passed=passed,
        id="sdd_feature_pointer",
        title="Speckit feature pointer",
        evidence=f"{rel} -> {feature_dir}",
        ok="active feature pointer resolves to spec, plan, and tasks",
        fail="feature pointer must resolve to a directory with spec.md, plan.md, and tasks.md",
    )


def check_handoff_entrypoint(repo: Path) -> ControlResult:
    rel = "HANDOFF.md"
    try:
        text = _read_text(repo, rel)
    except OSError as exc:
        text = ""
        err = str(exc)
    else:
        err = ""
    passed = _contains_all(text, ("git_ground_truth", "/sync", "AGENTS.md"))
    return _control(
        passed=passed,
        id="handoff_entrypoint",
        title="Handoff entrypoint",
        evidence=rel,
        ok="HANDOFF points new sessions to local truth, sync, and AGENTS.md",
        fail=err or "HANDOFF.md must orient new sessions to ground truth and sync",
    )


def _task_errors(tasks: Any) -> tuple[list[str], set[int], set[str]]:
    errors: list[str] = []
    risk_grades: set[int] = set()
    categories: set[str] = set()
    seen_ids: set[str] = set()

    if not isinstance(tasks, list):
        return ["top-level 'tasks' must be an array"], risk_grades, categories

    for idx, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            errors.append(f"task {idx} must be a table")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not re.fullmatch(r"HARNESS-\d{3}", task_id):
            errors.append(f"task {idx} has invalid id")
        elif task_id in seen_ids:
            errors.append(f"duplicate task id: {task_id}")
        else:
            seen_ids.add(task_id)

        grade = task.get("risk_grade")
        if not isinstance(grade, int) or grade not in REQUIRED_RISK_GRADES:
            errors.append(f"{task_id or idx} has invalid risk_grade")
        else:
            risk_grades.add(grade)

        controls = task.get("expected_controls")
        if not isinstance(controls, list) or not controls:
            errors.append(f"{task_id or idx} must include expected_controls")
        else:
            for control in controls:
                if isinstance(control, str) and control:
                    categories.add(control)
                else:
                    errors.append(f"{task_id or idx} has a non-string expected control")

        criteria = task.get("success_criteria")
        if not isinstance(criteria, list) or not criteria:
            errors.append(f"{task_id or idx} must include success_criteria")

        for field in ("title", "prompt"):
            value = task.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{task_id or idx} must include {field}")

    if len(tasks) < REQUIRED_TASK_COUNT:
        errors.append(f"task suite must contain at least {REQUIRED_TASK_COUNT} tasks")

    missing_grades = REQUIRED_RISK_GRADES - risk_grades
    if missing_grades:
        errors.append(f"missing risk grades: {sorted(missing_grades)}")

    missing_categories = REQUIRED_CONTROL_CATEGORIES - categories
    if missing_categories:
        errors.append(f"missing control categories: {sorted(missing_categories)}")

    return errors, risk_grades, categories


def evaluate_task_suite(repo: Path) -> TaskSuiteResult:
    rel = TASK_SUITE_REL
    try:
        data = tomllib.loads(_read_text(repo, rel))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return TaskSuiteResult(
            status="FAIL",
            path=str(rel),
            task_count=0,
            risk_grades=[],
            control_categories=[],
            messages=[f"cannot read task suite: {exc}"],
        )

    tasks = data.get("tasks")
    errors, risk_grades, categories = _task_errors(tasks)
    task_count = len(tasks) if isinstance(tasks, list) else 0
    return TaskSuiteResult(
        status="PASS" if not errors else "FAIL",
        path=str(rel),
        task_count=task_count,
        risk_grades=sorted(risk_grades),
        control_categories=sorted(categories),
        messages=errors or ["task suite coverage is complete"],
    )


def _task_string_list(
    task: dict[str, Any], field: str, task_id: str | int
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    values: list[str] = []
    raw = task.get(field)
    if not isinstance(raw, list) or not raw:
        errors.append(f"{task_id} must include {field}")
        return values, errors
    for value in raw:
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        else:
            errors.append(f"{task_id} has a non-string {field} entry")
    return values, errors


def _quality_errors(tasks: Any) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    categories: set[str] = set()
    seen_ids: set[str] = set()

    if not isinstance(tasks, list):
        return ["top-level 'tasks' must be an array"], categories

    for idx, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            errors.append(f"task {idx} must be a table")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not re.fullmatch(r"QUALITY-\d{3}", task_id):
            errors.append(f"task {idx} has invalid id")
        elif task_id in seen_ids:
            errors.append(f"duplicate task id: {task_id}")
        else:
            seen_ids.add(task_id)

        label = task_id if isinstance(task_id, str) else idx
        for field in ("title", "prompt"):
            value = task.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label} must include {field}")

        found_categories, category_errors = _task_string_list(
            task, "required_categories", label
        )
        errors.extend(category_errors)
        categories.update(found_categories)

        _criteria, criteria_errors = _task_string_list(task, "success_criteria", label)
        errors.extend(criteria_errors)

    if len(tasks) < REQUIRED_QUALITY_COUNT:
        errors.append(f"quality suite must contain at least {REQUIRED_QUALITY_COUNT} tasks")

    missing_categories = REQUIRED_QUALITY_CATEGORIES - categories
    if missing_categories:
        errors.append(f"missing quality categories: {sorted(missing_categories)}")

    return errors, categories


def evaluate_quality_suite(repo: Path) -> QualitySuiteResult:
    rel = QUALITY_SUITE_REL
    try:
        data = tomllib.loads(_read_text(repo, rel))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return QualitySuiteResult(
            status="FAIL",
            path=str(rel),
            task_count=0,
            required_categories=[],
            messages=[f"cannot read quality suite: {exc}"],
        )

    tasks = data.get("tasks")
    errors, categories = _quality_errors(tasks)
    task_count = len(tasks) if isinstance(tasks, list) else 0
    return QualitySuiteResult(
        status="PASS" if not errors else "FAIL",
        path=str(rel),
        task_count=task_count,
        required_categories=sorted(categories),
        messages=errors or ["quality suite coverage is complete"],
    )


def _redteam_errors(tasks: Any) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    attack_types: set[str] = set()
    seen_ids: set[str] = set()

    if not isinstance(tasks, list):
        return ["top-level 'tasks' must be an array"], attack_types

    for idx, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            errors.append(f"task {idx} must be a table")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not re.fullmatch(r"REDTEAM-\d{3}", task_id):
            errors.append(f"task {idx} has invalid id")
        elif task_id in seen_ids:
            errors.append(f"duplicate task id: {task_id}")
        else:
            seen_ids.add(task_id)

        label = task_id if isinstance(task_id, str) else idx
        for field in ("title", "prompt"):
            value = task.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label} must include {field}")

        attack_type = task.get("attack_type")
        if not isinstance(attack_type, str) or not attack_type.strip():
            errors.append(f"{label} must include attack_type")
        elif attack_type not in REQUIRED_REDTEAM_ATTACK_TYPES:
            errors.append(f"{label} has unknown attack_type: {attack_type}")
        else:
            attack_types.add(attack_type)

        _behaviors, behavior_errors = _task_string_list(
            task, "expected_behaviors", label
        )
        errors.extend(behavior_errors)

        _criteria, criteria_errors = _task_string_list(task, "success_criteria", label)
        errors.extend(criteria_errors)

    if len(tasks) < REQUIRED_REDTEAM_COUNT:
        errors.append(f"redteam suite must contain at least {REQUIRED_REDTEAM_COUNT} tasks")

    missing_attacks = REQUIRED_REDTEAM_ATTACK_TYPES - attack_types
    if missing_attacks:
        errors.append(f"missing redteam attack types: {sorted(missing_attacks)}")

    return errors, attack_types


def evaluate_redteam_suite(repo: Path) -> RedteamSuiteResult:
    rel = REDTEAM_SUITE_REL
    try:
        data = tomllib.loads(_read_text(repo, rel))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return RedteamSuiteResult(
            status="FAIL",
            path=str(rel),
            task_count=0,
            attack_types=[],
            messages=[f"cannot read redteam suite: {exc}"],
        )

    tasks = data.get("tasks")
    errors, attack_types = _redteam_errors(tasks)
    task_count = len(tasks) if isinstance(tasks, list) else 0
    return RedteamSuiteResult(
        status="PASS" if not errors else "FAIL",
        path=str(rel),
        task_count=task_count,
        attack_types=sorted(attack_types),
        messages=errors or ["redteam suite coverage is complete"],
    )


def evaluate(repo: Path) -> HarnessReport:
    controls = [
        check_codex_hooks_order(repo),
        check_git_ground_truth_hook(repo),
        check_local_concurrency_guard(repo),
        check_pr_quality_workflow(repo),
        check_pr_template(repo),
        check_pr_checker(repo),
        check_quality_gate_doc(repo),
        check_agents_doc(repo),
        check_sdd_feature_pointer(repo),
        check_handoff_entrypoint(repo),
    ]
    task_suite = evaluate_task_suite(repo)
    quality_suite = evaluate_quality_suite(repo)
    redteam_suite = evaluate_redteam_suite(repo)
    handoff_facts = check_handoff_facts.evaluate(repo)
    controls.append(
        _control(
            passed=task_suite.status == "PASS",
            id="evaluation_task_suite",
            title="Harness regression task suite",
            evidence=task_suite.path,
            ok="task suite covers required risk grades and control categories",
            fail="; ".join(task_suite.messages),
        )
    )
    controls.append(
        _control(
            passed=quality_suite.status == "PASS",
            id="quality_task_suite",
            title="First-response quality task suite",
            evidence=quality_suite.path,
            ok="quality suite covers required first-response categories",
            fail="; ".join(quality_suite.messages),
        )
    )
    controls.append(
        _control(
            passed=redteam_suite.status == "PASS",
            id="redteam_task_suite",
            title="Operating redteam task suite",
            evidence=redteam_suite.path,
            ok="redteam suite covers required failure modes",
            fail="; ".join(redteam_suite.messages),
        )
    )
    controls.append(
        _control(
            passed=handoff_facts.status == "OK",
            id="handoff_fact_check",
            title="HANDOFF summary facts",
            evidence="HANDOFF.md",
            ok="HANDOFF summary rows match local repository facts",
            fail="; ".join(fact.message for fact in handoff_facts.facts),
        )
    )

    required = [control for control in controls if control.severity == "required"]
    score = sum(1 for control in required if control.status == "PASS")
    max_score = len(required)
    status = "OK" if score == max_score else "DEGRADED"
    return HarnessReport(
        status=status,
        score=score,
        max_score=max_score,
        controls=controls,
        task_suite=task_suite,
        quality_suite=quality_suite,
        redteam_suite=redteam_suite,
        handoff_facts=handoff_facts,
    )


def render_text(report: HarnessReport) -> str:
    lines = [
        "에이전트 하네스 평가",
        f"종합 판정: {report.status} ({report.score}/{report.max_score})",
        "",
        "통제 항목:",
    ]
    for control in report.controls:
        lines.append(
            f"- {control.status} {control.id}: {control.message} [{control.evidence}]"
        )
    lines.extend(
        [
            "",
            "평가 과제 묶음:",
            f"- 상태: {report.task_suite.status}",
            f"- 과제 수: {report.task_suite.task_count}",
            f"- 위험 등급: {report.task_suite.risk_grades}",
            f"- 통제 범주: {report.task_suite.control_categories}",
            "",
            "첫 판단 품질 과제 묶음:",
            f"- 상태: {report.quality_suite.status}",
            f"- 과제 수: {report.quality_suite.task_count}",
            f"- 필수 범주: {report.quality_suite.required_categories}",
            "",
            "레드팀 과제 묶음:",
            f"- 상태: {report.redteam_suite.status}",
            f"- 과제 수: {report.redteam_suite.task_count}",
            f"- 공격 유형: {report.redteam_suite.attack_types}",
            "",
            "HANDOFF 사실 검증:",
            f"- 상태: {report.handoff_facts.status}",
        ]
    )
    for fact in report.handoff_facts.facts:
        lines.append(f"- {fact.status} {fact.id}: {fact.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the local Codex agent harness.")
    parser.add_argument("--repo", type=Path, default=REPO, help="Repository root to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when a required harness control fails.",
    )
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    report = evaluate(repo)
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(render_text(report))

    if args.strict and report.status != "OK":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
