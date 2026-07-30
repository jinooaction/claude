"""Regression tests for fixed observation commands in SSH-backed workflows."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER_WORKFLOW = ROOT / ".github" / "workflows" / "rebalance-paper-forward.yml"
LADDER_WORKFLOW = ROOT / ".github" / "workflows" / "forward-edge-autoarm.yml"


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
