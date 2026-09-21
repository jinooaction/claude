"""Sealed research inputs and causal signals; no broker or live promotion path."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import tempfile
from contextlib import ExitStack, contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import exchange_calendars as xc

from auto_invest.analytics.observed_intraday_inputs import Minute, ObservedSeries, Source, Window

CONTRACT_SHA256 = 'd80a899952f84daa84bf62e821587fb59b3943d3b8863b98551691aec388279e'
INVENTORY_SHA256 = '8b36761ecb4a01a67a1e97aafbb9a6207def836cb1e025618fe0988c588c7c1f'
MINUTE = timedelta(minutes=1)
FIELDS = ['timestamp_utc', 'symbol', 'open', 'high', 'low', 'close', 'volume']


def sealed_contract(directory: Path) -> tuple[dict, dict]:
    values = []
    for name, expected in [('preregistration.json', CONTRACT_SHA256),
                           ('source-inventory.json', INVENTORY_SHA256)]:
        raw = (directory/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('sealed research contract changed')
        values.append(json.loads(raw))
    contract, inventory = values
    if set(contract['members']) != set(inventory):
        raise ValueError('sealed universe mismatch')
    return contract, inventory


def _rows(handle, symbol):
    reader = csv.DictReader(handle)
    if reader.fieldnames != FIELDS:
        raise ValueError('invalid minute CSV schema')
    previous = None
    for row in reader:
        if set(row) != set(FIELDS) or None in row.values() or row['symbol'] != symbol:
            raise ValueError('invalid minute CSV row')
        stamp = datetime.fromisoformat(row['timestamp_utc'])
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
            raise ValueError('UTC CSV timestamps required')
        stamp = stamp.astimezone(UTC)
        if previous is not None and stamp <= previous:
            raise ValueError('unordered or duplicate CSV rows')
        previous = stamp
        yield Minute(stamp, *(float(row[k]) for k in FIELDS[2:]))


@contextmanager
def research_inputs(manifest_path: Path, contract_directory: Path):
    """Hash immutable disk snapshots, then expose at most one session per symbol."""
    contract, inventory = sealed_contract(contract_directory)
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if (not isinstance(manifest, dict) or set(manifest) !=
            {'schema_version', 'symbols', 'start', 'end', 'calendar', 'files'}
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 2
            or manifest['calendar'] != 'XNYS'
            or manifest['start'] != contract['period']['first']
            or manifest['end'] != contract['period']['last']
            or not isinstance(manifest['symbols'], list)
            or not all(isinstance(s, str) for s in manifest['symbols'])
            or len(manifest['symbols']) != len(inventory)
            or set(manifest['symbols']) != set(inventory)
            or not isinstance(manifest['files'], dict)
            or set(manifest['files']) != set(inventory)):
        raise ValueError('manifest differs from sealed scope')
    calendar = xc.get_calendar('XNYS', start=manifest['start'], end=manifest['end'])
    sessions = tuple(s.date() for s in calendar.sessions)
    sources, streams = {}, {}
    with ExitStack() as stack:
        for symbol in sorted(inventory):
            info = manifest['files'][symbol]
            fields = {'path', 'sha256', 'original_sha256', 'file_symbol', 'provider',
                      'adjustment', 'issuer_lineage_status'}
            if (not isinstance(info, dict) or set(info) != fields
                    or not all(isinstance(v, str) and v for v in info.values())
                    or info['original_sha256'] != inventory[symbol]['sha256']
                    or info['file_symbol'] != inventory[symbol]['file_symbol']
                    or info['provider'] != 'hfdatalibrary-pitrading'
                    or info['adjustment'] != 'source-split-dividend-adjusted'
                    or info['issuer_lineage_status'] != 'unverified'):
                raise ValueError('source descriptor differs from sealed inventory')
            source = Source(symbol, info['sha256'], info['provider'], info['adjustment'],
                            info['issuer_lineage_status'])
            snapshot = stack.enter_context(tempfile.TemporaryFile())
            digest = hashlib.sha256()
            with (manifest_path.parent/info['path']).open('rb') as input_file:
                while chunk := input_file.read(1024*1024):
                    digest.update(chunk)
                    snapshot.write(chunk)
            if digest.hexdigest() != source.sha256:
                raise ValueError('CSV fingerprint mismatch')
            snapshot.seek(0)
            handle = stack.enter_context(io.TextIOWrapper(snapshot, encoding='utf-8', newline=''))
            sources[symbol] = source
            streams[symbol] = iter(_rows(handle, symbol))

        def days():
            upcoming = {symbol: next(rows, None) for symbol, rows in streams.items()}
            for day in sessions:
                current = {}
                for symbol in sorted(streams):
                    rows = []
                    while upcoming[symbol] is not None and upcoming[symbol].start.date() <= day:
                        row = upcoming[symbol]
                        if row.start.date() < day:
                            raise ValueError('CSV row outside fixed exchange sessions')
                        rows.append(row)
                        upcoming[symbol] = next(streams[symbol], None)
                    current[symbol] = ObservedSeries(sources[symbol], day, day, rows)
                yield day, current
            if any(row is not None for row in upcoming.values()):
                raise ValueError('CSV rows beyond fixed scope')

        yield {'manifest_sha256': hashlib.sha256(raw).hexdigest(),
               'contract': contract, 'sessions': sessions, 'days': days()}


class OpeningSignals:
    """One symbol's opening windows. Missing calendar days are never compressed."""

    def __init__(self, sessions: tuple[date, ...]):
        if not sessions or tuple(sorted(set(sessions))) != tuple(sessions):
            raise ValueError('ordered unique calendar sessions required')
        self.sessions = tuple(sessions)
        self._indices = {day: index for index, day in enumerate(sessions)}
        self._openings: dict[date, Window] = {}
        self._attempted: set[date] = set()
        self._source: Source | None = None
        self._last_seen: datetime | None = None
        self.input_unavailable: dict | None = None

    def entry(self, data: ObservedSeries, day: date, as_of: datetime) -> dict | None:
        if day not in self._indices:
            raise ValueError('day outside fixed calendar')
        if self._source is not None and data.source != self._source:
            raise ValueError('signal source changed')
        self._source = data.source
        lo, hi = data.bounds(day)
        if not lo <= as_of <= hi:
            raise ValueError('decision outside session')
        if self._last_seen is not None and as_of < self._last_seen:
            raise ValueError('decisions must be chronological')
        self._last_seen = as_of
        offset = (as_of-lo)/MINUTE
        if offset < 5:
            return None
        index = self._indices[day]
        self._openings.setdefault(day, data.window(day, 0, 5, as_of))
        prior_days = self.sessions[max(0, index-14):index]
        keep = set(prior_days) | {day}
        self._openings = {d: w for d, w in self._openings.items() if d in keep}
        if day in self._attempted or offset < 10 or offset > 60 or offset % 5:
            return None
        self.input_unavailable = None
        opening = self._openings[day]
        previous = [self._openings.get(d) for d in prior_days]
        if len(previous) != 14:
            self.input_unavailable = {'reason': 'WARMUP'}
            return None
        if not opening.complete:
            self.input_unavailable = {'reason': 'OPENING_MISSING'}
            return None
        missing = [d.isoformat() for d, w in zip(prior_days, previous, strict=True)
                   if w is None or not w.complete]
        if missing:
            self.input_unavailable = {'reason': 'LOOKBACK_MISSING', 'missing_sessions': missing}
            return None
        assert opening.ohlcv is not None
        mean_volume = sum(w.ohlcv[4] for w in previous if w and w.ohlcv)/14
        if mean_volume <= 0:
            self.input_unavailable = {'reason': 'ZERO_LOOKBACK_VOLUME'}
            return None
        o, high, low, close, volume = opening.ohlcv
        if close <= o or volume < 2*mean_volume:
            return None
        trigger = data.window(day, int(offset)-5, 5, as_of)
        if trigger.ohlcv is None or trigger.ohlcv[3] <= high:
            return None
        self._attempted.add(day)
        return {'decision_at': as_of.isoformat(), 'symbol': data.source.symbol,
                'signal_close': trigger.ohlcv[3], 'opening_low': low,
                'opening_high': high, 'relative_volume': volume/mean_volume}

    @staticmethod
    def exit_due(data: ObservedSeries, day: date, as_of: datetime,
                 opening_low: float) -> bool:
        lo, hi = data.bounds(day)
        if not lo <= as_of <= hi:
            raise ValueError('decision outside session')
        if as_of >= hi-5*MINUTE:
            return True
        offset = (as_of-lo)/MINUTE
        if offset < 5 or offset % 5:
            return False
        window = data.window(day, int(offset)-5, 5, as_of)
        return window.ohlcv is not None and window.ohlcv[3] <= opening_low


