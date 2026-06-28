"""스펙 067 — 자율 성장 루프 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _REPO_ROOT / "scripts" / "evolution_loop_probe.py"
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "evolution_loop" / "fresh"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "autonomous-evolution-loop.yml"

_spec = importlib.util.spec_from_file_location("evolution_loop_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_manifest_lists_required_sidecars(capsys) -> None:
    rc = probe_main(["--manifest"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "money-path\tautomation/money-path-last-run\tLAST_RUN.md" in out
    assert "reassign\tautomation/reassign-last-run\tLAST_RUN.md" in out
    assert "pipeline-liveness\tautomation/pipeline-liveness-last-run\tLAST_RUN.md" in out


def test_probe_json_output_includes_expected_sections(capsys) -> None:
    rc = probe_main(
        [
            "--evidence-dir",
            str(_FIXTURES),
            "--json",
            "--now",
            "2026-06-29T01:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "test-run",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "test-run"
    assert payload["top_breakthrough_candidates"]
    assert payload["safe_high_leverage_work"]
    assert "market_observation" in payload["evidence_dependencies"]
    assert payload["operator_review"] == []


def test_probe_writes_sidecar_artifacts(tmp_path, capsys) -> None:
    summary = tmp_path / "LAST_RUN.md"
    summary_json = tmp_path / "evolution_summary.json"
    ledger = tmp_path / "learning_ledger.json"
    backlog = tmp_path / "candidate_backlog.json"
    rc = probe_main(
        [
            "--evidence-dir",
            str(_FIXTURES),
            "--summary-out",
            str(summary),
            "--json-out",
            str(summary_json),
            "--ledger-out",
            str(ledger),
            "--candidate-backlog-out",
            str(backlog),
            "--now",
            "2026-06-29T01:00:00Z",
            "--commit",
            "abc1234",
        ]
    )
    assert rc == 0
    assert "자율 성장 루프" in summary.read_text(encoding="utf-8")
    assert json.loads(summary_json.read_text(encoding="utf-8"))["candidates"]
    assert json.loads(ledger.read_text(encoding="utf-8"))["entries"]
    assert json.loads(backlog.read_text(encoding="utf-8"))["candidates"]
    assert "주문, 자본, whitelist, caps, live 전략은 변경하지 않았습니다" in capsys.readouterr().out


def test_autonomous_evolution_workflow_is_read_only_and_publishes_sidecar() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text and "workflow_dispatch:" in text
    assert "automation/autonomous-evolution-last-run" in text
    assert "evolution_loop_probe.py --manifest" in text
    assert "--candidate-backlog-out" in text
    assert "VULTR_SSH" not in text
    assert "KIS_" not in text
    assert "ssh " not in text and "ssh -" not in text
    assert text.count("set -euo pipefail") == 4
    assert "no orders, no capital change, no whitelist/caps change, no live strategy change" in text
