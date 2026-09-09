import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import httpx
import pytest

from auto_invest.broker.intraday_account import observe_account
from auto_invest.broker.intraday_inputs import EXCHANGES, PREFIXES, SourceQuote
from auto_invest.execution.intraday_observation import (
    ExecutionObserver,
    ObservationError,
    build_observation,
)
from auto_invest.execution.intraday_rehearsal import rehearsal_session

NOW = datetime(2026, 9, 8, 15, tzinfo=UTC)


def account(*, positions=None):
    return dict(
        currency="USD", pagination_complete=True, full_account_scope_verified=True,
        cash_aggregation_verified=True, nav_verified=True, unverified_assets={},
        observation_started_at=NOW.isoformat(), observation_completed_at=NOW.isoformat(),
        execution_cash="600", nav="600", positions=positions or {}, open_orders=[],
    )


def quotes(now=NOW):
    return {symbol: SourceQuote(
        symbol, exchange, PREFIXES[exchange] + symbol, Decimal("20"), None, None,
        now, now, "20260909", "000000", "20260908", "110000", "1",
    ) for symbol, exchange in EXCHANGES.items()}


@pytest.mark.parametrize("field", [
    "pagination_complete", "full_account_scope_verified",
    "cash_aggregation_verified", "nav_verified",
])
@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_reader_verification_is_exact_and_never_coerced(field, value):
    raw = account()
    raw[field] = value
    with pytest.raises(ObservationError, match="UNVERIFIED"):
        build_observation(raw, quotes(), now=NOW)


def test_buying_power_cannot_replace_execution_cash():
    raw = account()
    del raw["execution_cash"]
    raw["usd_orderable_amount"] = "999999"
    with pytest.raises(ObservationError, match="AMOUNT_INVALID"):
        build_observation(raw, quotes(), now=NOW)


def calculated_account():
    raw = account(positions={"SPY": dict(quantity=2, sellable_quantity=2)})
    raw.update(valuation_basis="net_cash_and_listed_equities", net_cash="600",
               nav="99999999", nav_verified=False)
    return raw


def test_nav_is_calculated_from_net_cash_and_all_equities_not_reported_nav():
    raw = calculated_account()
    raw["positions"]["AAPL"] = dict(quantity=3, sellable_quantity=2)
    market = quotes()
    market["AAPL"] = replace(market["SPY"], symbol="AAPL", exchange="NASD",
                             rsym=PREFIXES["NASD"] + "AAPL", last=Decimal("30.123456789012"))
    # An unrelated ambient Decimal context must not round the account NAV.
    with localcontext() as context:
        context.prec = 2
        view = build_observation(raw, market, now=NOW)
    assert view.nav == Decimal("730.370370367036")
    assert view.cash == Decimal("600")
    assert view.sellable_positions["AAPL"] == 2
    assert raw["nav"] == "99999999" and raw["nav_verified"] is False


@pytest.mark.parametrize("field", [
    "pagination_complete", "full_account_scope_verified", "cash_aggregation_verified",
])
def test_calculated_nav_still_requires_verified_inputs(field):
    raw = calculated_account()
    raw[field] = False
    with pytest.raises(ObservationError, match="UNVERIFIED"):
        build_observation(raw, quotes(), now=NOW)


@pytest.mark.parametrize("change", ["cash_missing", "mark_missing", "liability",
                                   "unknown_basis", "asset", "price_nan", "price_huge"])
def test_calculation_cannot_fill_missing_or_invalid_evidence(change):
    raw, market = calculated_account(), quotes()
    if change == "cash_missing":
        del raw["net_cash"]
    elif change == "mark_missing":
        del market["SPY"]
    elif change == "liability":
        raw.update(execution_cash="0", net_cash="-41")
    elif change == "unknown_basis":
        raw["valuation_basis"] = "available_cash_is_net_cash"
    elif change == "asset":
        raw["unverified_assets"] = {"OTHER": {"reported_quantity": "1"}}
    else:
        market["SPY"] = replace(market["SPY"], last=Decimal(
            "NaN" if change == "price_nan" else "1e99"))
    with pytest.raises(ObservationError):
        build_observation(raw, market, now=NOW)


