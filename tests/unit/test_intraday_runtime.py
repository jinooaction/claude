import json
from datetime import UTC, datetime, timedelta

import pytest

from auto_invest.analytics.intraday_paper_challenger import load_preregistration
from auto_invest.analytics.intraday_runtime import PaperRuntime
from auto_invest.market_data.intraday import SYMBOLS, DataError, iso


def config():
    from pathlib import Path

    return load_preregistration(
        Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
    )


def bars(moment, price=100, volume=100000):
    return [
        dict(
            symbol=s,
            timestamp_utc=iso(moment),
            open=price,
            high=price + 1,
            low=price - 1,
            close=price + 0.2,
            volume=volume,
        )
        for s in SYMBOLS
    ]


def test_restart_idempotency_and_immutable_events(tmp_path):
    path = tmp_path / "paper.db"
    start = datetime(2026, 9, 4, 13, 30, tzinfo=UTC)
    runtime = PaperRuntime(path, config(), "test", True, "replay")
    for n in range(20):
        moment = start + timedelta(minutes=5 * n)
        runtime.process(bars(moment, 100 + n), moment + timedelta(minutes=5))
    expected = runtime.status()
    runtime.close()
    resumed = PaperRuntime(path, config(), "test", True, "replay")
    assert resumed.process(bars(start), start + timedelta(minutes=5)) is False
    assert resumed.status() == expected
    with pytest.raises(DataError, match="REVISION"):
        resumed.process(bars(start, 999), start + timedelta(minutes=5))
    with pytest.raises(Exception, match="append-only"):
        resumed.conn.execute("DELETE FROM intraday_events")
    assert expected["simulated_fills"] > 0
    assert expected["orders_submitted"] == 0
    assert expected["live_eligible"] is False


def test_gap_and_stale_new_entries_blocked(tmp_path):
    start = datetime(2026, 9, 4, 13, 30, tzinfo=UTC)
    runtime = PaperRuntime(tmp_path / "x.db", config(), "test", True, "forward")
    runtime.process(bars(start), start + timedelta(minutes=30))
    assert "STALE_BAR" in runtime.status()["halt_reasons"]
    runtime.process(bars(start + timedelta(minutes=10)), start + timedelta(minutes=15))
    assert "DATA_GAP" in runtime.status()["halt_reasons"]
    assert runtime.status()["simulated_fills"] == 0


def test_future_and_wrong_identity_and_foreign_db(tmp_path):
    start = datetime(2026, 9, 4, 13, 30, tzinfo=UTC)
    path = tmp_path / "x.db"
    runtime = PaperRuntime(path, config(), "test", True, "replay")
    with pytest.raises(DataError, match="BAR"):
        runtime.process(bars(start), start)
    runtime.close()
    with pytest.raises(DataError, match="IDENTITY"):
        PaperRuntime(path, config(), "other", True, "replay")
    import sqlite3

    conn = sqlite3.connect(tmp_path / "foreign.db")
    conn.execute("CREATE TABLE orders(id INTEGER)")
    conn.close()
    with pytest.raises(DataError, match="FOREIGN"):
        PaperRuntime(tmp_path / "foreign.db", config(), "test", True, "replay")


def test_partial_sell_residual_never_disappears(tmp_path):
    runtime = PaperRuntime(tmp_path / "x.db", config(), "test", True, "replay")
    start = datetime(2026, 9, 4, 13, 30, tzinfo=UTC)
    for n in range(78):
        moment = start + timedelta(minutes=5 * n)
        runtime.process(
            bars(moment, 100 + n * 0.1, 100000 if n < 74 else 1), moment + timedelta(minutes=5)
        )
    status = runtime.status()
    assert status["open_quantity"] > 0
    next_day = datetime(2026, 9, 8, 13, 30, tzinfo=UTC)
    runtime.process(bars(next_day), next_day + timedelta(minutes=5))
    assert "OVERNIGHT_RESIDUAL" in runtime.status()["halt_reasons"]
    assert runtime.status()["open_quantity"] == status["open_quantity"]
    assert json.dumps(runtime.status()).find("live_eligible") >= 0


