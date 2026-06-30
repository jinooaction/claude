"""스펙 071 — 후보 결과 실행기 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.candidate_factory import build_candidate_factory_run

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _REPO_ROOT / "scripts" / "candidate_result_executor_probe.py"
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "candidate_factory" / "fresh"
_RESULT_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "candidate-result-executor.yml"
_FACTORY_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "candidate-implementation-factory.yml"

_spec = importlib.util.spec_from_file_location("candidate_result_executor_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def _json(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _write_package_plan(path: Path) -> None:
    run = build_candidate_factory_run(
        candidate_backlog=_json("candidate_backlog.json"),
        promotion_summary=_json("promotion_summary.json"),
        commit="abc1234",
        run_id="factory",
    )
    path.write_text(json.dumps(run.package_plan_dict(), ensure_ascii=False), encoding="utf-8")


def test_probe_writes_pending_results_when_runtime_data_is_absent(tmp_path, capsys) -> None:
    package_plan = tmp_path / "candidate_packages.json"
    _write_package_plan(package_plan)
    summary = tmp_path / "LAST_RUN.md"
    summary_json = tmp_path / "candidate_result_executor.json"
    results = tmp_path / "candidate_results.json"

    rc = probe_main(
        [
            "--package-plan",
            str(package_plan),
            "--summary-out",
            str(summary),
            "--json-out",
            str(summary_json),
            "--results-out",
            str(results),
            "--timeout-seconds",
            "1",
            "--now",
            "2026-06-30T03:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "test-run",
        ]
    )
    assert rc == 0
    assert "후보 결과 실행기" in summary.read_text(encoding="utf-8")
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    assert payload["run_id"] == "test-run"
    assert len(payload["results"]) == 9
    assert payload["diagnostic_counts"]
    result_doc = json.loads(results.read_text(encoding="utf-8"))
    assert result_doc["results"]
    pending = [item for item in result_doc["results"] if item["status"] == "pending"]
    assert pending
    assert all(item.get("diagnostics") for item in pending)
    assert all(item.get("next_actions") for item in pending)
    assert "진단 집계" in summary.read_text(encoding="utf-8")
    assert "주문, 자본 사다리" in capsys.readouterr().out


def test_result_executor_workflow_publishes_sidecar_without_order_or_broker_path() -> None:
    text = _RESULT_WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text and "workflow_dispatch:" in text
    assert "42 8 * * *" in text
    assert "automation/candidate-implementation-factory-last-run:candidate_packages.json" in text
    assert "automation/candidate-implementation-results" in text
    assert "candidate_result_executor_probe.py" in text
    assert "candidate_results.json" in text
    assert "KIS_" not in text
    assert "VULTR_SSH" not in text
    assert "ssh " not in text and "ssh -" not in text
    assert "--mode live" not in text
    assert "--confirm-live" not in text
    assert "rebalance-live.request" not in text


def test_factory_workflow_collects_candidate_result_sidecar() -> None:
    text = _FACTORY_WORKFLOW.read_text(encoding="utf-8")
    assert "+refs/heads/automation/*:refs/remotes/origin/automation/*" in text
    assert "automation/candidate-implementation-results:candidate_results.json" in text
