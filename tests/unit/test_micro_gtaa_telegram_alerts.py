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


def test_micro_gtaa_telegram_notification_runs_after_sidecar_publish() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    publish_idx = text.index("Publish micro GTAA result to sidecar branch")
    notify_idx = text.index("Notify Telegram — micro GTAA result")
    assert publish_idx < notify_idx
    assert "/tmp/micro_preflight.json" in text[notify_idx:]
    assert "/tmp/micro_live.json" in text[notify_idx:]
