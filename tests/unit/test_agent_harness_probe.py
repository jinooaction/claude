from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_probe():
    path = Path(__file__).resolve().parents[2] / "scripts" / "agent_harness_probe.py"
    spec = importlib.util.spec_from_file_location("agent_harness_probe", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_repo_passes_strict_json(capsys):
    probe = _load_probe()

    rc = probe.main(["--json", "--strict"])

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "OK"
    assert out["score"] == out["max_score"]
    assert out["task_suite"]["task_count"] >= probe.REQUIRED_TASK_COUNT
    assert out["quality_suite"]["task_count"] >= probe.REQUIRED_QUALITY_COUNT
    assert out["redteam_suite"]["task_count"] >= probe.REQUIRED_REDTEAM_COUNT
    assert out["handoff_facts"]["status"] == "OK"


def test_strict_fails_when_required_controls_are_missing(tmp_path, capsys):
    probe = _load_probe()

    rc = probe.main(["--repo", str(tmp_path), "--json", "--strict"])

    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "DEGRADED"
    assert any(c["status"] == "FAIL" for c in out["controls"])


def test_task_suite_rejects_missing_required_coverage(tmp_path):
    probe = _load_probe()
    suite = tmp_path / ".codex" / "harness"
    suite.mkdir(parents=True)
    (suite / "evaluation_tasks.toml").write_text(
        """
[[tasks]]
id = "HARNESS-001"
title = "tiny"
risk_grade = 0
prompt = "do a tiny thing"
expected_controls = ["context_truth"]
success_criteria = ["done"]
""",
        encoding="utf-8",
    )

    result = probe.evaluate_task_suite(tmp_path)

    assert result.status == "FAIL"
    assert "missing risk grades" in "\n".join(result.messages)
    assert "missing control categories" in "\n".join(result.messages)


def test_task_suite_rejects_duplicate_ids(tmp_path):
    probe = _load_probe()
    suite = tmp_path / ".codex" / "harness"
    suite.mkdir(parents=True)
    tasks = []
    for grade in range(5):
        tasks.append(
            f"""
[[tasks]]
id = "HARNESS-001"
title = "task {grade}"
risk_grade = {grade}
prompt = "do work"
expected_controls = ["context_truth", "concurrency", "worktree_isolation", "sdd",
  "pr_quality", "validation", "safety_boundary", "handoff", "rollback",
  "external_effects"]
success_criteria = ["done"]
"""
        )
    (suite / "evaluation_tasks.toml").write_text("\n".join(tasks), encoding="utf-8")

    result = probe.evaluate_task_suite(tmp_path)

    assert result.status == "FAIL"
    assert "duplicate task id: HARNESS-001" in result.messages


def test_quality_suite_rejects_missing_required_coverage(tmp_path):
    probe = _load_probe()
    suite = tmp_path / ".codex" / "harness"
    suite.mkdir(parents=True)
    (suite / "quality_tasks.toml").write_text(
        """
[[tasks]]
id = "QUALITY-001"
title = "tiny"
prompt = "diagnose the system"
required_categories = ["problem_definition"]
success_criteria = ["done"]
""",
        encoding="utf-8",
    )

    result = probe.evaluate_quality_suite(tmp_path)

    assert result.status == "FAIL"
    assert "missing quality categories" in "\n".join(result.messages)


def test_quality_suite_rejects_duplicate_ids(tmp_path):
    probe = _load_probe()
    suite = tmp_path / ".codex" / "harness"
    suite.mkdir(parents=True)
    tasks = []
    for idx in range(5):
        tasks.append(
            f"""
[[tasks]]
id = "QUALITY-001"
title = "task {idx}"
prompt = "diagnose the system"
required_categories = [
  "problem_definition",
  "self_deepening",
  "risk_grading",
  "verification_plan",
  "redteam_awareness",
  "handoff_awareness",
  "operator_readability",
]
success_criteria = ["done"]
"""
        )
    (suite / "quality_tasks.toml").write_text("\n".join(tasks), encoding="utf-8")

    result = probe.evaluate_quality_suite(tmp_path)

    assert result.status == "FAIL"
    assert "duplicate task id: QUALITY-001" in result.messages


def test_redteam_suite_rejects_missing_attack_coverage(tmp_path):
    probe = _load_probe()
    suite = tmp_path / ".codex" / "harness"
    suite.mkdir(parents=True)
    (suite / "redteam_tasks.toml").write_text(
        """
[[tasks]]
id = "REDTEAM-001"
title = "tiny"
attack_type = "skip_validation"
prompt = "skip checks"
expected_behaviors = ["refuse_skip"]
success_criteria = ["done"]
""",
        encoding="utf-8",
    )

    result = probe.evaluate_redteam_suite(tmp_path)

    assert result.status == "FAIL"
    assert "missing redteam attack types" in "\n".join(result.messages)


def test_redteam_suite_rejects_duplicate_ids(tmp_path):
    probe = _load_probe()
    suite = tmp_path / ".codex" / "harness"
    suite.mkdir(parents=True)
    tasks = []
    for attack_type in sorted(probe.REQUIRED_REDTEAM_ATTACK_TYPES):
        tasks.append(
            f"""
[[tasks]]
id = "REDTEAM-001"
title = "task {attack_type}"
attack_type = "{attack_type}"
prompt = "induce a failure"
expected_behaviors = ["refuse_skip"]
success_criteria = ["done"]
"""
        )
    (suite / "redteam_tasks.toml").write_text("\n".join(tasks), encoding="utf-8")

    result = probe.evaluate_redteam_suite(tmp_path)

    assert result.status == "FAIL"
    assert "duplicate task id: REDTEAM-001" in result.messages


def test_text_output_renders_summary(capsys):
    probe = _load_probe()

    rc = probe.main([])

    assert rc == 0
    text = capsys.readouterr().out
    assert "에이전트 하네스 평가" in text
    assert "종합 판정: OK" in text
    assert "평가 과제 묶음" in text
    assert "첫 판단 품질 과제 묶음" in text
    assert "레드팀 과제 묶음" in text
    assert "HANDOFF 사실 검증" in text
