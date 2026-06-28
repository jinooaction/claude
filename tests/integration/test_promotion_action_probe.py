"""스펙 069 — 자율 승격 실행 루프 probe 통합 테스트."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE_PATH = _REPO_ROOT / "scripts" / "promotion_action_probe.py"
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "promotion_actions" / "fresh"
_ACTIONS_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "autonomous-promotion-actions.yml"
_FORWARD_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "promotion-forward-tracks.yml"
_CANARY_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "promotion-canary-submissions.yml"

_spec = importlib.util.spec_from_file_location("promotion_action_probe", _PROBE_PATH)
assert _spec and _spec.loader
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
probe_main = _probe.main


def test_probe_json_output_includes_actions(capsys) -> None:
    rc = probe_main(
        [
            "--promotion-summary",
            str(_FIXTURES / "promotion_summary.json"),
            "--forward-registry",
            str(_FIXTURES / "promotion-forward-registry.json"),
            "--canary-submissions",
            str(_FIXTURES / "promotion-canary-submissions.json"),
            "--json",
            "--now",
            "2026-06-29T00:00:00Z",
            "--commit",
            "abc1234",
            "--run-id",
            "test-run",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "test-run"
    assert payload["actions"]
    assert payload["forward_registry_next"]["tracks"]
    assert payload["canary_submissions_next"]["submissions"]


def test_probe_writes_sidecar_and_next_state_artifacts(tmp_path, capsys) -> None:
    summary = tmp_path / "LAST_RUN.md"
    actions_json = tmp_path / "promotion_actions.json"
    registry = tmp_path / "promotion-forward-registry.json"
    submissions = tmp_path / "promotion-canary-submissions.json"
    rc = probe_main(
        [
            "--promotion-summary",
            str(_FIXTURES / "promotion_summary.json"),
            "--forward-registry",
            str(_FIXTURES / "promotion-forward-registry.json"),
            "--canary-submissions",
            str(_FIXTURES / "promotion-canary-submissions.json"),
            "--summary-out",
            str(summary),
            "--json-out",
            str(actions_json),
            "--forward-registry-out",
            str(registry),
            "--canary-submissions-out",
            str(submissions),
            "--now",
            "2026-06-29T00:00:00Z",
            "--commit",
            "abc1234",
        ]
    )
    assert rc == 0
    assert "자율 승격 실행 루프" in summary.read_text(encoding="utf-8")
    assert json.loads(actions_json.read_text(encoding="utf-8"))["actions"]
    assert json.loads(registry.read_text(encoding="utf-8"))["tracks"]
    assert json.loads(submissions.read_text(encoding="utf-8"))["submissions"]
    assert "실거래 sentinel을 변경하지 않는다" in capsys.readouterr().out


def test_actions_workflow_publishes_sidecar_without_secrets_or_ssh() -> None:
    text = _ACTIONS_WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in text and "workflow_dispatch:" in text
    assert "automation/autonomous-promotion-actions-last-run" in text
    assert "promotion_action_probe.py" in text
    assert "promotion_actions.json" in text
    assert "promotion-forward-registry.json" in text
    assert "promotion-canary-submissions.json" in text
    assert "VULTR_SSH" not in text
    assert "KIS_" not in text
    assert "ssh " not in text and "ssh -" not in text
    assert "--mode live" not in text
    assert "--confirm-live" not in text


def test_promotion_forward_workflow_is_paper_only_and_publishes_sidecar() -> None:
    text = _FORWARD_WORKFLOW.read_text(encoding="utf-8")
    assert "automation/promotion-forward-last-run" in text
    assert "automation/autonomous-promotion-actions-last-run" in text
    assert "promotion-forward-registry.next.json" in text
    assert "promotion-forward-registry.json" in text
    assert "rebalance-once" in text
    assert "--mode paper" in text
    assert "--mode live" not in text
    assert "--confirm-live" not in text
    assert "rebalance-live.request" not in text


def test_promotion_canary_workflow_runs_hardened_canary_without_live_order_path() -> None:
    text = _CANARY_WORKFLOW.read_text(encoding="utf-8")
    assert "automation/promotion-canary-last-run" in text
    assert "automation/autonomous-promotion-actions-last-run" in text
    assert "promotion-canary-submissions.next.json" in text
    assert "promotion-canary-submissions.json" in text
    assert "canary-portfolio" in text
    assert "--mode live" not in text
    assert "--confirm-live" not in text
    assert "rebalance-live.request" not in text
