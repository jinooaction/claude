from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics import late_session_intraday as research

CONTRACT = Path("specs/198-late-session-research/contracts/preregistration.json")
PRIOR = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")


def fixture(end="2024-03-12"):
    days = tuple(day.date() for day in paper._CALENDAR.sessions_window(end, -3))
    data = {}
    for symbol in paper.EXPECTED_UNIVERSE:
        data[symbol] = {}
        for day in days:
            start = paper._CALENDAR.session_open(str(day)).to_pydatetime()
            close = paper._CALENDAR.session_close(str(day)).to_pydatetime()
            count = int((close-start).total_seconds() / 300)
            data[symbol][day] = tuple(paper.ResampledBar(
                symbol=symbol, session_date=day, timestamp_utc=start+timedelta(minutes=5*i),
                end_utc=start+timedelta(minutes=5*(i+1)), timeframe_minutes=5, bar_index=i,
                open=100, high=103, low=99, close=100, volume=1000000, base_bar_count=1,
                complete=True, entry_eligible=i < count-1,
            ) for i in range(count))
    return data, days


def change(data, day, index, **values):
    rows = list(data["SPY"][day])
    rows[index] = replace(rows[index], **values)
    data["SPY"][day] = tuple(rows)


def bullish(data, day):
    change(data, day, 5, close=101)
    change(data, day, -7, close=102)


def test_contract_and_candidate_identity(tmp_path):
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    candidate, = research.candidate_registry(contract)
    assert candidate.family == "late_session" and candidate.timeframe_minutes == 5
    assert len(paper.build_candidate_registry(prior)) == 18
    changed = tmp_path / "changed.json"
    changed.write_bytes(CONTRACT.read_bytes()+b" ")
    with pytest.raises(ValueError, match="seal"):
        research.load_contract(changed, PRIOR)


@pytest.mark.parametrize("end,count", [("2024-03-12", 78), ("2024-11-29", 42)])
def test_exact_calendar_time_and_first_day_no_entry(end, count):
    data, days = fixture(end)
    for day in days:
        bullish(data, day)
    plan = research.signal_plan(data, days)
    day = days[-1]
    assert len(data["SPY"][day]) == count
    buys = [i for (s, d, i), flags in plan.items() if s == "SPY" and d == day and flags[0]]
    assert buys == [count-7]
    assert not any(v[0] for (s, d, i), v in plan.items() if d == days[0])
    assert plan[("SPY", day, count-2)] == (False, True)


@pytest.mark.parametrize("slot,price", [(5, 100), (-7, 100), (5, 99), (-7, 99)])
def test_both_returns_must_be_strictly_positive(slot, price):
    data, days = fixture()
    bullish(data, days[-1])
    change(data, days[-1], slot, close=price)
    assert not any(v[0] for v in research.signal_plan(data, days).values())


def test_dst_holiday_and_exact_previous_session():
    data, days = fixture("2024-03-12")
    assert data["SPY"][days[0]][0].timestamp_utc.hour == 14
    assert data["SPY"][days[1]][0].timestamp_utc.hour == 13
    bullish(data, days[-1])
    assert research.signal_plan(data, days)[("SPY", days[-1], 71)][0]
    del data["SPY"][days[-2]]
    reduced = tuple(d for d in days if d != days[-2])
    assert not research.signal_plan(data, reduced)[("SPY", days[-1], 71)][0]


def test_future_prices_do_not_change_entry():
    data, days = fixture()
    day = days[1]
    bullish(data, day)
    before = research.signal_plan(data, days)
    for index in range(72, 78):
        change(data, day, index, close=1000, high=2000, volume=0)
    for index in range(78):
        change(data, days[-1], index, close=1000, high=2000)
    after = research.signal_plan(data, days)
    assert after[("SPY", day, 71)] == before[("SPY", day, 71)] == (True, False)


@pytest.mark.parametrize("slot", [5, 71])
def test_incomplete_required_observation_has_no_signal(slot):
    data, days = fixture()
    bullish(data, days[-1])
    change(data, days[-1], slot, complete=False)
    assert not research.signal_plan(data, days)[("SPY", days[-1], 71)][0]


def test_wrong_slot_and_missing_previous_close():
    data, days = fixture()
    bullish(data, days[-1])
    change(data, days[-2], -1, complete=False)
    assert not research.signal_plan(data, days)[("SPY", days[-1], 71)][0]
    change(data, days[-1], 5, bar_index=7)
    with pytest.raises(ValueError, match="contiguous"):
        research.signal_plan(data, days)


@pytest.mark.parametrize("model", ["base", "stress"])
def test_next_open_exit_and_costs(model):
    data, days = fixture()
    day = days[-1]
    bullish(data, day)
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    run = paper.simulate_candidate(research.candidate_registry(contract)[0], data, days, prior,
                                   cost_model_name=model,
                                   signal_plan=research.signal_plan(data, days))
    buy, sell = run.ledger_rows
    assert buy["eligible_at_utc"] == paper._iso(data["SPY"][day][72].timestamp_utc)
    assert sell["eligible_at_utc"] == paper._iso(data["SPY"][day][77].timestamp_utc)
    assert buy["signal_at_utc"] == buy["eligible_at_utc"]
    assert run.total_net_pnl_usd == pytest.approx(-run.total_cost_usd)
    assert run.total_cost_usd > 0 and run.unclosed_quantity == 0


