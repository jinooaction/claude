"""스펙 070 — 후보 구현 공장 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _REPO_ROOT / "scripts" / "candidate_factory_probe.py"
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "candidate_factory" / "fresh"
_FACTORY_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "candidate-implementation-factory.yml"
_PROMOTION_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "autonomous-promotion-loop.yml"

_spec = importlib.util.spec_from_file_location("candidate_factory_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_json_output_includes_packages(capsys) -> None:
    rc = probe_main(
        [
            "--candidate-backlog",
            str(_FIXTURES / "candidate_backlog.json"),
            "--promotion-summary",
            str(_FIXTURES / "promotion_summary.json"),
            "--json",
            "--now",
            "2026-06-29T03:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "test-run",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "test-run"
    assert len(payload["packages"]) == 9
    assert payload["enriched_candidate_backlog"]["candidates"]


def test_probe_writes_sidecar_artifacts(tmp_path, capsys) -> None:
    summary = tmp_path / "LAST_RUN.md"
    summary_json = tmp_path / "candidate_factory.json"
    enriched = tmp_path / "candidate_backlog.enriched.json"
    packages = tmp_path / "candidate_packages.json"
    rc = probe_main(
        [
            "--candidate-backlog",
            str(_FIXTURES / "candidate_backlog.json"),
            "--promotion-summary",
            str(_FIXTURES / "promotion_summary.json"),
            "--result-evidence",
            str(_FIXTURES / "result_evidence.json"),
            "--summary-out",
            str(summary),
            "--json-out",
            str(summary_json),
            "--enriched-backlog-out",
            str(enriched),
            "--package-plan-out",
            str(packages),
            "--now",
            "2026-06-29T03:00:00Z",
            "--commit",
            "abc1234",
        ]
    )
    assert rc == 0
    assert "후보 구현 공장" in summary.read_text(encoding="utf-8")
    assert json.loads(summary_json.read_text(encoding="utf-8"))["packages"]
    assert json.loads(enriched.read_text(encoding="utf-8"))["candidates"][0][
        "promotion_evidence"
    ]["historical_backtest"] == "pass"
    assert json.loads(packages.read_text(encoding="utf-8"))["packages"]
    assert "주문, 자본 사다리" in capsys.readouterr().out


def test_factory_workflow_publishes_sidecar_without_order_or_broker_path() -> None:
    text = _FACTORY_WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text and "workflow_dispatch:" in text
    assert "40 8 * * *" in text
    assert "+refs/heads/automation/*:refs/remotes/origin/automation/*" in text
    assert (
        "automation/candidate-implementation-results || true" not in text
    )
    assert "automation/candidate-implementation-factory-last-run" in text
    assert "candidate_factory_probe.py" in text
    assert "candidate_backlog.enriched.json" in text
    assert "candidate_packages.json" in text
    assert "KIS_" not in text
    assert "VULTR_SSH" not in text
    assert "ssh " not in text and "ssh -" not in text
    assert "--mode live" not in text
    assert "--confirm-live" not in text
    assert "rebalance-live.request" not in text


def test_promotion_workflow_prefers_factory_enriched_backlog() -> None:
    text = _PROMOTION_WORKFLOW.read_text(encoding="utf-8")
    assert "candidate-implementation-factory-last-run:candidate_backlog.enriched.json" in text
    assert "candidate-factory: enriched backlog collected" in text
    assert "using autonomous-evolution backlog" in text
    assert (
        "candidate-factory automation/candidate-implementation-factory-last-run LAST_RUN.md"
        in text
    )
