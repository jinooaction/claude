import asyncio
import importlib.util
import json
import sqlite3
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from auto_invest.execution import intraday_launch as launch
from auto_invest.market_data.intraday import DataError
from auto_invest.persistence import db


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupted", [False, True])
async def test_real_launcher_reaches_execution_reader_and_closes_on_missing_evidence(
    inputs, monkeypatch, interrupted,
):
    from auto_invest.analytics.intraday_paper_challenger import (
        build_candidate_registry,
        load_preregistration,
    )
    from auto_invest.execution import intraday_qualification as qualification
    from auto_invest.execution.intraday_selection import ResearchSelection
    from auto_invest.execution.intraday_signals import execution_fingerprint

    # Isolate historical research only. Launcher, assembler, authority, token
    # refresh, GET parsers, cost source and SQLite closure are production code.
    candidate = build_candidate_registry(load_preregistration(qualification.PREREGISTRATION))[0]
    provider = "kis-nasdaq-partial-unadjusted"
    selected = ResearchSelection(candidate, provider, "a" * 40, "dataset", "research",
                                 execution_fingerprint(candidate, provider),
                                 "PAPER_CHALLENGER", 756, 0)
    monkeypatch.setattr(qualification, "select_research", lambda *a: selected)
    monkeypatch.setattr(qualification, "assess_registered_forward", lambda *a: dict(
        freeze_authentication_verified=True, minimum_observation_count_met=True,
        complete_sessions=60, required_sessions=60, invalid_sessions=0,
        session_dates=["2026-09-10", "2026-09-11"],
    ))
    inputs["registration"].write_bytes(b"isolated-research-fixture")
    calls, connections = [], []
    original_open = launch._open_existing

    def track_open(path):
        connection = original_open(path)
        connections.append(connection)
        return connection

    monkeypatch.setattr(launch, "_open_existing", track_open)

    async def respond(self, method, url, **kwargs):
        calls.append((method, url))
        request = httpx.Request(method, str(self.base_url.join(url)))
        if url.endswith("/oauth2/tokenP"):
            return httpx.Response(200, request=request,
                                  json=dict(access_token="fixture-fresh", expires_in=86400))
        assert method == "GET", "No order, cancel, or capital write is allowed"
        assert kwargs["headers"]["authorization"] == "Bearer fixture-fresh"
        if interrupted:
            raise asyncio.CancelledError
        if url.endswith("inquire-ccnl"):
            body = dict(rt_cd="0", output=[])
        else:
            assert url.endswith("inquire-period-trans")
            body = dict(rt_cd="0", output1=[], output2=[])
        return httpx.Response(200, request=request, headers={"tr_cont": "D"}, json=body)

    monkeypatch.setattr(httpx.AsyncClient, "request", respond)
    for _ in range(2):
        if interrupted:
            with pytest.raises(asyncio.CancelledError):
                await launch.launch(**inputs)
        else:
            with pytest.raises(DataError, match="QUALIFICATION_EXECUTION_COSTS_NOT_ACCEPTED"):
                await launch.launch(**inputs)
        with pytest.raises(sqlite3.ProgrammingError):
            connections[-1].execute("SELECT 1")
    assert len([call for call in calls if call[0] == "GET"]) == (2 if interrupted else 14)
    assert all(method == "GET" or url.endswith("/oauth2/tokenP") for method, url in calls)
    with sqlite3.connect(inputs["database"]) as check:
        assert check.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
        assert check.execute("SELECT COUNT(*) FROM fills").fetchone()[0] == 0


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    for name, value in {"KIS_APP_KEY": "offline", "KIS_APP_SECRET": "offline",
                        "KIS_ACCOUNT_NO": "1234567801"}.items():
        monkeypatch.setenv(name, value)
    rules = tmp_path / "rules.toml"
    rules.write_text('''[caps]
per_trade_pct=20
per_symbol_pct=20
global_exposure_pct=80
canary_capital_pct=10
canary_min_duration_days=60
canary_acceptance_drawdown_pct=2
[whitelist]
symbols=["SPY","QQQ","IWM","TLT","GLD"]
accounts=["1234567801"]
''')
    baseline = tmp_path / "holdings.toml"
    baseline.write_text("holdings=[]\n")
    database = tmp_path / "execution.db"
    conn = db.get_connection(database)
    db.migrate(conn)
    conn.close()
    return dict(database=database, rules=rules, external_holdings=baseline,
                archives=tmp_path / "archives", forward_database=tmp_path / "forward.db",
                registration=tmp_path / "freeze.json", halt_path=tmp_path / "halt",
                token_cache=tmp_path / "token.json", stop_event=asyncio.Event())


@pytest.mark.asyncio
async def test_failed_qualification_closes_ledger_without_network_or_token_cache(
    inputs, monkeypatch,
):
    seen = []

    async def assemble(**kwargs):
        router = kwargs["router"]
        seen.append(router.conn)
        assert router.account_no == "1234567801"
        assert router.execution_authority.conn is router.conn
        assert router.execution_authority.broker_write_lock_path == launch.DEFAULT_BROKER_WRITE_LOCK
        assert kwargs["external_holdings"] == {}
        assert kwargs["capital_limit"] == 600
        raise DataError("QUALIFICATION_FORWARD_NOT_ACCEPTED")

    async def forbidden(*a, **k):
        pytest.fail("Qualification failure must precede network access")

    monkeypatch.setattr(launch, "build_kis_program", assemble)
    monkeypatch.setattr(launch.httpx.AsyncClient, "request", forbidden)
    with pytest.raises(DataError, match="QUALIFICATION_FORWARD_NOT_ACCEPTED"):
        await launch.launch(**inputs)
    assert not inputs["token_cache"].exists()
    with pytest.raises(sqlite3.ProgrammingError):
        seen[0].execute("SELECT 1")


