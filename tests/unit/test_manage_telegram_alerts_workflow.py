from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "manage-telegram-alerts.yml"


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_manage_telegram_alerts_workflow_is_manual_and_scoped() -> None:
    text = _workflow_text()

    assert "name: Manage Telegram alerts on server" in text
    assert "workflow_dispatch:" in text
    assert "permissions:\n  contents: read" in text
    assert "auto-invest-telegram-alerts.service" in text
    assert "systemctl disable --now \"${SERVICE}\"" in text
    assert "systemctl restart \"${SERVICE}\"" in text
    assert "systemctl enable --now \"${SERVICE}\"" in text
    assert "auto-invest.service" not in text.replace("auto-invest-telegram-alerts.service", "")


def test_manage_telegram_alerts_workflow_uses_only_ssh_secrets() -> None:
    text = _workflow_text()

    for name in (
        "VULTR_SSH_HOST",
        "VULTR_SSH_USER",
        "VULTR_SSH_PRIVATE_KEY",
        "VULTR_SSH_PORT",
    ):
        assert f"secrets.{name}" in text
    assert "secrets.TELEGRAM_BOT_TOKEN" not in text
    assert "secrets.KIS_APP_KEY" not in text
    assert "secrets.KIS_APP_SECRET" not in text
