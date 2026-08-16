"""Live canary workflow production-gate boundaries."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "rebalance-live-canary.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _preview_job(text: str) -> str:
    return text.split("  live_portfolio_canary_preview:", 1)[1].split(
        "\n  autonomous_live_approval:", 1
    )[0]


def _approval_job(text: str) -> str:
    return text.split("  autonomous_live_approval:", 1)[1].split(
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


def test_live_canary_machine_approval_is_main_only_and_event_explicit() -> None:
    approval = _approval_job(_workflow_text())

    assert "needs: live_portfolio_canary_preview" in approval
    assert "github.event_name == 'schedule'" in approval
    assert "github.event_name == 'workflow_dispatch'" in approval
    assert "uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in approval
    assert '[[ "${REF}" == "refs/heads/main" ]]' in approval
    assert "Validate autonomous production approval evidence" in approval
    assert 'schedule) decision="scheduled-real-order"' in approval
    assert 'workflow_dispatch) decision="manual-no-order-preflight"' in approval
    assert "AUTONOMOUS_PRODUCTION_APPROVED" in approval
    assert "LIVE_ORDER_SIGNING_KEY" not in approval
    assert "environment: production" not in approval


def test_live_canary_real_orders_remain_behind_machine_and_production_gates() -> None:
    text = _workflow_text()
    real_order = _real_order_job(text)
    header = real_order.split("\n    steps:", 1)[0]

    assert "needs: [live_portfolio_canary_preview, autonomous_live_approval]" in header
    assert "needs.autonomous_live_approval.result == 'success'" in header
    assert "needs.autonomous_live_approval.outputs.decision" in header
    assert "\n    environment: production\n" in real_order
    assert "Validate production live gate outputs" in real_order
    assert 'decision="${{ needs.autonomous_live_approval.outputs.decision }}"' in real_order
    assert "Authorize request — scheduled runs place real orders" in real_order
    assert "LIVE_ORDER_SIGNING_KEY: ${{ secrets.LIVE_ORDER_SIGNING_KEY }}" in real_order
    assert "openssl pkeyutl -sign -rawin" in real_order
    assert 'gateway_action="live-canary-order"' in real_order
    assert 'gateway_action="live-canary-verify-order"' in real_order
    assert '[[ "${EVENT}" == "workflow_dispatch" ]]' in real_order
    assert '"${gateway_action} ${GITHUB_RUN_ID}' in real_order
    assert "real orders=0" in real_order
    assert "${GITHUB_RUN_ATTEMPT}" in real_order

    helper = (ROOT / "deploy" / "live-canary-on-instance.sh").read_text(
        encoding="utf-8"
    )
    assert "--mode live" in helper
    assert "--confirm-live" in helper
    assert "--account-wide" in helper


def test_live_canary_real_order_failures_reach_job_and_sidecar() -> None:
    text = _workflow_text()
    real_order = _real_order_job(text)

    live_section = real_order.split(
        "Authorize request — scheduled runs place real orders", 1
    )[1]
    live_step = live_section.split("\n\n      - name:", 1)[0]
    assert "ssh_exit=$?" in live_step
    assert 'exit "${ssh_exit}"' in live_step

    fill_step = real_order.split("Sync broker fills and read audit ledger", 1)[1].split(
        "\n\n      - name:", 1
    )[0]
    assert "if: always()" in fill_step
    assert '"live-canary-fills"' in fill_step
    assert 'exit "${sync_exit}"' in fill_step

    measure_step = real_order.split("Measure live track after real orders", 1)[1].split(
        "\n\n      - name:", 1
    )[0]
    assert "if: always()" in measure_step
    assert '"observe live-canary-measure ${CAP}"' in measure_step
    assert '"live-canary-profit ${CAP}"' in measure_step
    assert 'exit "${ssh_exit}"' in measure_step

    publish_step = real_order.split("Publish production live canary result", 1)[1]
    assert "FILLS_OUTCOME: ${{ steps.fills.outcome }}" in publish_step
    assert "MEASURE_OUTCOME: ${{ steps.measure.outcome }}" in publish_step
    assert "cat /tmp/live_rebal.err" in publish_step
    assert "KIS 체결 동기화·감사 장부 요약" in publish_step


def test_live_canary_preview_and_real_orders_use_broker_snapshot() -> None:
    text = _workflow_text()
    real_order = _real_order_job(text)
    observe_helper = (ROOT / "deploy" / "observe-on-instance.sh").read_text(encoding="utf-8")
    live_helper = (ROOT / "deploy" / "live-canary-on-instance.sh").read_text(
        encoding="utf-8"
    )

    preview_fn = observe_helper.split("live_canary_preview()", 1)[1].split(
        "live_canary_measure()", 1
    )[0]
    assert "--account-wide" in preview_fn
    assert "--account-wide" in live_helper
    assert "live-canary-order" in real_order


def test_live_canary_runs_do_not_overlap() -> None:
    text = _workflow_text()

    assert "concurrency:\n  group: rebalance-live-canary" in text
    assert "cancel-in-progress: false" in text
