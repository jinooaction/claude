from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from auto_invest.analytics import intraday_paper_challenger as paper
from auto_invest.analytics import noise_band_intraday as research

CONTRACT = Path("specs/192-noise-band-research/contracts/preregistration.json")
PRIOR = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")


def fixture(end="2024-03-12"):
    sessions = tuple(d.date() for d in paper._CALENDAR.sessions_window(end, -16))
    resampled = {}
    for symbol in paper.EXPECTED_UNIVERSE:
        resampled[symbol] = {}
        for day in sessions:
            start = paper._CALENDAR.session_open(str(day)).to_pydatetime()
            end_at = paper._CALENDAR.session_close(str(day)).to_pydatetime()
            count = int((end_at-start).total_seconds() / 1800)
            resampled[symbol][day] = tuple(paper.ResampledBar(
                symbol=symbol, session_date=day, timestamp_utc=start+timedelta(minutes=30*i),
                end_utc=start+timedelta(minutes=30*(i+1)), timeframe_minutes=30, bar_index=i,
                open=100, high=101, low=99, close=100, volume=1000000, base_bar_count=6,
                complete=True, entry_eligible=i < count-1,
            ) for i in range(count))
    return resampled, sessions


def change(data, day, index, **values):
    rows = list(data["SPY"][day])
    rows[index] = replace(rows[index], **values)
    data["SPY"][day] = tuple(rows)


def test_contract_registry_and_tamper(tmp_path):
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    assert len(research.candidate_registry(contract)) == 1
    assert len(paper.build_candidate_registry(prior)) == 18
    altered = tmp_path / "changed.json"
    altered.write_bytes(CONTRACT.read_bytes()+b" ")
    with pytest.raises(ValueError, match="seal"):
        research.load_contract(altered, PRIOR)


def test_fourteen_prior_days_mean_gap_and_strict_boundary():
    data, days = fixture()
    for day in days[:14]:
        change(data, day, 0, close=101)
    day = days[14]
    change(data, day, 0, close=101)
    key = ("SPY", day, 0)
    signals = research.signal_plan(data, days)
    assert signals[key] == (False, True)  # exact upper 100*(1+.01)
    assert not any(flags[0] for (_, d, _), flags in signals.items() if d in days[:14])
    change(data, day, 0, close=101.01)
    assert research.signal_plan(data, days)[key] == (True, False)
    change(data, days[13], -1, close=102)
    assert research.signal_plan(data, days)[key] == (False, True)


def test_current_and_future_rows_cannot_change_previous_signals():
    data, days = fixture()
    change(data, days[14], 0, close=102)
    original = research.signal_plan(data, days)
    changed = deepcopy(data)
    for index in range(1, 13):
        change(changed, days[14], index, close=1000, high=1200, volume=10)
    for index in range(13):
        change(changed, days[15], index, close=2000, high=2500)
    actual = research.signal_plan(changed, days)
    for key in original:
        if key[1] < days[14] or (key[1] == days[14] and key[2] == 0):
            assert actual[key] == original[key]
    assert actual[("SPY", days[14], 0)][0]


def test_dst_uses_session_slot_not_utc_clock():
    data, days = fixture()
    assert data["SPY"][days[0]][0].timestamp_utc.hour == 14
    assert data["SPY"][days[-1]][0].timestamp_utc.hour == 13
    change(data, days[-1], 0, close=102)
    assert research.signal_plan(data, days)[("SPY", days[-1], 0)][0]


def test_missing_exchange_day_is_not_replaced_with_older_day():
    data, days = fixture()
    change(data, days[-1], 0, close=102)
    assert research.signal_plan(data, days)[("SPY", days[-1], 0)][0]
    reduced = tuple(d for d in days if d != days[5])
    for symbol in data:
        del data[symbol][days[5]]
    assert research.signal_plan(data, reduced)[("SPY", days[-1], 0)] == (False, False)


def test_half_day_missing_slot_disables_only_that_slot():
    data, days = fixture("2024-12-03")
    day = days[-1]
    assert any(len(data["SPY"][d]) == 7 for d in days[:-1])
    change(data, day, 0, close=102)
    change(data, day, 9, close=103)
    result = research.signal_plan(data, days)
    assert result[("SPY", day, 0)][0]
    assert result[("SPY", day, 9)] == (False, False)


def test_zero_volume_and_discontinuous_bars():
    data, days = fixture()
    change(data, days[-1], 0, volume=0, close=102)
    assert research.signal_plan(data, days)[("SPY", days[-1], 0)] == (False, False)
    change(data, days[-1], 1, bar_index=3)
    with pytest.raises(ValueError, match="contiguous"):
        research.signal_plan(data, days)


def engine_fixture():
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    candidate = research.candidate_registry(contract)[0]
    data, days = fixture()
    day = days[-1]
    data = {symbol: {day: data[symbol][day]} for symbol in data}
    plan = {(symbol, day, i): (i == 0, i == 2)
            for symbol in data for i in range(13)}
    return candidate, prior, data, day, plan


