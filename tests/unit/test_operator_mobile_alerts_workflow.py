from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "operator-mobile-alerts.yml"


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_operator_mobile_alerts_workflow_schedule_and_sidecar() -> None:
    text = _workflow_text()

    assert "name: Operator mobile alerts" in text
    assert 'cron: "25 9 * * *"' in text
    assert "workflow_dispatch:" in text
    assert "automation/operator-status-last-run" in text
    assert "operator_status.json" in text
    assert "scripts/operator_status_probe.py --manifest" in text


def test_operator_mobile_alerts_workflow_skips_missing_telegram_secrets() -> None:
    text = _workflow_text()

    assert "TELEGRAM_BOT_TOKEN" in text
    assert "TELEGRAM_CHAT_ID" in text
    assert "SKIPPED_MISSING_SECRETS" in text
    assert "Telegram secrets absent" in text
    assert "continue-on-error: true" in text
    assert "::add-mask::${TELEGRAM_BOT_TOKEN" in text
    assert "::add-mask::${TELEGRAM_CHAT_ID" in text


def test_operator_mobile_alerts_workflow_stays_read_only() -> None:
    text = _workflow_text()

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
        "auto-invest deploy",
    ]
    for token in forbidden:
        assert token not in text
    assert "auto-invest-telegram-alerts.service" not in text
    assert "auto-invest.service" not in text
