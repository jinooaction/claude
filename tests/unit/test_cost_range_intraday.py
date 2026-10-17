from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from auto_invest.analytics import cost_range_intraday as research
from auto_invest.analytics import intraday_paper_challenger as paper

CONTRACT = Path('specs/220-cost-range-research/contracts/preregistration.json')
PRIOR = Path('specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json')


def fixture(end='2024-03-12'):
    days = tuple(d.date() for d in paper._CALENDAR.sessions_window(end, -3))
    data = {}
    for symbol in paper.EXPECTED_UNIVERSE:
        data[symbol] = {}
        for day in days:
            start = paper._CALENDAR.session_open(str(day)).to_pydatetime()
            close = paper._CALENDAR.session_close(str(day)).to_pydatetime()
            count = int((close-start).total_seconds()/1800)
            data[symbol][day] = tuple(paper.ResampledBar(
                symbol=symbol, session_date=day, timestamp_utc=start+timedelta(minutes=30*i),
                end_utc=start+timedelta(minutes=30*(i+1)), timeframe_minutes=30, bar_index=i,
                open=100, high=100.5, low=100, close=100, volume=1000000, base_bar_count=6,
                complete=True, entry_eligible=i < count-1,
            ) for i in range(count))
    return data, days


def change(data, day, index, **values):
    rows = list(data['SPY'][day])
    rows[index] = replace(rows[index], **values)
    data['SPY'][day] = tuple(rows)


def signal(data, day):
    change(data, day, 0, high=100.9)
    change(data, day, 1, close=101, high=101.5)


def test_sealed_contract_and_no_live_registry_extension(tmp_path):
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    candidate, = research.candidate_registry(contract)
    assert candidate.family == 'cost_range_breakout' and candidate.timeframe_minutes == 30
    assert len(paper.build_candidate_registry(prior)) == 18
    assert candidate.candidate_id not in {
        c.candidate_id for c in paper.build_candidate_registry(prior)
    }
    changed = tmp_path/'changed.json'
    changed.write_bytes(CONTRACT.read_bytes()+b' ')
    with pytest.raises(ValueError, match='seal'):
        research.load_contract(changed, PRIOR)


@pytest.mark.parametrize('high,eligible', [(10040, True), (10039.99, False), (10040.01, True)])
def test_exact_economic_boundary(high, eligible):
    data, days = fixture()
    day = days[-1]
    change(data, day, 0, open=10000, low=9960, high=high, close=10000)
    change(data, day, 1, open=10000, low=10000, high=10042, close=10041)
    assert research.signal_plan(data, days)[('SPY', day, 1)][0] is eligible


@pytest.mark.parametrize('end,count', [('2024-03-12', 13), ('2024-11-29', 7)])
def test_calendar_and_no_same_opening_bar_signal(end, count):
    data, days = fixture(end)
    day = days[-1]
    signal(data, day)
    plan = research.signal_plan(data, days)
    assert len(data['SPY'][day]) == count
    assert plan[('SPY', day, 0)] == (False, False)
    assert plan[('SPY', day, 1)] == (True, False)
    assert plan[('SPY', day, count-2)] == (False, True)


def test_future_changes_leave_past_signal_unchanged():
    data, days = fixture()
    day = days[1]
    signal(data, day)
    before = research.signal_plan(data, days)
    for i in range(2, 13):
        change(data, day, i, open=1000, high=2000, low=900, close=1000, volume=0)
    for i in range(13):
        change(data, days[-1], i, high=2000, close=1000)
    assert research.signal_plan(data, days)[('SPY', day, 1)] == before[('SPY', day, 1)]


@pytest.mark.parametrize('slot', [0, 1])
def test_incomplete_input_cannot_signal(slot):
    data, days = fixture()
    signal(data, days[-1])
    change(data, days[-1], slot, complete=False)
    assert not research.signal_plan(data, days)[('SPY', days[-1], 1)][0]


@pytest.mark.parametrize('field,value', [('bar_index', 3), ('base_bar_count', 5),
                                        ('timeframe_minutes', 5)])
def test_bad_slot_rejected(field, value):
    data, days = fixture()
    change(data, days[-1], 1, **{field: value})
    with pytest.raises(ValueError, match='contiguous'):
        research.signal_plan(data, days)


def test_missing_bar_is_not_compressed():
    data, days = fixture()
    data['SPY'][days[-1]] = data['SPY'][days[-1]][1:]
    with pytest.raises(ValueError, match='contiguous'):
        research.signal_plan(data, days)