@pytest.mark.parametrize("volume", [0, 100])
def test_exit_attempt_remains_pending_when_signal_reverses(volume):
    candidate, prior, data, day, plan = engine_fixture()
    change(data, day, 3, volume=volume)
    run = paper.simulate_candidate(candidate, data, [day], prior,
                                   cost_model_name="base", signal_plan=plan)
    rows = [row for row in run.ledger_rows if row["symbol"] == "SPY"]
    assert [row["side"] for row in rows] == ["BUY", "SELL", "SELL"]
    assert rows[0]["eligible_at_utc"] == paper._iso(data["SPY"][day][1].timestamp_utc)
    assert rows[-1]["eligible_at_utc"] == paper._iso(data["SPY"][day][4].timestamp_utc)
    assert run.unclosed_quantity == 0


def test_unfilled_buy_consumes_only_attempt_and_final_exit_failure():
    candidate, prior, data, day, plan = engine_fixture()
    change(data, day, 1, volume=0)
    plan[("SPY", day, 4)] = (True, False)
    run = paper.simulate_candidate(candidate, data, [day], prior,
                                   cost_model_name="base", signal_plan=plan)
    rows = [row for row in run.ledger_rows if row["symbol"] == "SPY"]
    assert len(rows) == 1 and rows[0]["fill_status"] == "UNFILLED"
    candidate, prior, data, day, plan = engine_fixture()
    for key in plan:
        plan[key] = (key[2] == 0, False)
    change(data, day, 12, volume=0)
    run = paper.simulate_candidate(candidate, data, [day], prior,
                                   cost_model_name="base", signal_plan=plan)
    assert run.unclosed_quantity > 0


def test_mapping_must_be_complete_boolean_and_family_specific():
    candidate, prior, data, day, plan = engine_fixture()
    for value in [None, {}, {**plan, ("SPY", day, 0): (1, False)}]:
        with pytest.raises(ValueError, match="signal"):
            paper.simulate_candidate(candidate, data, [day], prior,
                                     cost_model_name="base", signal_plan=value)
    old_candidate = paper.build_candidate_registry(prior)[0]
    with pytest.raises(ValueError, match="only allowed"):
        paper.simulate_candidate(old_candidate, data, [day], prior,
                                 cost_model_name="base", signal_plan=plan)


def test_other_manifest_rejected_before_prices(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    monkeypatch.setattr(paper, "load_intraday_dataset", lambda *a: pytest.fail("price read"))
    with pytest.raises(ValueError, match="price files not read"):
        research.load_development(tmp_path, manifest, {})


def test_vwap_can_be_higher_than_noise_boundary():
    data, days = fixture()
    day = days[-1]
    change(data, day, 0, high=110, low=100, close=109)
    change(data, day, 1, close=102)
    signals = research.signal_plan(data, days)
    assert signals[("SPY", day, 0)][0]
    assert signals[("SPY", day, 1)] == (False, True)


def test_gap_up_uses_current_open_as_upper_anchor():
    data, days = fixture()
    day = days[-1]
    change(data, day, 0, open=105, high=106, low=103, close=104)
    assert research.signal_plan(data, days)[("SPY", day, 0)] == (False, True)
    change(data, day, 0, close=106)
    assert research.signal_plan(data, days)[("SPY", day, 0)] == (True, False)


def test_penultimate_signal_cannot_buy_without_time_to_exit():
    candidate, prior, data, day, plan = engine_fixture()
    for key in plan:
        plan[key] = (key[2] == 11, False)
    run = paper.simulate_candidate(candidate, data, [day], prior,
                                   cost_model_name="base", signal_plan=plan)
    assert run.ledger_rows == ()


def test_development_reports_evaluation_window_and_replays(monkeypatch):
    data, days = fixture()
    for day in days[-2:]:
        change(data, day, 0, close=102)
    dataset = SimpleNamespace(sessions=days, dataset_fingerprint="sha256:fixture")
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    contract = deepcopy(contract)
    contract["development"]["evaluation_sessions"] = 2
    monkeypatch.setattr(research, "validate_development", lambda *a: None)
    monkeypatch.setattr(paper, "resample_dataset", lambda *a: data)
    result, ledger = research.run_development(dataset, contract, prior, code_commit="a"*40)
    assert result["session_count"] == 16
    assert result["evaluation_session_count"] == 2
    assert result["warmup_session_count"] == 14
    assert result["minimum_cumulative_trials"] == 29
    assert result["holdout_read"] is False
    assert result["safety"] == paper.EXPECTED_SAFETY
    assert result["verdict"] == "DEVELOPMENT_REJECTED"
    assert len(result["evaluations"]) == 1
    assert research.verify_development(result, ledger, dataset, contract, prior) == result
    forged = deepcopy(result)
    forged["evaluations"][0]["base"]["net_return_pct"] += 1
    forged.pop("content_sha256")
    forged["content_sha256"] = paper._sha256(paper._canonical_bytes(forged))
    with pytest.raises(ValueError, match="source replay"):
        research.verify_development(forged, ledger, dataset, contract, prior)
    with pytest.raises(ValueError, match="ledger fingerprint"):
        research.validate_seal(result, ledger+b"tampered")
