import json
from datetime import UTC, datetime, timedelta

import pytest

from auto_invest.analytics.intraday_service import (
    busy_lock,
    publish,
    read_service_status,
    service_identity,
)

NOW = datetime(2026, 9, 7, 1, tzinfo=UTC)


def test_service_lock_is_exclusive_and_released_after_failure(tmp_path):
    with busy_lock(tmp_path) as acquired:
        assert acquired
        with busy_lock(tmp_path) as other:
            assert not other
    with busy_lock(tmp_path) as acquired:
        assert acquired


def test_identity_changes_with_execution_source_not_documentation(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("original")
    old = service_identity([source])
    (tmp_path / "README.md").write_text("docs")
    assert service_identity([source]) == old
    source.write_text("changed")
    assert service_identity([source]) != old


def test_status_fresh_stale_missing_and_fail_closed(tmp_path):
    assert read_service_status(tmp_path, NOW)["status"] == "NOT_STARTED"
    publish(tmp_path, dict(status="WAIT_SESSION", orders_submitted=0), NOW)
    result = read_service_status(tmp_path, NOW)
    assert result["status"] == "WAIT_SESSION"
    assert result["live_eligible"] is False
    assert result["qualified_forward_sessions"] == 0
    assert "LIVE_ADAPTER_NOT_IMPLEMENTED" in result["blockers"]
    assert read_service_status(tmp_path, NOW + timedelta(seconds=181))["status"] == "STALE"
    assert read_service_status(tmp_path, NOW - timedelta(seconds=1))["status"] == "INVALID_STATUS"
    (tmp_path / "status.json").write_text('{"status":"fake","orders_submitted":1}')
    assert read_service_status(tmp_path, NOW)["status"] == "INVALID_STATUS"


def test_published_status_never_forwards_credentials_or_account_details(tmp_path):
    publish(tmp_path, dict(status="WAIT_SESSION", secret="never", accounts={"key": "secret"}), NOW)
    text = (tmp_path / "status.json").read_text()
    assert "never" not in text and "accounts" not in text
    assert json.loads(text)["orders_submitted"] == 0
    (tmp_path / "status.json").unlink()
    (tmp_path / "status.json").symlink_to(tmp_path / "missing")
    assert read_service_status(tmp_path, NOW)["status"] == "INVALID_STATUS"


@pytest.mark.asyncio
async def test_service_holiday_archives_once_never_replays_or_orders(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location("service_cli", "scripts/intraday_runtime.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    calls = []

    async def probe(transport, env, now, cache, output):
        calls.append(output)
        output.mkdir(parents=True)
        (output / "manifest.json").write_text("{}")
        return {"status": "INTRADAY_DATA_CONTRACT_OK", "session": "2026-09-04"}

    async def execute(args):
        assert args.command == "run" and args.cycles == 1
        return dict(status="WAIT_SESSION", orders_submitted=0, live_eligible=False)

    monkeypatch.setattr(cli, "probe_kis_session", probe)
    monkeypatch.setattr(cli, "execute", execute)
    args = SimpleNamespace(service_root=tmp_path, token_cache=Path("unused"))
    for _ in range(2):
        result = await cli.service_cycle(args, now=NOW)
        assert result["orders_submitted"] == 0
        assert result["status"] == "WAIT_SESSION"
    assert len(calls) == 1
    assert not list(tmp_path.rglob("paper.db"))


@pytest.mark.asyncio
async def test_service_failure_is_sanitized_and_next_cycle_recovers(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location("failure_cli", "scripts/intraday_runtime.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    async def execute(args):
        raise RuntimeError("secret should never appear")

    monkeypatch.setattr(cli, "execute", execute)
    args = SimpleNamespace(service_root=tmp_path, token_cache=Path("unused"))
    during = datetime(2026, 9, 8, 14, tzinfo=UTC)
    result = await cli.service_cycle(args, now=during)
    assert result["status"] == "FAILED"
    assert result["reason"] == "RuntimeError"
    assert "secret should never" not in (tmp_path / "status.json").read_text()
    assert len(list(tmp_path.glob("failure-*.json"))) == 1

    async def success(args):
        return dict(status="DIAGNOSTIC_PAPER", processed_bars=5)

    monkeypatch.setattr(cli, "execute", success)
    assert (await cli.service_cycle(args, now=during))["status"] == "DIAGNOSTIC_PAPER"
