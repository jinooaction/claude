"""Sparse historical observations, never orders, fills, or strategy eligibility."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import MappingProxyType

import exchange_calendars as xc

MINUTE = timedelta(minutes=1)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware datetime required')
    return value.astimezone(UTC)


@dataclass(frozen=True)
class Source:
    symbol: str
    sha256: str
    provider: str
    adjustment: str
    issuer_lineage_status: str

    def __post_init__(self):
        if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,19}', self.symbol):
            raise ValueError('invalid symbol')
        if not re.fullmatch(r'[0-9a-f]{64}', self.sha256):
            raise ValueError('invalid SHA256')
        if not self.provider.strip() or not self.adjustment.strip():
            raise ValueError('source semantics required')
        if self.issuer_lineage_status not in ('verified', 'unverified'):
            raise ValueError('explicit lineage status required')


@dataclass(frozen=True)
class Minute:
    start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime
    observed_count: int
    missing: tuple[datetime, ...]
    pending: tuple[datetime, ...]
    ohlcv: tuple[float, float, float, float, float] | None

    @property
    def complete(self) -> bool:
        return self.ohlcv is not None


@dataclass(frozen=True)
class PriceObservation:
    requested_at: datetime
    observed_at: datetime | None
    available_at: datetime | None
    reference_open: float | None
    status: str
    fill_verified: bool = False
    capacity_unknown: bool = True


class ObservedSeries:
    """One fixed symbol/scope. Whole-file validation is separate from as-of queries."""

    def __init__(self, source: Source, start: date, end: date, rows: Iterable[Minute]):
        if type(start) is not date or type(end) is not date or start > end:
            raise ValueError('invalid date scope')
        self.source = source
        self.start, self.end = start, end
        calendar = xc.get_calendar('XNYS', start=start-timedelta(days=60),
                                   end=end+timedelta(days=1))
        sessions = calendar.sessions_in_range(str(start), str(end))
        if len(sessions) == 0:
            raise ValueError('scope has no trading sessions')
        self.sessions = tuple(s.date() for s in sessions)
        self._bounds = MappingProxyType({
            s.date(): (calendar.session_open(s).to_pydatetime(),
                       calendar.session_close(s).to_pydatetime()) for s in sessions
        })
        indexed = {}
        previous = None
        for row in rows:
            stamp = _utc(row.start)
            bounds = self._bounds.get(stamp.date())
            if (stamp.second or stamp.microsecond or bounds is None
                    or not bounds[0] <= stamp < bounds[1]):
                raise ValueError('observation outside regular minute grid')
            if previous is not None and stamp <= previous:
                raise ValueError('duplicate or unordered observation')
            values = (row.open, row.high, row.low, row.close, row.volume)
            if any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) for v in values):
                raise ValueError('non-finite observation')
            if (min(values[:4]) <= 0 or row.volume < 0
                    or row.low > min(row.open, row.close)
                    or row.high < max(row.open, row.close)):
                raise ValueError('invalid OHLCV')
            indexed[stamp] = Minute(stamp, *values)
            previous = stamp
        self._rows = MappingProxyType(indexed)
        self._times = tuple(indexed)

    def bounds(self, day: date) -> tuple[datetime, datetime]:
        if day not in self._bounds:
            raise ValueError('session outside fixed scope')
        return self._bounds[day]

    def window(self, day: date, offset: int, length: int, as_of: datetime) -> Window:
        as_of = _utc(as_of)
        lo, hi = self.bounds(day)
        if type(offset) is not int or type(length) is not int or offset < 0 or length < 1:
            raise ValueError('positive integer window required')
        start, end = lo + offset*MINUTE, lo + (offset+length)*MINUTE
        if end > hi:
            raise ValueError('window extends past session close')
        missing, pending, observed = [], [], []
        for i in range(length):
            stamp = start + i*MINUTE
            if stamp + MINUTE > as_of:
                pending.append(stamp)
            elif stamp not in self._rows:
                missing.append(stamp)
            else:
                observed.append(self._rows[stamp])
        ohlcv = None
        if not missing and not pending:
            ohlcv = (observed[0].open, max(r.high for r in observed),
                     min(r.low for r in observed), observed[-1].close,
                     math.fsum(r.volume for r in observed))
        return Window(start, end, len(observed), tuple(missing), tuple(pending), ohlcv)

    def prior_windows(self, day: date, count: int, length: int | None,
                      as_of: datetime) -> tuple[Window, ...]:
        """None length requests each full regular session; integers request opening minutes."""
        self.bounds(day)
        if type(count) is not int or count < 1:
            raise ValueError('positive history count required')
        index = self.sessions.index(day)
        if index < count:
            raise ValueError('insufficient fixed-scope calendar history')
        return tuple(self.window(d, 0, length if length is not None else
                                 int((self.bounds(d)[1]-self.bounds(d)[0])/MINUTE), as_of)
                     for d in self.sessions[index-count:index])

    def exact_price(self, requested_at: datetime, as_of: datetime) -> PriceObservation:
        requested_at, as_of = _utc(requested_at), _utc(as_of)
        lo, hi = self.bounds(requested_at.date())
        if (requested_at.second or requested_at.microsecond
                or not lo <= requested_at < hi):
            raise ValueError('requested minute outside regular session')
        if requested_at + MINUTE > as_of:
            return PriceObservation(requested_at, None, None, None, 'NOT_YET_OBSERVABLE')
        row = self._rows.get(requested_at)
        if row is None:
            return PriceObservation(requested_at, None, None, None, 'MISSING')
        if row.volume == 0:
            return PriceObservation(requested_at, requested_at, requested_at+MINUTE,
                                    None, 'ZERO_VOLUME')
        return PriceObservation(requested_at, requested_at, requested_at+MINUTE,
                                row.open, 'EXACT')

    def next_price(self, requested_at: datetime, as_of: datetime) -> PriceObservation:
        """Strictly later completed observation; never a deferred fill instruction."""
        requested_at, as_of = _utc(requested_at), _utc(as_of)
        initial = self.exact_price(requested_at, as_of)
        if initial.status == 'NOT_YET_OBSERVABLE':
            return initial
        for stamp in self._times[bisect_right(self._times, requested_at):]:
            if stamp + MINUTE > as_of:
                break
            row = self._rows[stamp]
            if row.volume > 0:
                return PriceObservation(requested_at, stamp, stamp+MINUTE, row.open, 'LATER')
        return PriceObservation(requested_at, None, None, None, 'MISSING')

    def audit(self) -> dict:
        """Retrospective coverage only; never use day completeness to select trades."""
        counts = {}
        for stamp in self._times:
            day = stamp.date()
            slot = int((stamp-self.bounds(day)[0])/(5*MINUTE))
            counts[day, slot] = counts.get((day, slot), 0)+1
        days = []
        for day in self.sessions:
            lo, hi = self.bounds(day)
            expected = int((hi-lo)/MINUTE)
            slots = [counts.get((day, i), 0) for i in range(expected//5)]
            observed = sum(slots)
            days.append({'session': str(day), 'expected_minutes': expected,
                         'observed_minutes': observed, 'missing_minutes': expected-observed,
                         'complete_five_minute_windows': sum(n == 5 for n in slots),
                         'complete_session': observed == expected})
        return {'symbol': self.source.symbol, 'source_sha256': self.source.sha256,
                'provider': self.source.provider, 'adjustment': self.source.adjustment,
                'issuer_lineage_status': self.source.issuer_lineage_status,
                'expected_sessions': len(days),
                'complete_sessions': sum(d['complete_session'] for d in days),
                'expected_minutes': sum(d['expected_minutes'] for d in days),
                'observed_minutes': len(self._rows),
                'missing_minutes': sum(d['missing_minutes'] for d in days),
                'sessions': days}


def audit_manifest(path: Path) -> dict:
    """Hash and parse the same bytes. Process one symbol at a time, preserving empty files."""
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    required = {'schema_version', 'symbols', 'start', 'end', 'calendar', 'files'}
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError('invalid manifest fields')
    if manifest['schema_version'] != 1 or isinstance(manifest['schema_version'], bool):
        raise ValueError('unsupported schema')
    if manifest['calendar'] != 'XNYS':
        raise ValueError('unsupported calendar')
    symbols = manifest['symbols']
    if (not isinstance(symbols, list) or not symbols
            or not all(isinstance(s, str) for s in symbols)
            or len(set(symbols)) != len(symbols)):
        raise ValueError('invalid fixed universe')
    files = manifest['files']
    if not isinstance(files, dict) or set(files) != set(symbols):
        raise ValueError('file universe mismatch')
    start, end = date.fromisoformat(manifest['start']), date.fromisoformat(manifest['end'])
    reports = []
    fields = ['timestamp_utc', 'symbol', 'open', 'high', 'low', 'close', 'volume']
    for symbol in symbols:
        info = files[symbol]
        if (not isinstance(info, dict) or set(info) !=
                {'path', 'sha256', 'provider', 'adjustment', 'issuer_lineage_status'}
                or not all(isinstance(v, str) and v for v in info.values())):
            raise ValueError('invalid source descriptor')
        source = Source(symbol, info['sha256'], info['provider'], info['adjustment'],
                        info['issuer_lineage_status'])
        raw = (path.parent/info['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source.sha256:
            raise ValueError('source fingerprint mismatch')
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8')))
        if reader.fieldnames != fields:
            raise ValueError('invalid minute CSV schema')

        def observations(rows=reader, expected_symbol=symbol):
            for row in rows:
                if (set(row) != set(fields) or row['symbol'] != expected_symbol
                        or None in row.values()):
                    raise ValueError('invalid minute CSV row')
                yield Minute(datetime.fromisoformat(row['timestamp_utc']),
                             *(float(row[k]) for k in fields[2:]))

        reports.append(ObservedSeries(source, start, end, observations()).audit())
    return {'schema_version': 1, 'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': {k: manifest[k] for k in ('symbols', 'start', 'end', 'calendar')},
            'files': reports, 'live_eligible': False, 'strategy_admitted': False,
            'orders_submitted': 0, 'generated_prices': 0}
