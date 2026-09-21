"""Offline sealed replay and independent cash-ledger arithmetic verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path

import exchange_calendars as xc

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT/'specs/194-sparse-opening-research/contracts'


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition):
    if not condition:
        raise ValueError('research ledger verification failed')


def equal(left, right):
    require(isinstance(left, (int, float)) and not isinstance(left, bool)
            and math.isfinite(left) and abs(left-right) <= 1e-7)


def verify_ledger(path, summary, cost):
    """Reconstruct balances from journal primitives without calling ResearchAccount."""
    cash, realized, minimum = 10000.0, 0.0, 10000.0
    reservations, positions, settlements = {}, {}, []
    closed = missing = sequence = 0
    unavailable = {}
    previous = None
    with path.open() as handle:
        for line in handle:
            event = json.loads(line)
            sequence += 1
            require(event['sequence'] == sequence)
            stamp = datetime.fromisoformat(event['at'])
            require(stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0)
                    and (previous is None or stamp >= previous))
            previous = stamp
            kind, symbol = event['kind'], event['symbol']
            if kind == 'ENTRY_RESERVED':
                require(symbol not in reservations and symbol not in positions
                        and len(reservations)+len(positions) < 4
                        and not any(p['exit_pending'] for p in positions.values()))
                room = 8000-sum(r['amount'] for r in reservations.values())-sum(
                    p['basis'] for p in positions.values())
                quantity = math.floor(max(0, min(2000, cash, room))/(event['limit']*(1+cost)))
                require(type(event['quantity']) is int and event['quantity'] == quantity > 0)
                amount = quantity*event['limit']*(1+cost)
                equal(event['amount'], amount)
                cash -= amount
                reservations[symbol] = event
            elif kind == 'ENTRY_OBSERVED':
                reserved = reservations.pop(symbol)
                quantity = event['quantity']
                require(type(quantity) is int and 0 <= quantity <= reserved['quantity'])
                require(datetime.fromisoformat(reserved['at'])+timedelta(minutes=1) == stamp)
                require(event['reference_at'] == reserved['at'])
                require(not quantity or 0 < event['price'] <= reserved['limit'])
                expected = (min(reserved['quantity'], event['reference_capacity'])
                            if event['price'] is not None and event['price'] <= reserved['limit']
                            else 0)
                require(quantity == expected)
                basis = quantity*event['price']*(1+cost) if quantity else 0
                equal(event['basis'], basis)
                equal(event['released'], reserved['amount']-basis)
                cash += reserved['amount']-basis
                if quantity:
                    positions[symbol] = {'quantity': quantity, 'basis': basis,
                                         'exit_pending': False}
            elif kind == 'EXIT_REQUESTED':
                require(not positions[symbol]['exit_pending'])
                equal(event['quantity'], positions[symbol]['quantity'])
                positions[symbol]['exit_pending'] = True
            elif kind == 'EXIT_OBSERVED':
                position = positions[symbol]
                quantity = event['quantity']
                require(position['exit_pending'] and type(quantity) is int
                        and 0 <= quantity <= position['quantity'])
                require(datetime.fromisoformat(event['reference_at'])+timedelta(minutes=1)
                        == stamp)
                require(quantity == (min(position['quantity'], event['reference_capacity'])
                                     if event['price'] is not None else 0))
                basis = position['basis']*quantity/position['quantity']
                proceeds = quantity*event['price']*(1-cost) if quantity else 0
                equal(event['basis'], basis)
                equal(event['proceeds'], proceeds)
                if quantity:
                    require(event['price'] > 0 and event['due'] is not None)
                    due = datetime.fromisoformat(event['due'])
                    sale_day = datetime.fromisoformat(event['reference_at']).date()
                    calendar = xc.get_calendar('XNYS', start=sale_day-timedelta(days=7),
                                               end=sale_day+timedelta(days=15))
                    sale_session = calendar.date_to_session(str(sale_day))
                    due_session = calendar.session_offset(sale_session, 2)
                    require(due == calendar.session_open(due_session).to_pydatetime())
                    settlements.append((symbol, event['due'], proceeds))
                    realized += proceeds-basis
                    position['quantity'] -= quantity
                    position['basis'] -= basis
                    if position['quantity'] == 0:
                        closed += 1
                        del positions[symbol]
            elif kind == 'SETTLEMENT_RELEASED':
                index = next(i for i, s in enumerate(settlements)
                             if s[0] == symbol and s[1] == event['due']
                             and abs(s[2]-event['amount']) <= 1e-7)
                settlement = settlements.pop(index)
                require(datetime.fromisoformat(settlement[1]) <= stamp)
                cash += settlement[2]
            else:
                require(kind in ('SIGNAL', 'ENTRY_REJECTED', 'INPUT_UNAVAILABLE'))
                if kind == 'INPUT_UNAVAILABLE':
                    reason = event['reason']
                    require(reason in ('WARMUP', 'OPENING_MISSING', 'LOOKBACK_MISSING',
                                       'ZERO_LOOKBACK_VOLUME'))
                    unavailable[reason] = unavailable.get(reason, 0)+1
            if event.get('status') in ('MISSING', 'ZERO_VOLUME'):
                missing += 1
                require(event['quantity'] == 0)
            require(cash >= -1e-8)
            equal(event['cash_after'], cash)
            equal(event['reserved_after'], sum(r['amount'] for r in reservations.values()))
            minimum = min(minimum, cash)
    unsettled = sum(s[2] for s in settlements)
    for key, value in {'cash': cash, 'reserved': sum(r['amount'] for r in reservations.values()),
                       'unsettled': unsettled, 'realized_profit': realized,
                       'minimum_cash': minimum, 'event_count': sequence,
                       'closed_roundtrips': closed, 'unobserved_references': missing,
                       'unclosed_quantity': sum(p['quantity'] for p in positions.values())}.items():
        equal(summary[key], value)
    require(set(summary['positions']) == set(positions))
    require(summary.get('input_unavailable_counts', {}) == unavailable)
    for symbol, position in positions.items():
        for key in ('quantity', 'basis'):
            equal(summary['positions'][symbol][key], position[key])
        require(summary['positions'][symbol]['exit_pending'] == position['exit_pending'])
    if positions or reservations:
        require(summary['net_profit'] is None and summary['net_return'] is None)
    else:
        equal(summary['net_profit'], cash+unsettled-10000)
        equal(summary['net_return'], (cash+unsettled-10000)/10000)
    require(summary['live_eligible'] is False and summary['promotion_allowed'] is False
            and summary['fill_verified'] is False and summary['lineage_verified'] is False
            and summary['capacity_unknown'] is True and summary['orders_submitted'] == 0
            and summary['actual_capital_fraction'] == 0)


def verify(directory):
    from auto_invest.analytics.sparse_opening_research import CONTRACT_SHA256, INVENTORY_SHA256

    result = json.loads((directory/'result.json').read_text())
    require(result['contract_sha256'] == CONTRACT_SHA256
            and result['inventory_sha256'] == INVENTORY_SHA256)
    require(set(result['ledger_sha256']) == {'base', 'stress'})
    require(fingerprint(directory/'input-manifest.json') == result['manifest_sha256'])
    for name, cost in [('base', .0031), ('stress', .004)]:
        path = directory/f'{name}.jsonl'
        require(fingerprint(path) == result['ledger_sha256'][name])
        verify_ledger(path, result['scenarios'][name], cost)
    scenarios = result['scenarios']
    passed = scenarios['base']['closed_roundtrips'] >= 200 and all(
        s['net_profit'] is not None and s['net_profit'] > 0 and s['unclosed_quantity'] == 0
        for s in scenarios.values())
    require(result['status'] == ('INDEPENDENT_VALIDATION_REQUIRED' if passed
                                 else 'DEVELOPMENT_REJECTED'))
    require(result['live_eligible'] is False and result['promotion_allowed'] is False
            and result['orders_submitted'] == 0 and result['actual_capital_fraction'] == 0)
    return {'verified': True, 'status': result['status'], 'live_eligible': False}


def replay(manifest, output):
    code_paths = (Path(__file__).resolve(),
                  ROOT/'src/auto_invest/analytics/sparse_opening_research.py',
                  ROOT/'src/auto_invest/analytics/observed_intraday_inputs.py')
    code_sha256 = {str(path.relative_to(ROOT)): fingerprint(path) for path in code_paths}
    from auto_invest.analytics.sparse_opening_research import (
        CONTRACT_SHA256,
        INVENTORY_SHA256,
        replay_research,
        research_inputs,
    )

    manifest_bytes = manifest.read_bytes()
    with research_inputs(manifest, CONTRACTS) as inputs:
        require(inputs['manifest_sha256'] == hashlib.sha256(manifest_bytes).hexdigest())
        output.mkdir(parents=True, exist_ok=False)
        (output/'input-manifest.json').write_bytes(manifest_bytes)
        with ExitStack() as stack:
            files = {name: stack.enter_context((output/f'{name}.jsonl').open('x'))
                     for name in ('base', 'stress')}
            sinks = {name: (lambda event, handle=handle:
                            handle.write(json.dumps(event, allow_nan=False)+'\n'))
                     for name, handle in files.items()}
            result = replay_research(inputs, sinks)
        require(code_sha256 == {str(path.relative_to(ROOT)): fingerprint(path)
                                for path in code_paths})
        result.update(manifest_sha256=inputs['manifest_sha256'],
                      contract_sha256=CONTRACT_SHA256, inventory_sha256=INVENTORY_SHA256,
                      ledger_sha256={name: fingerprint(output/f'{name}.jsonl') for name in files},
                      code_sha256=code_sha256)
        (output/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return verify(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('replay')
    run.add_argument('--manifest', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (replay(args.manifest, args.output) if args.command == 'replay'
                  else verify(args.result))
    except (OSError, ValueError, KeyError, TypeError, StopIteration, IndexError):
        print(json.dumps({'error': 'invalid input, existing output, or inconsistent ledger'}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
