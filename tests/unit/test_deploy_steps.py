"""Focused regression tests for deploy step configuration loading."""

from __future__ import annotations

from pathlib import Path

from auto_invest.deploy.steps import dry_run_config

ROOT = Path(__file__).resolve().parents[2]


def test_dry_run_config_loads_fixed_env_file(tmp_path: Path, monkeypatch) -> None:
    for name in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO"):
        monkeypatch.delenv(name, raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "KIS_APP_KEY=test-key\n"
        "KIS_APP_SECRET=test-secret\n"
        "KIS_ACCOUNT_NO=00000000-00\n",
        encoding="utf-8",
    )

    result = dry_run_config(ROOT / "deploy" / "canary-live-rules.toml", env_path=env_path)

    assert result.ok is True


def test_dry_run_config_fails_closed_without_process_or_file_secrets(
    tmp_path: Path, monkeypatch
) -> None:
    for name in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO"):
        monkeypatch.delenv(name, raising=False)

    result = dry_run_config(
        ROOT / "deploy" / "canary-live-rules.toml",
        env_path=tmp_path / "missing.env",
    )

    assert result.ok is False
    assert "required secret(s) missing" in result.detail
