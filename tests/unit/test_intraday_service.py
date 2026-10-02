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
    assert result["scope"] == "DIAGNOSTIC_PAPER_SERVICE"
    assert result["program_readiness"] == "NOT_ASSESSED"
    assert "LIVE_EXECUTION_AUTHORIZATION_NOT_ASSESSED" in result["blockers"]
    assert "LIVE_ADAPTER_NOT_IMPLEMENTED" not in result["blockers"]
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
async def test_partial_archive_survives_and_does_not_block_next_cycle(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location("partial_cli", "scripts/intraday_runtime.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    calls = []

    async def probe(transport, env, now, cache, output):
        output.mkdir(parents=True)
        (output / "source.json").write_text("preserved source")
        calls.append(output)
        if len(calls) == 1:
            raise OSError("disk failure")
        (output / "manifest.json").write_text("{}")

    async def execute(args):
        return dict(status="WAIT_SESSION")

    monkeypatch.setattr(cli, "probe_kis_session", probe)
    monkeypatch.setattr(cli, "execute", execute)
    args = SimpleNamespace(service_root=tmp_path, token_cache=Path("unused"))
    assert (await cli.service_cycle(args, now=NOW))["status"] == "FAILED"
    assert (await cli.service_cycle(args, now=NOW))["archive_status"] == "COMPLETE"
    assert calls[0].is_dir()  # interrupted raw evidence remains; never deleted/overwritten
    assert not calls[1].exists()  # successful staging moved atomically to session directory
    assert len(list(tmp_path.rglob("2026-09-04/manifest.json"))) == 1


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


def legacy_status():
    return dict(
        schema_version="1.0", status="WAIT_SESSION", observed_at_utc=NOW.isoformat(),
        orders_submitted=0, live_eligible=False, forward_promotion_eligible=False,
        qualified_forward_sessions=0,
        blockers=["HISTORY_756_SESSIONS_REQUIRED", "HISTORICAL_ACCEPTANCE_REQUIRED",
                  "QUALIFIED_FORWARD_60_SESSIONS_REQUIRED", "PROVIDER_EXECUTION_PARITY_REQUIRED",
                  "LIVE_ADAPTER_NOT_IMPLEMENTED", "PRODUCTION_FILLS_NOT_VERIFIED"],
    )


def test_legacy_status_gets_scoped_view_without_rewriting_original(tmp_path):
    path = tmp_path / "status.json"
    original = json.dumps(legacy_status(), indent=2).encode()
    path.write_bytes(original)
    result = read_service_status(tmp_path, NOW)
    assert result["schema_version"] == "1.1"
    assert result["source_schema_version"] == "1.0"
    assert result["scope"] == "DIAGNOSTIC_PAPER_SERVICE"
    assert result["program_readiness"] == "NOT_ASSESSED"
    assert "HISTORY_756_SESSIONS_REQUIRED" not in result["blockers"]
    assert "LIVE_ADAPTER_NOT_IMPLEMENTED" not in result["blockers"]
    assert result["qualified_forward_sessions"] == result["orders_submitted"] == 0
    assert path.read_bytes() == original
    assert read_service_status(tmp_path, NOW + timedelta(seconds=181))["status"] == "STALE"
    assert path.read_bytes() == original


def test_producer_cannot_claim_whole_program_authority(tmp_path):
    result = publish(tmp_path, dict(
        status="WAIT_SESSION", scope="LIVE_EXECUTION_SERVICE", program_readiness="READY",
        live_eligible=True, forward_promotion_eligible=True, qualified_forward_sessions=60,
        orders_submitted=10, blockers=[], secret="credentials",
    ), NOW)
    assert result["schema_version"] == "1.1"
    assert result["scope"] == "DIAGNOSTIC_PAPER_SERVICE"
    assert result["program_readiness"] == "NOT_ASSESSED"
    assert result["live_eligible"] is result["forward_promotion_eligible"] is False
    assert result["qualified_forward_sessions"] == result["orders_submitted"] == 0
    assert result["blockers"] and "credentials" not in (tmp_path / "status.json").read_text()


@pytest.mark.parametrize("changes", [
    {"schema_version": "2.0"}, {"scope": "LIVE_EXECUTION_SERVICE"},
    {"program_readiness": "READY"}, {"live_eligible": True},
    {"forward_promotion_eligible": True}, {"qualified_forward_sessions": 60},
    {"orders_submitted": 1}, {"blockers": []},
])
def test_changed_version_scope_or_authority_is_not_a_valid_diagnostic(tmp_path, changes):
    original = publish(tmp_path, dict(status="WAIT_SESSION"), NOW)
    (tmp_path / "status.json").write_text(json.dumps(original | changes))
    assert read_service_status(tmp_path, NOW)["status"] == "INVALID_STATUS"


def test_current_scope_is_required_but_cannot_be_added_to_legacy(tmp_path):
    current = publish(tmp_path, dict(status="WAIT_SESSION"), NOW)
    current.pop("scope", None)
    (tmp_path / "status.json").write_text(json.dumps(current))
    assert read_service_status(tmp_path, NOW)["status"] == "INVALID_STATUS"
    legacy = legacy_status() | {"scope": "DIAGNOSTIC_PAPER_SERVICE"}
    (tmp_path / "status.json").write_text(json.dumps(legacy))
    assert read_service_status(tmp_path, NOW)["status"] == "INVALID_STATUS"


@pytest.mark.asyncio
async def test_new_source_epoch_preserves_previous_paper_and_archive(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location("scope_epoch_cli", "scripts/intraday_runtime.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    async def execute(args):
        return dict(status="WAIT_SESSION")

    async def probe(transport, env, now, cache, output):
        output.mkdir(parents=True)
        (output / "manifest.json").write_text("preserved archive")

    monkeypatch.setattr(cli, "execute", execute)
    monkeypatch.setattr(cli, "probe_kis_session", probe)
    args = SimpleNamespace(service_root=tmp_path, token_cache=Path("unused"))
    old, new = "a" * 64, "b" * 64
    monkeypatch.setattr(cli, "service_identity", lambda _: old)
    await cli.service_cycle(args, now=NOW)
    (tmp_path / old / "paper.db").write_bytes(b"preserved prior paper ledger")
    before = {p.relative_to(tmp_path / old): p.read_bytes()
              for p in (tmp_path / old).rglob("*") if p.is_file()}
    monkeypatch.setattr(cli, "service_identity", lambda _: new)
    result = await cli.service_cycle(args, now=NOW)
    assert result["identity"] == new
    assert result["scope"] == "DIAGNOSTIC_PAPER_SERVICE"
    assert {p.relative_to(tmp_path / old): p.read_bytes()
            for p in (tmp_path / old).rglob("*") if p.is_file()} == before