def test_net_liability_reduces_nav_without_becoming_orderable_cash():
    raw = calculated_account()
    raw.update(execution_cash="0", net_cash="-10")
    view = build_observation(raw, quotes(), now=NOW)
    assert view.nav == Decimal("30") and view.cash == 0


@pytest.mark.parametrize("change", ["old", "future", "unverified_asset", "fraction", "duplicate"])
def test_bad_account_batch_never_reaches_engine(change):
    raw = account()
    if change == "old":
        raw["observation_started_at"] = (NOW - timedelta(seconds=31)).isoformat()
    elif change == "future":
        raw["observation_completed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif change == "unverified_asset":
        raw["unverified_assets"] = {"ASSET": {"reported_quantity": "0.2"}}
    elif change == "fraction":
        raw["positions"] = {"SPY": {"quantity": Decimal("0.5"), "sellable_quantity": 0}}
    else:
        raw["open_orders"] = [{"order_id": "1"}, {"order_id": "1"}]
    with pytest.raises(ObservationError):
        build_observation(raw, quotes(), now=NOW)


def test_old_source_timestamps_survive_for_the_engine_to_check_before_pricing():
    stamp = NOW - timedelta(seconds=31)
    view = build_observation(account(), quotes(stamp), now=NOW)
    assert view.observed_at == NOW
    assert set(view.mark_times.values()) == {stamp}


@pytest.mark.asyncio
async def test_private_upstream_error_is_not_republished():
    async def read():
        raise RuntimeError("private account secret")

    observer = ExecutionObserver(read, quotes, now=lambda: NOW)
    with pytest.raises(ObservationError, match="^ACCOUNT_INPUT_UNAVAILABLE$"):
        await observer()


@pytest.mark.asyncio
async def test_collection_delay_cannot_be_hidden_by_new_source_timestamps():
    clock = [NOW]

    async def read():
        clock[0] += timedelta(seconds=31)
        raw = account()
        raw.update(observation_started_at=clock[0], observation_completed_at=clock[0])
        return raw

    with pytest.raises(ObservationError, match="COLLECTION_STALE"):
        await ExecutionObserver(read, quotes, now=lambda: clock[0])()


@pytest.mark.asyncio
async def test_normalized_account_drives_real_engine_using_only_simulated_broker(tmp_path):
    async with rehearsal_session(
        tmp_path / "simulation.db", capital_limit=Decimal("600"), mark=Decimal("20"),
    ) as book:
        async def read():
            observed = await book.observe()
            raw = account()
            raw.update(
                execution_cash=str(observed.cash), net_cash=str(observed.cash),
                valuation_basis="net_cash_and_listed_equities", nav_verified=False, nav=None,
                positions={s: dict(quantity=q, sellable_quantity=q)
                           for s, q in observed.positions.items()},
                open_orders=[dict(order_id=i) for i in observed.open_order_ids],
            )
            return raw

        book.engine.observe = ExecutionObserver(
            read, lambda: quotes(book.now), now=lambda: book.now,
        )
        submitted = await book.engine.step(book.decision(5))
        assert submitted["actions"][0]["kind"] == "SUBMITTED"
        book.fill("1", 2, "20")
        assert (await book.engine.manage())["status"] == "WAIT_BROKER"
        book.engine.request_drain()
        # An old quote must not prevent cancellation; it still blocks a new sell.
        book.engine.observe.quote_snapshot = lambda: quotes(book.now - timedelta(seconds=31))
        cancelled = await book.engine.manage()
        assert cancelled["actions"][0]["kind"] == "CANCEL_REQUEST"
        book.fill("1", 3, "20", terminal=True)
        assert (await book.engine.manage())["reason"] == "STALE_EXECUTION_MARK"
        assert len(book.requests) == 2
        book.engine.observe.quote_snapshot = lambda: quotes(book.now)
        assert (await book.engine.manage())["actions"][0]["kind"] == "SUBMITTED"
        book.fill("2", 3, "20")
        assert (await book.engine.manage())["status"] == "STOPPED"


@pytest.mark.asyncio
async def test_calculated_account_resumes_partial_fill_drain_from_existing_database(tmp_path):
    database = tmp_path / "resume.db"

    def connect(book):
        async def read():
            observed = await book.observe()
            raw = calculated_account()
            raw.update(
                net_cash=str(observed.cash), execution_cash=str(observed.cash), nav=None,
                positions={s: dict(quantity=q, sellable_quantity=q)
                           for s, q in observed.positions.items()},
                open_orders=[dict(order_id=i) for i in observed.open_order_ids],
            )
            return raw
        book.engine.observe = ExecutionObserver(
            read, lambda: quotes(book.now), now=lambda: book.now,
        )

    async with rehearsal_session(database, capital_limit=Decimal("600"),
                                 mark=Decimal("20")) as book:
        connect(book)
        assert (await book.engine.step(book.decision(5)))["actions"][0]["kind"] == "SUBMITTED"
        book.fill("1", 2, "20")
        book.engine.request_drain()
        assert (await book.engine.manage())["actions"][0]["kind"] == "CANCEL_REQUEST"
        book.fill("1", 3, "20", terminal=True)
        orders = book.orders

    async with rehearsal_session(database, capital_limit=Decimal("600"),
                                 mark=Decimal("20")) as resumed:
        resumed.orders = orders
        connect(resumed)
        view = await resumed.engine.observe()
        assert view.cash == Decimal("539.85") and view.nav == Decimal("599.85")
        assert resumed.engine.drain_requested()
        assert (await resumed.engine.manage())["actions"][0]["kind"] == "SUBMITTED"
        assert resumed.orders["2"]["qty"] == 3
        resumed.fill("2", 3, "20")
        assert (await resumed.engine.manage())["status"] == "STOPPED"
        view = await resumed.engine.observe()
        assert view.nav == view.cash == Decimal("599.70")
        assert not view.positions
        assert (await resumed.engine.manage())["actions"] == []


@pytest.mark.asyncio
async def test_current_kis_reader_stays_unverified_in_the_new_bridge():
    rows = {
        "inquire-balance": dict(rt_cd="0", output1=[], ctx_area_fk200="", ctx_area_nk200=""),
        "inquire-nccs": dict(rt_cd="0", output=[], ctx_area_fk200="", ctx_area_nk200=""),
        "inquire-psamount": dict(rt_cd="0", output={"ovrs_ord_psbl_amt": "99999"}),
        "foreign-margin": dict(rt_cd="0", output=[]),
    }
    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json=rows[request.url.path.rsplit("/", 1)[1]])

    async with httpx.AsyncClient(
        base_url="https://kis.invalid", transport=httpx.MockTransport(handle),
    ) as client:
        async def read():
            return await observe_account(
                client, access_token="offline", app_key="offline", app_secret="offline",
                account="1234567801", now=lambda: NOW,
            )

        with pytest.raises(ObservationError, match="ACCOUNT_SCOPE_UNVERIFIED"):
            await ExecutionObserver(read, quotes, now=lambda: NOW)()
    assert calls == ["GET"] * 4


def test_wrong_quote_market_and_future_receipt_are_rejected():
    for bad in (replace(quotes()["SPY"], exchange="NASD"),
                replace(quotes()["SPY"], received_at=NOW + timedelta(seconds=1))):
        values = quotes()
        values["SPY"] = bad
        with pytest.raises(ObservationError):
            build_observation(account(), values, now=NOW)


@pytest.mark.asyncio
async def test_hung_reader_is_cancelled_and_cancellation_is_not_swallowed(monkeypatch):
    from auto_invest.execution import intraday_observation

    monkeypatch.setattr(intraday_observation, "READ_TIMEOUT_SECONDS", .01)
    exited = asyncio.Event()

    async def hanging():
        try:
            await asyncio.Event().wait()
        finally:
            exited.set()

    observer = ExecutionObserver(hanging, quotes, now=lambda: NOW)
    with pytest.raises(ObservationError, match="ACCOUNT_INPUT_UNAVAILABLE"):
        await observer()
    assert exited.is_set()
    monkeypatch.setattr(intraday_observation, "READ_TIMEOUT_SECONDS", 30)
    task = asyncio.create_task(observer())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
