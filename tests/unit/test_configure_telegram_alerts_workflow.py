from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "configure-telegram-alerts.yml"


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_configure_telegram_alerts_workflow_is_manual_and_parseable() -> None:
    text = _workflow_text()

    assert "name: Configure Telegram alerts on server" in text
    assert "workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text


def test_configure_telegram_alerts_workflow_uses_required_secrets_without_values() -> None:
    text = _workflow_text()

    for name in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "VULTR_SSH_HOST",
        "VULTR_SSH_USER",
        "VULTR_SSH_PRIVATE_KEY",
        "VULTR_SSH_PORT",
    ):
        assert f"secrets.{name}" in text
    assert "::add-mask::${TELEGRAM_BOT_TOKEN" in text
    assert "::add-mask::${TELEGRAM_CHAT_ID" in text
    assert "bot860" not in text
    assert "8783665778" not in text


def test_configure_telegram_alerts_workflow_updates_env_and_enables_observer_only() -> None:
    text = _workflow_text()

    assert "TELEGRAM_ENABLED" in text
    assert "TELEGRAM_SOURCE_LABEL" in text
    assert "auto-invest telegram-alerts" in text
    assert "--test-message" in text
    assert "systemctl enable --now \"${SERVICE}\"" in text
    assert "auto-invest-telegram-alerts.service" in text
    assert "auto-invest-deploy.service" not in text
    assert "auto-invest.service\" " not in text
    assert "go-live" not in text