def test_fill_uses_only_previous_marks_not_next_bar_close(tmp_path):
    import copy

    runtime = PaperRuntime(tmp_path / "x.db", config(), "test", True, "replay")
    candidate = runtime.candidates[0]
    moment = datetime(2026, 9, 4, 13, 35, tzinfo=UTC)
    account = runtime._initial()["accounts"][candidate.candidate_id]
    account["cash"] = 80000
    account["positions"]["SPY"] = 100
    account["pending"]["QQQ"] = dict(side="BUY", qty=2000, limit=10, eligible=iso(moment))
    outputs = []
    for spy_close in (100, 500):
        rows = {r["symbol"]: r for r in bars(moment, 10, 1000000)}
        rows["SPY"]["close"] = spy_close
        current = copy.deepcopy(account)
        actions = []
        runtime._fill(current, rows, moment, False, actions, candidate, {s: 100 for s in SYMBOLS})
        outputs.append((current, actions))
    assert outputs[0] == outputs[1]
    assert outputs[0][1][0]["qty"] == 1800


def test_independent_accounts_and_fixed_overnight_exit(tmp_path):
    runtime = PaperRuntime(tmp_path / "x.db", config(), "test", True, "replay")
    start = datetime(2026, 9, 4, 13, 30, tzinfo=UTC)
    # Inject the initial account only, before any immutable events exist.
    initial = runtime._initial()
    first = runtime.candidates[0].candidate_id
    initial["accounts"][first]["positions"]["SPY"] = 100
    initial["accounts"][first]["cash"] = 90000
    initial["accounts"][first]["pending"]["SPY"] = dict(
        side="SELL", qty=100, limit=100, eligible=iso(start - timedelta(days=1))
    )
    runtime._initial = lambda: initial
    runtime.process(bars(start, 50), start + timedelta(minutes=5))
    payload = json.loads(runtime.conn.execute("SELECT payload FROM intraday_events").fetchone()[0])
    accounts = payload["state"]["accounts"]
    assert accounts[first]["pending"]["SPY"]["limit"] == 100
    assert accounts[first]["positions"]["SPY"] == 100
    assert accounts[first]["halt_reasons"] == ["OVERNIGHT_RESIDUAL"]
    assert all(not a["halt_reasons"] for k, a in accounts.items() if k != first)


def test_two_connections_same_bar_only_one_commit(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "concurrent.db"
    moment = datetime(2026, 9, 4, 13, 30, tzinfo=UTC)

    def submit(_):
        runtime = PaperRuntime(path, config(), "test", True, "replay")
        try:
            return runtime.process(bars(moment), moment + timedelta(minutes=5))
        finally:
            runtime.close()

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(submit, range(2))) == [False, True]


def test_tampered_audit_rejected_on_reopen(tmp_path):
    path = tmp_path / "x.db"
    runtime = PaperRuntime(path, config(), "test", True, "replay")
    start = datetime(2026, 9, 4, 13, 30, tzinfo=UTC)
    runtime.process(bars(start), start + timedelta(minutes=5))
    runtime.conn.execute("DROP TRIGGER intraday_events_UPDATE")
    runtime.conn.execute("UPDATE intraday_events SET hash='corrupted'")
    runtime.close()
    with pytest.raises(DataError, match="AUDIT_INTEGRITY"):
        PaperRuntime(path, config(), "test", True, "replay")


def test_early_close_and_limit_not_touched(tmp_path):
    runtime = PaperRuntime(tmp_path / "x.db", config(), "test", True, "replay")
    moment = datetime(2026, 11, 27, 14, 30, tzinfo=UTC)
    for n in range(42):
        stamp = moment + timedelta(minutes=5 * n)
        runtime.process(bars(stamp, 100 + n * 0.1), stamp + timedelta(minutes=5))
    events = [json.loads(r[0]) for r in runtime.conn.execute("SELECT payload FROM intraday_events")]
    for event in events:
        for action in event["actions"]:
            if action["kind"] == "ORDER" and action["side"] == "BUY":
                assert action["eligible"] < "2026-11-27T17:45:00Z"
    assert runtime.status()["open_quantity"] == 0