@pytest.mark.parametrize("volume", [0, 100])
def test_final_exit_failure_is_retained(volume):
    data, days = fixture()
    bullish(data, days[-1])
    change(data, days[-1], -1, volume=volume)
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    run = paper.simulate_candidate(research.candidate_registry(contract)[0], data, days, prior,
                                   cost_model_name="base",
                                   signal_plan=research.signal_plan(data, days))
    assert run.unclosed_quantity > 0
    assert run.ledger_rows[-1]["reason"] == "session_close_liquidity_failure"
    assert run.ledger_rows[-1]["unfilled_qty"] == run.unclosed_quantity


def test_unfilled_buy_cannot_retry_and_mapping_is_checked():
    data, days = fixture()
    day = days[-1]
    bullish(data, day)
    change(data, day, 72, volume=0)
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    candidate = research.candidate_registry(contract)[0]
    plan = research.signal_plan(data, days)
    plan[("SPY", day, 73)] = (True, False)
    run = paper.simulate_candidate(candidate, data, days, prior,
                                   cost_model_name="base", signal_plan=plan)
    assert len(run.ledger_rows) == 1 and run.ledger_rows[0]["fill_status"] == "UNFILLED"
    for bad in [None, {}, {**plan, ("SPY", day, 71): (1, False)}]:
        with pytest.raises(ValueError, match="signal"):
            paper.simulate_candidate(candidate, data, days, prior,
                                     cost_model_name="base", signal_plan=bad)


def test_other_manifest_rejected_before_prices(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    monkeypatch.setattr(paper, "load_intraday_dataset", lambda *a: pytest.fail("price read"))
    with pytest.raises(ValueError, match="price files not read"):
        research.load_development(tmp_path, manifest, {})


def test_replay_rejects_resealed_fabricated_metrics(monkeypatch):
    data, days = fixture()
    bullish(data, days[-1])
    dataset = SimpleNamespace(sessions=days, dataset_fingerprint="sha256:fixture")
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    contract = deepcopy(contract)
    contract["development"]["evaluation_sessions"] = len(days)-1
    monkeypatch.setattr(research, "validate_development", lambda *a: None)
    monkeypatch.setattr(paper, "resample_dataset", lambda *a: data)
    result, ledger = research.run_development(dataset, contract, prior, code_commit="a"*40)
    assert result["evaluation_session_count"] == len(days)-1
    assert result["minimum_cumulative_trials"] == 32
    assert result["verdict"] == "DEVELOPMENT_REJECTED"
    assert result["safety"] == paper.EXPECTED_SAFETY and result["holdout_read"] is False
    assert research.verify_development(result, ledger, dataset, contract, prior) == result
    forged = deepcopy(result)
    forged["evaluations"][0]["base"]["net_return_pct"] += 1
    forged.pop("content_sha256")
    forged["content_sha256"] = paper._sha256(paper._canonical_bytes(forged))
    with pytest.raises(ValueError, match="source replay"):
        research.verify_development(forged, ledger, dataset, contract, prior)
    with pytest.raises(ValueError, match="ledger fingerprint"):
        research.validate_seal(result, ledger+b"changed")


def test_five_minute_resampling_preserves_source_and_old_registry():
    data, days = fixture("2024-11-29")
    base = {symbol: tuple(paper.IntradayBar(
        symbol=symbol, timestamp_utc=bar.timestamp_utc, session_date=day,
        session_open_utc=rows[0].timestamp_utc, session_close_utc=rows[-1].end_utc,
        open=bar.open, high=bar.high, low=bar.low, close=bar.close, volume=bar.volume,
    ) for day, rows in by_day.items() for bar in rows) for symbol, by_day in data.items()}
    dataset = SimpleNamespace(bars_by_symbol=base, sessions=days)
    actual = paper.resample_dataset(dataset, 5)
    assert actual == data
    assert paper.EXPECTED_TIMEFRAMES == (15, 30, 60)


def test_partial_exit_keeps_retrying_after_exit_signal_disappears():
    data, days = fixture()
    day = days[-1]
    bullish(data, day)
    plan = research.signal_plan(data, days)
    plan[("SPY", day, 73)] = (False, True)
    change(data, day, 74, volume=100)
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    run = paper.simulate_candidate(research.candidate_registry(contract)[0], data, days, prior,
                                   cost_model_name="base", signal_plan=plan)
    assert [row["side"] for row in run.ledger_rows] == ["BUY", "SELL", "SELL"]
    assert run.ledger_rows[1]["fill_status"] == "PARTIAL"
    assert run.ledger_rows[2]["eligible_at_utc"] == paper._iso(data["SPY"][day][75].timestamp_utc)
    assert run.unclosed_quantity == 0
