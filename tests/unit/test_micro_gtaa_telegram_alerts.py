from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "rebalance-micro-gtaa-canary.yml"


def test_micro_gtaa_workflow_has_best_effort_telegram_notification() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "Notify Telegram — micro GTAA result" in text
    block = text[text.index("Notify Telegram — micro GTAA result") :]
    assert "if: always()" in block
    assert "continue-on-error: true" in block
    assert "TELEGRAM_BOT_TOKEN" in block
    assert "TELEGRAM_CHAT_ID" in block
    assert "Telegram secrets absent; skipping notification." in block
    assert "raise SystemExit(0)" in block
    assert "4. 거부 주문 기회손익" in block
    assert "브로커 거부(접수/체결 안 됨)" in block
    assert "양수=체결됐으면 현재 더 유리" in block


def test_micro_gtaa_telegram_notification_runs_after_sidecar_publish() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    publish_idx = text.index("Publish micro GTAA result to sidecar branch")
    notify_idx = text.index("Notify Telegram — micro GTAA result")
    assert publish_idx < notify_idx
    assert "/tmp/micro_preflight.json" in text[notify_idx:]
    assert "/tmp/micro_live.json" in text[notify_idx:]
    assert "/tmp/micro_opportunity.json" in text[notify_idx:]
    assert "/tmp/micro_opportunity_monitor.json" in text[notify_idx:]


def test_micro_gtaa_workflow_evaluates_rejected_order_opportunity() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "Evaluate rejected order opportunity" in text
    block = text[text.index("Evaluate rejected order opportunity") :]
    assert "continue-on-error: true" in block
    assert "rejected-order-opportunity" in block
    assert "--format json" in block
    assert "/tmp/micro_opportunity.json" in block
    assert "mark_fetch_error" in block
    assert "## 거부 주문 기회손익" in text


def test_micro_gtaa_workflow_publishes_rejected_order_opportunity_monitor() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "Update rejected order opportunity monitor" in text
    assert "scripts/opportunity_monitor_sidecar.py" in text
    assert "opportunity_history.json" in text
    assert "opportunity_monitor.json" in text
    assert "## 거부 주문 누적 평가" in text
    assert "5. 누적 전략/실행 평가" in text
    assert "음수=전략 의도 손실 검토" in text
