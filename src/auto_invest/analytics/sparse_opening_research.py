"""Sealed research inputs and causal signals; no broker or live promotion path."""

from __future__ import annotations

import csv
import hashlib
import io
import json
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
        opening = self._openings[day]
        previous = [self._openings.get(d) for d in prior_days]
        if (len(previous) != 14 or not opening.complete
                or any(w is None or not w.complete for w in previous)):
            return None
        assert opening.ohlcv is not None
        mean_volume = sum(w.ohlcv[4] for w in previous if w and w.ohlcv)/14
        if mean_volume <= 0:
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