class ResearchAccount:
    """Cash-constrained reference ledger, never a broker execution account."""

    def __init__(self, cost_bps: int, event_sink=None):
        if type(cost_bps) is not int or cost_bps not in (31, 40):
            raise ValueError('sealed cost scenario required')
        self.rate = cost_bps/10000
        self.cash = 10000.0
        self.entries: dict[str, dict] = {}
        self.positions: dict[str, dict] = {}
        self.settlements: list[dict] = []
        self.events: list[dict] = []
        self._event_sink = event_sink
        self.event_count = 0
        self.minimum_cash = self.cash
        self.unobserved_references = 0
        self.input_unavailable_counts: dict[str, int] = {}
        self.closed_roundtrips = 0
        self.realized_profit = 0.0
        self._last_time: datetime | None = None

    @property
    def reserved(self):
        return sum(entry['reserved'] for entry in self.entries.values())

    def _time(self, stamp):
        if (stamp.tzinfo is None or stamp.utcoffset() != timedelta(0)
                or stamp.second or stamp.microsecond
                or (self._last_time is not None and stamp < self._last_time)):
            raise ValueError('chronological UTC minute required')

    def _record(self, kind, stamp, symbol=None, **details):
        self._last_time = stamp
        if self.cash < -1e-8 or self.reserved < -1e-8:
            raise ValueError('negative research cash or reservation')
        self.event_count += 1
        self.minimum_cash = min(self.minimum_cash, self.cash)
        if details.get('status') in ('MISSING', 'ZERO_VOLUME'):
            self.unobserved_references += 1
        if kind == 'INPUT_UNAVAILABLE':
            reason = details['reason']
            self.input_unavailable_counts[reason] = self.input_unavailable_counts.get(reason, 0)+1
        event = {'sequence': self.event_count, 'kind': kind, 'at': stamp.isoformat(),
                 'symbol': symbol, **details, 'cash_after': self.cash,
                 'reserved_after': self.reserved}
        if self._event_sink is None:
            self.events.append(event)
        else:
            self._event_sink(event)

    def reserve(self, symbol, stamp, signal_close, opening_low):
        self._time(stamp)
        if (not symbol or not all(math.isfinite(p) and p > 0
                                  for p in (signal_close, opening_low))):
            raise ValueError('positive finite signal prices required')
        reason = None
        if symbol in self.entries or symbol in self.positions:
            reason = 'SYMBOL_ACTIVE'
        elif any(p['exit_pending'] for p in self.positions.values()):
            reason = 'EXIT_PENDING'
        elif len(self.entries)+len(self.positions) >= 4:
            reason = 'POSITION_LIMIT'
        limit = signal_close*1.001
        room = 8000-self.reserved-sum(p['basis'] for p in self.positions.values())
        quantity = math.floor(max(0, min(2000, self.cash, room))/(limit*(1+self.rate)))
        if reason is None and quantity == 0:
            reason = 'INSUFFICIENT_CASH_OR_CAPACITY'
        if reason:
            self._record('ENTRY_REJECTED', stamp, symbol, reason=reason)
            return False
        reserved = quantity*limit*(1+self.rate)
        self.cash -= reserved
        self.entries[symbol] = {'at': stamp, 'limit': limit, 'quantity': quantity,
                                'reserved': reserved, 'opening_low': opening_low}
        self._record('ENTRY_RESERVED', stamp, symbol, quantity=quantity,
                     limit=limit, amount=reserved, opening_low=opening_low)
        return True

    def _observation(self, symbol, data, requested, as_of):
        self._time(as_of)
        if data.source.symbol != symbol:
            raise ValueError('observation symbol mismatch')
        if requested+MINUTE != as_of:
            raise ValueError('reference minute not yet observable or observed late')
        price = data.exact_price(requested, as_of)
        lo, _ = data.bounds(requested.date())
        window = data.window(requested.date(), int((requested-lo)/MINUTE), 1, as_of)
        volume = window.ohlcv[4] if window.ohlcv else 0
        return price.reference_open, math.floor(volume*.01), price.status

    def observe_entry(self, symbol, data, as_of):
        entry = self.entries[symbol]
        price, capacity, status = self._observation(symbol, data, entry['at'], as_of)
        quantity = (min(entry['quantity'], capacity)
                    if price is not None and price <= entry['limit'] else 0)
        basis = quantity*price*(1+self.rate) if quantity else 0.0
        self.cash += entry['reserved']-basis
        del self.entries[symbol]
        if quantity:
            self.positions[symbol] = {'quantity': quantity, 'basis': basis,
                                      'opening_low': entry['opening_low'],
                                      'exit_pending': False, 'exit_at': None,
                                      'last_reference': entry['at'].isoformat()}
        self._record('ENTRY_OBSERVED', as_of, symbol, quantity=quantity, price=price,
                     basis=basis, released=entry['reserved']-basis, status=status,
                     reference_capacity=capacity, source_sha256=data.source.sha256,
                     reference_at=entry['at'].isoformat())

    def request_exit(self, symbol, stamp):
        self._time(stamp)
        position = self.positions[symbol]
        if position['exit_pending']:
            self._last_time = stamp
            return
        position['exit_pending'] = True
        position['exit_at'] = stamp
        self._record('EXIT_REQUESTED', stamp, symbol, quantity=position['quantity'])

    def observe_exit(self, symbol, data, requested, as_of):
        position = self.positions[symbol]
        if (not position['exit_pending'] or requested < position['exit_at']
                or requested.isoformat() <= position['last_reference']):
            raise ValueError('invalid or repeated exit reference')
        price, capacity, status = self._observation(symbol, data, requested, as_of)
        quantity = min(position['quantity'], capacity) if price is not None else 0
        basis = position['basis']*quantity/position['quantity']
        proceeds = quantity*price*(1-self.rate) if quantity else 0.0
        due = None
        if quantity:
            calendar = xc.get_calendar('XNYS', start=requested.date()-timedelta(days=7),
                                       end=requested.date()+timedelta(days=15))
            # The requested calendar end may be a weekend beyond its last session.
            days = calendar.sessions[calendar.sessions.date >= requested.date()]
            due = calendar.session_open(days[2]).to_pydatetime()
            self.settlements.append({'due': due, 'amount': proceeds, 'symbol': symbol})
            self.realized_profit += proceeds-basis
            position['quantity'] -= quantity
            position['basis'] -= basis
        position['last_reference'] = requested.isoformat()
        if position['quantity'] == 0:
            self.closed_roundtrips += 1
            del self.positions[symbol]
        self._record('EXIT_OBSERVED', as_of, symbol, quantity=quantity, price=price,
                     basis=basis, proceeds=proceeds, due=due.isoformat() if due else None,
                     reference_capacity=capacity, source_sha256=data.source.sha256,
                     status=status, reference_at=requested.isoformat())

    def release_settlements(self, stamp):
        self._time(stamp)
        self._last_time = stamp
        released = [s for s in self.settlements if s['due'] <= stamp]
        self.settlements = [s for s in self.settlements if s['due'] > stamp]
        for settlement in sorted(released, key=lambda s: s['symbol']):
            self.cash += settlement['amount']
            self._record('SETTLEMENT_RELEASED', stamp, settlement['symbol'],
                         amount=settlement['amount'], due=settlement['due'].isoformat())

    def summary(self):
        unsettled = sum(s['amount'] for s in self.settlements)
        unresolved = bool(self.positions or self.entries)
        profit = None if unresolved else self.cash+unsettled-10000
        return {'cash': self.cash, 'reserved': self.reserved, 'unsettled': unsettled,
                'event_count': self.event_count, 'minimum_cash': self.minimum_cash,
                'unobserved_references': self.unobserved_references,
                'input_unavailable_counts': dict(self.input_unavailable_counts),
                'realized_profit': self.realized_profit, 'net_profit': profit,
                'net_return': None if profit is None else profit/10000,
                'closed_roundtrips': self.closed_roundtrips,
                'unclosed_quantity': sum(p['quantity'] for p in self.positions.values()),
                'positions': {s: {k: (v.isoformat() if isinstance(v, datetime) else v)
                                  for k, v in p.items()} for s, p in self.positions.items()},
                'live_eligible': False, 'promotion_allowed': False, 'fill_verified': False,
                'capacity_unknown': True, 'lineage_verified': False,
                'orders_submitted': 0, 'actual_capital_fraction': 0}


