"""Regression tests for fixed observation commands in SSH-backed workflows."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER_WORKFLOW = ROOT / ".github" / "workflows" / "rebalance-paper-forward.yml"
LADDER_WORKFLOW = ROOT / ".github" / "workflows" / "forward-edge-autoarm.yml"
ANCHORED_WORKFLOW = ROOT / ".github" / "workflows" / "forward-anchored-verdict.yml"
PROMOTE_WORKFLOW = ROOT / ".github" / "workflows" / "promote-readiness.yml"
RESULT_WORKFLOW = ROOT / ".github" / "workflows" / "candidate-result-executor.yml"


def test_paper_forward_uses_fixed_observe_gateway_commands() -> None:
    body = PAPER_WORKFLOW.read_text(encoding="utf-8")

    assert "observe halt-status" in body
    assert "observe signal-ic trend" in body
    for track in [
        "trend",
        "notrend",
        "rmbeta",
        "multiasset",
        "global",
        "globalfixed",
        "wide",
    ]:
        assert f"observe paper-track-run {track} " in body
        assert f"observe paper-track-verdict {track}" in body

    assert "cd /opt/auto-invest" not in body
    assert "/usr/local/bin/uv run auto-invest" not in body
    assert "bash -s" not in body


def test_capital_ladder_uses_fixed_observe_gateway_commands() -> None:
    body = LADDER_WORKFLOW.read_text(encoding="utf-8")

    assert "observe ladder-forward-verdict" in body
    assert "observe ladder-anchored-verdict" in body
    assert "observe account-nav" in body
    assert "observe live-growth" in body
    assert "cd /opt/auto-invest" not in body
    assert "/usr/local/bin/uv run auto-invest" not in body
    assert "bash -s" not in body


def test_forward_anchored_uses_fixed_observe_gateway_command() -> None:
    body = ANCHORED_WORKFLOW.read_text(encoding="utf-8")

    assert "observe ladder-anchored-verdict" in body
    assert "cd /opt/auto-invest" not in body
    assert "/usr/local/bin/uv run auto-invest" not in body
    assert "bash -s" not in body


def test_promote_readiness_uses_fixed_observe_gateway_command() -> None:
    body = PROMOTE_WORKFLOW.read_text(encoding="utf-8")

    assert "observe promote-readiness" in body
    assert "cd /opt/auto-invest" not in body
    assert "/usr/local/bin/uv run auto-invest" not in body
    assert "bash -s" not in body


def test_candidate_result_history_uses_fixed_observe_gateway_command() -> None:
    body = RESULT_WORKFLOW.read_text(encoding="utf-8")

    assert "observe candidate-history" in body
    assert "ssh -n -o StrictHostKeyChecking=yes" in body
    assert "candidate_history_support_probe.py --manifest" in body
    assert "/tmp/candidate_result_history" in body
    assert "CANDIDATE_HISTORY_ARCHIVE_BEGIN" in body
    assert "scp " not in body
    assert "bash -s" not in body
    assert "cd /opt/auto-invest" not in body
    assert "/usr/local/bin/uv run auto-invest" not in body
