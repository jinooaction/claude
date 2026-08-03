"""Live canary workflow production-gate boundaries."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "rebalance-live-canary.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _preview_job(text: str) -> str:
    return text.split("  live_portfolio_canary_preview:", 1)[1].split(
        "\n  live_portfolio_canary_real_orders:", 1
    )[0]


def _real_order_job(text: str) -> str:
    return text.split("  live_portfolio_canary_real_orders:", 1)[1]


def test_live_canary_preview_job_publishes_sidecar_without_production_gate() -> None:
    text = _workflow_text()
    preview = _preview_job(text)

    assert "\n    environment: production\n" not in preview
    assert "Publish live canary result to sidecar branch" in preview
    assert "preview-job-skipped" in preview
    assert "production-gated job" in preview
    assert "observe live-canary-backfill" in preview
    assert "observe live-canary-preview ${CAP}" in preview
    assert "observe live-canary-measure ${CAP}" in preview
    assert "refused command: observe live-canary" in preview
    assert "cd /opt/auto-invest" not in preview
    assert "--mode live --confirm-live" not in preview
    assert "LIVE rebalance — REAL ORDERS" not in preview
    measure = preview.split("Measure live track", 1)[1].split("\n      - name:", 1)[0]
    assert "steps.gate.outputs.armed != 'true'" in measure


def test_live_canary_real_orders_remain_behind_production_gate() -> None:
    text = _workflow_text()
    real_order = _real_order_job(text)
    header = real_order.split("\n    steps:", 1)[0]

    assert "needs: live_portfolio_canary_preview" in header
    assert "needs.live_portfolio_canary_preview.outputs.armed == 'true'" in header
    assert "needs.live_portfolio_canary_preview.outputs.blocked != 'true'" in header
    assert "github.event_name != 'push'" in header
    assert "\n    environment: production\n" in real_order
    assert "Validate production live gate outputs" in real_order
    assert "LIVE rebalance — REAL ORDERS" in real_order
    assert "--mode live --confirm-live" in real_order
