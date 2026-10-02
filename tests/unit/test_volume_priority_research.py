from datetime import UTC, date, datetime, timedelta

import pytest

from auto_invest.analytics import sparse_opening_research as parent
from auto_invest.analytics.observed_intraday_inputs import Minute, ObservedSeries, Source
from auto_invest.analytics.volume_priority_research import (
    rank_ready_signals,
    read_contract,
    replay_volume_priority,
)

STAMP = datetime(2014, 3, 3, 14, 40, tzinfo=UTC)


def signal(symbol, volume, stamp=STAMP):
    return dict(decision_at=stamp.isoformat(), symbol=symbol, relative_volume=volume,
                signal_close=10.2, opening_low=9, opening_high=10.1)


def test_priority_is_independent_of_input_order_and_does_not_mutate_signals():
    rows = [signal('AAA', 2), signal('CCC', 4), signal('BBB', 4)]
    before = [dict(row) for row in rows]
    assert [r['symbol'] for r in rank_ready_signals(rows, STAMP)] == ['BBB', 'CCC', 'AAA']
    assert rank_ready_signals(list(reversed(rows)), STAMP) == rank_ready_signals(rows, STAMP)
    assert rows == before


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, 0, 1.99, True, '3'])
def test_unusable_relative_volume_is_refused(value):
    with pytest.raises(ValueError):
        rank_ready_signals([signal('AAA', value)], STAMP)


@pytest.mark.parametrize('offset', [-5, 5])
def test_signals_from_another_decision_time_are_not_reordered(offset):
    with pytest.raises(ValueError):
        rank_ready_signals([signal('AAA', 2, STAMP+timedelta(minutes=offset))], STAMP)


def test_duplicate_symbol_cannot_consume_two_reservations():
    with pytest.raises(ValueError):
        rank_ready_signals([signal('AAA', 2), signal('AAA', 5)], STAMP)


def test_new_contract_preserves_cost_model_and_is_not_a_promotion_grant():
    contract = read_contract()
    assert contract['minimum_prior_trials'] == 35
    assert contract['minimum_total_trials'] == 36
    assert contract['parent_contract_sha256'] == parent.CONTRACT_SHA256
    assert not contract['holdout_read'] and not contract['safety']['broker_access']
    assert not contract['safety']['live_eligible']


def test_wrong_input_identity_is_refused_before_consuming_prices():
    def forbidden():
        raise AssertionError('price stream consumed before identity check')
        yield

    with pytest.raises(ValueError):
        replay_volume_priority({'manifest_sha256': '0'*64, 'days': forbidden()})


@pytest.mark.parametrize('entry_volume', [100000, 100])
def test_shared_cash_and_position_limit_allocate_ready_signals_in_new_order(
        monkeypatch, entry_volume):
    day = date(2014, 3, 3)
    members = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE']
    data = {}
    for symbol in members:
        source = Source(symbol, '0'*64, 'synthetic', 'none', 'unverified')
        series = ObservedSeries(source, day, day, [])
        lo, hi = series.bounds(day)
        bars = [Minute(lo+timedelta(minutes=10), 10.2, 10.2, 10.2, 10.2, entry_volume),
                Minute(hi-timedelta(minutes=5), 11, 11, 11, 11, 100000)]
        data[symbol] = ObservedSeries(source, day, day, bars)

    class ReadySignals:
        input_unavailable = None

        def __init__(self, sessions):
            self.attempted = False

        def entry(self, series, session, stamp):
            if stamp != STAMP or self.attempted:
                return None
            self.attempted = True
            return signal(series.source.symbol, members.index(series.source.symbol)+2, stamp)

        @staticmethod
        def exit_due(series, session, stamp, opening_low):
            return stamp >= series.bounds(session)[1]-timedelta(minutes=5)

    monkeypatch.setattr(parent, 'OpeningSignals', ReadySignals)

    def replay(priority):
        events = {'base': [], 'stress': []}
        inputs = {'sessions': (day,), 'contract': {'members': members},
                  'days': iter([(day, data)])}
        result = parent._replay_research(
            inputs, {name: rows.append for name, rows in events.items()},
            relative_volume_priority=priority,
        )
        return result, events

    original, old_events = replay(False)
    ranked, new_events = replay(True)

    def reserved(rows):
        return [row['symbol'] for row in rows if row['kind'] == 'ENTRY_RESERVED']

    for name in ('base', 'stress'):
        assert reserved(old_events[name]) == ['AAA', 'BBB', 'CCC', 'DDD']
        assert reserved(new_events[name]) == ['EEE', 'DDD', 'CCC', 'BBB']
        assert [r['symbol'] for r in new_events[name]
                if r['kind'] == 'ENTRY_REJECTED'] == ['AAA']
        assert ranked['scenarios'][name]['closed_roundtrips'] == 4
        assert ranked['scenarios'][name]['unclosed_quantity'] == 0
        assert ranked['scenarios'][name]['minimum_cash'] >= 0
        assert ranked['scenarios'][name]['unsettled'] > 0
        if entry_volume == 100:
            observed = [row for row in new_events[name] if row['kind'] == 'ENTRY_OBSERVED']
            assert len(observed) == 4 and all(row['quantity'] == 1 for row in observed)
    assert not original['live_eligible'] and not ranked['live_eligible']

    public_events = {'base': [], 'stress': []}
    public = parent.replay_research(
        {'sessions': (day,), 'contract': {'members': members}, 'days': iter([(day, data)])},
        {name: rows.append for name, rows in public_events.items()},
    )
    assert public == original and public_events == old_events


def test_contract_tampering_is_refused(tmp_path, monkeypatch):
    from auto_invest.analytics import volume_priority_research as candidate

    changed = tmp_path/'preregistration.json'
    changed.write_text('{}')
    monkeypatch.setattr(candidate, 'CONTRACT', changed)
    with pytest.raises(ValueError, match='contract changed'):
        read_contract()


def test_original_public_replay_has_no_priority_override():
    with pytest.raises(TypeError):
        parent.replay_research({}, relative_volume_priority=True)
