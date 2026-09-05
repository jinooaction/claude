"""Backfill token-cache liveness contracts."""

from pathlib import Path

import pytest
from click import unstyle
from typer import rich_utils
from typer.testing import CliRunner

from auto_invest import cli


def test_explicit_token_cache_is_independent_of_ephemeral_database(tmp_path: Path) -> None:
    database = tmp_path / "ephemeral" / "parity.db"
    shared = Path("data/kis_token.json")

    assert cli._resolve_backfill_token_cache(database, shared) == shared


def test_legacy_backfill_cache_default_stays_database_adjacent(tmp_path: Path) -> None:
    database = tmp_path / "paper" / "bars.db"

    assert cli._resolve_backfill_token_cache(database, None) == database.parent / "kis_token.json"


@pytest.mark.parametrize("colored", [False, True])
def test_backfill_help_exposes_explicit_token_cache_option(
    monkeypatch: pytest.MonkeyPatch, colored: bool,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setattr(rich_utils, "FORCE_TERMINAL", colored)
    monkeypatch.setattr(rich_utils, "COLOR_SYSTEM", "standard" if colored else None)
    result = CliRunner().invoke(cli.app, ["backfill-bars", "--help"], color=colored)

    assert result.exit_code == 0, result.output
    if colored:
        assert "\x1b[" in result.output
    assert "--token-cache" in unstyle(result.output)