def replay_research(inputs: dict, event_sinks=None) -> dict:
    """Replay both cost cases on one clock and one causal stream of signals."""
    sessions = inputs['sessions']
    members = sorted(inputs['contract']['members'])
    signals = {s: OpeningSignals(sessions) for s in members}
    accounts = {name: ResearchAccount(cost, (event_sinks or {}).get(name))
                for name, cost in [('base', 31), ('stress', 40)]}
    count = 0
    for day, data in inputs['days']:
        if count >= len(sessions) or day != sessions[count] or set(data) != set(members):
            raise ValueError('replay requires every calendar session and original member')
        count += 1
        lo, hi = data[members[0]].bounds(day)
        if any(series.source.symbol != symbol or series.bounds(day) != (lo, hi)
               for symbol, series in data.items()):
            raise ValueError('replay source or exchange bounds mismatch')
        stamp = lo
        while stamp <= hi:
            for account in accounts.values():
                # Previous-minute outcomes become observable before new decisions.
                if stamp > lo:
                    pending = set(account.entries) | {
                        s for s, p in account.positions.items() if p['exit_pending']}
                    for symbol in sorted(pending):
                        if symbol in account.entries:
                            account.observe_entry(symbol, data[symbol], stamp)
                        else:
                            account.observe_exit(symbol, data[symbol], stamp-MINUTE, stamp)
                account.release_settlements(stamp)
            if stamp == hi:
                break
            offset = int((stamp-lo)/MINUTE)
            if offset % 5 == 0:
                for account in accounts.values():
                    for symbol in sorted(account.positions):
                        position = account.positions[symbol]
                        if (not position['exit_pending'] and OpeningSignals.exit_due(
                                data[symbol], day, stamp, position['opening_low'])):
                            account.request_exit(symbol, stamp)
                # Opening history is updated even when cash or pending exits bar entry.
                if 5 <= offset <= 60:
                    for symbol in members:
                        signal = signals[symbol].entry(data[symbol], day, stamp)
                        if offset == 10 and signals[symbol].input_unavailable:
                            for account in accounts.values():
                                account._record('INPUT_UNAVAILABLE', stamp, symbol,
                                                **signals[symbol].input_unavailable)
                        if signal is not None:
                            for account in accounts.values():
                                account._record('SIGNAL', stamp, **signal)
                                account.reserve(symbol, stamp, signal['signal_close'],
                                                signal['opening_low'])
            stamp += MINUTE
    if count != len(sessions):
        raise ValueError('replay ended before final calendar session')
    results = {name: account.summary() for name, account in accounts.items()}
    passed = (results['base']['closed_roundtrips'] >= 200 and all(
        result['net_profit'] is not None and result['net_profit'] > 0
        and result['unclosed_quantity'] == 0 for result in results.values()))
    return {'schema_version': 1, 'sessions': count, 'scenarios': results,
            'minimum_total_trials': 31,
            'limitations': ['Adjusted prices and minute volume are not execution certification.',
                            'DD corporate-action price lineage remains unverified.',
                            'UTX uses an unverified RTX file alias; price differences remain.',
                            'Previously observed development period; future holdout unopened.'],
            'status': ('INDEPENDENT_VALIDATION_REQUIRED' if passed else 'DEVELOPMENT_REJECTED'),
            'live_eligible': False, 'promotion_allowed': False,
            'orders_submitted': 0, 'actual_capital_fraction': 0}