@pytest.mark.parametrize('model', ['base', 'stress'])
def test_next_bar_fill_and_final_bar_exit(model):
    data, days = fixture()
    day = days[-1]
    signal(data, day)
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    run = paper.simulate_candidate(research.candidate_registry(contract)[0], data, days, prior,
                                   cost_model_name=model,
                                   signal_plan=research.signal_plan(data, days))
    buy, sell = run.ledger_rows
    assert buy['eligible_at_utc'] == paper._iso(data['SPY'][day][2].timestamp_utc)
    assert sell['eligible_at_utc'] == paper._iso(data['SPY'][day][-1].timestamp_utc)
    assert run.total_net_pnl_usd == pytest.approx(-run.total_cost_usd)
    assert run.total_cost_usd > 0 and run.unclosed_quantity == 0


def test_failed_first_buy_does_not_get_another_attempt():
    data, days = fixture()
    day = days[-1]
    signal(data, day)
    change(data, day, 2, volume=0)
    change(data, day, 3, high=102, close=101)
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    candidate, = research.candidate_registry(contract)
    plan = research.signal_plan(data, days)
    assert plan[('SPY', day, 3)][0]
    run = paper.simulate_candidate(candidate, data, days, prior, cost_model_name='base',
                                   signal_plan=plan)
    assert len(run.ledger_rows) == 1 and run.ledger_rows[0]['fill_status'] == 'UNFILLED'
    for bad in [None, {}, {**plan, ('SPY', day, 1): (1, False)}]:
        with pytest.raises(ValueError, match='signal'):
            paper.simulate_candidate(candidate, data, days, prior, cost_model_name='base',
                                     signal_plan=bad)


def test_other_manifest_rejected_before_price_read(tmp_path, monkeypatch):
    manifest = tmp_path/'manifest.json'
    manifest.write_text('{}')
    monkeypatch.setattr(paper, 'load_intraday_dataset', lambda *a: pytest.fail('price read'))
    with pytest.raises(ValueError, match='price files not read'):
        research.load_development(tmp_path, manifest, {})


def test_source_replay_rejects_resealed_fabrication(monkeypatch):
    data, days = fixture()
    signal(data, days[-1])
    dataset = SimpleNamespace(sessions=days, dataset_fingerprint='sha256:fixture')
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    monkeypatch.setattr(research, 'validate_development', lambda *a: None)
    monkeypatch.setattr(paper, 'resample_dataset', lambda *a: data)
    result, ledger = research.run_development(dataset, contract, prior, code_commit='a'*40)
    assert result['minimum_cumulative_trials'] == 37
    assert result['verdict'] == 'DEVELOPMENT_REJECTED'
    assert result['safety'] == paper.EXPECTED_SAFETY and result['holdout_read'] is False
    assert research.verify_development(result, ledger, dataset, contract, prior) == result
    forged = deepcopy(result)
    forged['evaluations'][0]['base']['net_return_pct'] += 1
    forged.pop('content_sha256')
    forged['content_sha256'] = paper._sha256(paper._canonical_bytes(forged))
    with pytest.raises(ValueError, match='source replay'):
        research.verify_development(forged, ledger, dataset, contract, prior)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 0])
def test_invalid_price_rejected(value):
    data, days = fixture()
    change(data, days[-1], 0, high=value)
    with pytest.raises(ValueError, match='finite positive'):
        research.signal_plan(data, days)


def test_dst_changes_utc_slots_without_changing_local_rule():
    data, days = fixture()
    assert data['SPY'][days[0]][0].timestamp_utc.hour == 14
    assert data['SPY'][days[1]][0].timestamp_utc.hour == 13
    for day in days:
        signal(data, day)
    plan = research.signal_plan(data, days)
    assert all(plan[('SPY', day, 1)][0] for day in days)


def test_unfilled_final_exit_is_not_discarded():
    data, days = fixture()
    day = days[-1]
    signal(data, day)
    change(data, day, -1, volume=0)
    contract, prior = research.load_contract(CONTRACT, PRIOR)
    run = paper.simulate_candidate(research.candidate_registry(contract)[0], data, days, prior,
                                   cost_model_name='base',
                                   signal_plan=research.signal_plan(data, days))
    assert run.unclosed_quantity > 0
    assert run.ledger_rows[-1]['reason'] == 'session_close_liquidity_failure'
