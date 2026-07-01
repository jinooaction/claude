"""스펙 077 — 자율 작업 실행 probe/workflow 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from auto_invest.analytics.pipeline_liveness import default_specs

_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _ROOT / "scripts" / "autonomous_work_execution_probe.py"
_spec = importlib.util.spec_from_file_location("autonomous_work_execution_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_manifest_matches_contract(capsys):
    rc = probe_main(["--manifest"])

    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == [
        (
            "capital-path-readiness\tautomation/capital-path-readiness-last-run\t"
            "capital_path_readiness.json"
        ),
        "evolution-backlog\tautomation/autonomous-evolution-last-run\tcandidate_backlog.json",
        "evolution-ledger\tautomation/autonomous-evolution-last-run\tlearning_ledger.json",
        "autonomous-promotion\tautomation/autonomous-promotion-last-run\tpromotion_summary.json",
        (
            "candidate-implementation-factory\t"
            "automation/candidate-implementation-factory-last-run\tcandidate_factory.json"
        ),
        (
            "candidate-packages\tautomation/candidate-implementation-factory-last-run\t"
            "candidate_packages.json"
        ),
        (
            "candidate-result-executor\tautomation/candidate-implementation-results\t"
            "candidate_results.json"
        ),
        "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md",
    ]


def test_probe_writes_json_and_markdown(tmp_path, capsys):
    (tmp_path / "capital-path-readiness.md").write_text(
        json.dumps(
            {
                "readiness_state": "ACCUMULATING_EDGE",
                "live_money_status": "PREVIEW_ONLY",
                "priority_candidates": [
                    {
                        "candidate_id": "candidate-fd04772a23c5",
                        "domain_key": "live_readiness",
                        "status": "new",
                        "score": 597,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "pipeline-liveness.md").write_text(
        "## 결정 JSON\n\n```json\n{\"overall\":\"OK\",\"checks\":[]}\n```\n",
        encoding="utf-8",
    )

    json_out = tmp_path / "autonomous_work_execution.json"
    summary_out = tmp_path / "LAST_RUN.md"
    rc = probe_main(
        [
            "--evidence-dir",
            str(tmp_path),
            "--json",
            "--json-out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            "--now",
            "2026-07-01T09:10:00Z",
            "--run-id",
            "123",
            "--commit",
            "abc123",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(json_out.read_text(encoding="utf-8"))
    assert printed == written
    assert written["selected_work"]["candidate_id"] == "candidate-fd04772a23c5"
    assert written["selected_work"]["status"] == "EXECUTION_READY"
    assert written["run_id"] == "123"
    assert written["commit"] == "abc123"
    assert "자율 작업 실행 루프" in summary_out.read_text(encoding="utf-8")


def test_pipeline_liveness_registers_autonomous_work_execution():
    specs = {spec.key: spec for spec in default_specs()}

    assert "autonomous-work-execution" in specs
    assert specs["autonomous-work-execution"].branch == (
        "automation/autonomous-work-execution-last-run"
    )
    assert specs["autonomous-work-execution"].critical is False


def test_workflow_stays_read_only_safety_contract():
    workflow = (_ROOT / ".github" / "workflows" / "autonomous-work-execution.yml").read_text(
        encoding="utf-8"
    )

    forbidden = [
        "KIS_",
        "ssh ",
        "ssh -",
        "rebalance-live --mode live",
        "--confirm-live",
        "place-order",
        "submit-order",
        "gh pr create",
        "git push origin main",
    ]
    for token in forbidden:
        assert token not in workflow
    assert "automation/autonomous-work-execution-last-run" in workflow