@pytest.mark.asyncio
async def test_launcher_preserves_stop_event_and_closes_resources_on_runtime_error(
    inputs, monkeypatch,
):
    handles = []

    async def assemble(**kwargs):
        handles.append(kwargs["router"].conn)

        async def run(**options):
            assert options["stop_event"] is inputs["stop_event"]
            raise ValueError("private runtime details")

        return SimpleNamespace(run=run)

    monkeypatch.setattr(launch, "build_kis_program", assemble)
    with pytest.raises(DataError, match="^LAUNCH_CONFIGURATION_INVALID$"):
        await launch.launch(**inputs)
    with pytest.raises(sqlite3.ProgrammingError):
        handles[0].execute("SELECT 1")


@pytest.mark.asyncio
async def test_missing_ledger_is_never_created(inputs):
    missing = inputs["database"].with_name("missing.db")
    inputs["database"] = missing
    with pytest.raises(DataError, match="LAUNCH_LOCAL_INPUT_UNAVAILABLE"):
        await launch.launch(**inputs)
    assert not missing.exists()


@pytest.mark.asyncio
async def test_missing_baseline_does_not_silently_become_an_empty_account(inputs):
    inputs["external_holdings"] = inputs["external_holdings"].with_name("missing.toml")
    with pytest.raises(DataError, match="LAUNCH_HOLDINGS_BASELINE_REQUIRED"):
        await launch.launch(**inputs)


def operator():
    spec = importlib.util.spec_from_file_location("launch_operator", "scripts/intraday_operator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def argv(inputs):
    values = ["execution-start"]
    for argument, key in (("db", "database"), ("rules", "rules"), ("archives", "archives"),
                          ("forward-db", "forward_database"), ("registration", "registration"),
                          ("external-holdings", "external_holdings"), ("halt-path", "halt_path"),
                          ("token-cache", "token_cache")):
        values.extend(["--" + argument, str(inputs[key])])
    return values


@pytest.mark.asyncio
async def test_user_command_routes_exact_paths_and_installs_graceful_stop(inputs, monkeypatch):
    module = operator()
    captured = {}

    async def start(**kwargs):
        captured.update(kwargs)
        return dict(phase="STOPPED", pending_orders=0, owned_symbols=0)

    monkeypatch.setattr(launch, "launch", start)
    result = await module.execute(module.parser().parse_args(argv(inputs)))
    assert result["phase"] == "STOPPED"
    for key, value in inputs.items():
        if key != "stop_event":
            assert captured[key] == value
    assert isinstance(captured["stop_event"], asyncio.Event)


def test_start_error_never_claims_zero_orders_after_unknown_runtime_failure(
    inputs, monkeypatch, capsys,
):
    module = operator()

    async def fail(args):
        raise RuntimeError("private broker response")

    monkeypatch.setattr(module, "execute", fail)
    monkeypatch.setattr("sys.argv", ["operator"] + argv(inputs))
    assert module.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result == dict(status="FAILED", reason="OPERATOR_FAILED", order_outcome_verified=False)


def test_execution_command_has_no_authority_or_transport_override(inputs):
    module = operator()
    for flag in ("--qualify", "--live", "--base-url", "--approval", "--capital-limit"):
        with pytest.raises(SystemExit):
            module.parser().parse_args(argv(inputs) + [flag, "value"])


@pytest.mark.asyncio
async def test_launcher_runs_actual_engine_stops_and_reopens_same_ledger(inputs, monkeypatch):
    from auto_invest.analytics.intraday_paper_challenger import (
        build_candidate_registry,
        load_preregistration,
    )
    from auto_invest.execution.intraday_program import build_program
    from auto_invest.execution.intraday_qualification import PREREGISTRATION
    from auto_invest.execution.intraday_rehearsal import rehearsal_session
    from auto_invest.execution.intraday_selection import ResearchSelection
    from auto_invest.execution.intraday_signals import execution_fingerprint

    candidate = build_candidate_registry(load_preregistration(PREREGISTRATION))[0]
    provider = "kis-nasdaq-partial-unadjusted"
    # Qualified research/account fixture; no production evidence is asserted.
    selected = ResearchSelection(candidate, provider, "a" * 40, "dataset", "research",
                                 execution_fingerprint(candidate, provider),
                                 "PAPER_CHALLENGER", 756, 0)
    async with rehearsal_session(inputs["database"], capital_limit=Decimal("600")) as book:
        book.conn.execute("CREATE TABLE preservation_marker (value TEXT)")
        book.conn.execute("INSERT INTO preservation_marker VALUES ('keep')")

        async def assemble(**kwargs):
            return build_program(
                selection=selected, router=kwargs["router"], observe=book.observe,
                qualify=lambda: None, collect_bars=kwargs["collect_bars"],
                capital_limit=kwargs["capital_limit"],
                external_holdings=kwargs["external_holdings"],
                now=lambda: book.now,
            )

        async def forbidden(*a, **k):
            pytest.fail("Stopped empty-account fixture must not request external data")

        monkeypatch.setattr(launch, "build_kis_program", assemble)
        monkeypatch.setattr(launch.httpx.AsyncClient, "request", forbidden)
        inputs["stop_event"].set()
        first = await launch.launch(**inputs)
        second = await launch.launch(**inputs)
        assert first["phase"] == second["phase"] == "STOPPED"
        assert first["run_id"] != second["run_id"]
        assert second["owned_symbols"] == second["pending_orders"] == 0
        assert book.conn.execute("SELECT value FROM preservation_marker").fetchone()[0] == "keep"
        assert book.conn.execute(
            "SELECT COUNT(*) FROM intraday_execution_events WHERE kind='STOP_COMPLETED'"
        ).fetchone()[0] == 2
