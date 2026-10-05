"""Development-only minute-to-runtime observation diagnostic; no trading authority."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from auto_invest.market_data.intraday import SYMBOLS, normalize
from auto_invest.market_data.public_minute import SOURCES, fingerprint, require

NY = ZoneInfo('America/New_York')
FIELDS = ('timestamp', 'open', 'high', 'low', 'close', 'volume', 'ticker')
EXACT_INTEGER_LIMIT = 2**53 - 1


def _minute(row: dict, month: str) -> None:
    stamp = row.get('timestamp')
    require(isinstance(stamp, datetime) and stamp.utcoffset() == timedelta(0)
            and stamp.second == 0 and stamp.microsecond == 0, 'MINUTE_TIME_REJECTED')
    require(stamp.astimezone(NY).strftime('%Y-%m') == month, 'MONTH_REJECTED')
    require(row.get('ticker') in SYMBOLS, 'SYMBOL_REJECTED')
    for field in ('open', 'high', 'low', 'close', 'volume'):
        value = row.get(field)
        require(type(value) in (int, float) and math.isfinite(value), 'NUMERIC_REJECTED')
    op, hi, lo, cl = (row[f] for f in ('open', 'high', 'low', 'close'))
    require(min(op, hi, lo, cl) > 0 and lo <= min(op, cl)
            and hi >= max(op, cl), 'PRICE_REJECTED')
    volume = row['volume']
    require(0 <= volume <= EXACT_INTEGER_LIMIT and int(volume) == volume, 'VOLUME_REJECTED')


def aggregate(rows: list[dict], start: datetime, *, observed: datetime | None = None):
    """Internal OHLCV only; require the entire five-minute interval plus modeled delay."""
    require(len(rows) == 5 and {r['timestamp'] for r in rows} == {
        start + timedelta(minutes=i) for i in range(5)}
        and len({r['ticker'] for r in rows}) == 1, 'BIN_INCOMPLETE')
    ordered = sorted(rows, key=lambda r: r['timestamp'])
    for row in ordered:
        _minute(row, start.astimezone(NY).strftime('%Y-%m'))
    ready = start + timedelta(minutes=6)
    require(observed is None or (observed.utcoffset() == timedelta(0) and observed >= ready),
            'NOT_YET_AVAILABLE')
    volume = sum(int(r['volume']) for r in ordered)
    require(volume <= EXACT_INTEGER_LIMIT, 'VOLUME_REJECTED')
    raw = {'t': start.isoformat(), 'o': ordered[0]['open'],
           'h': max(r['high'] for r in ordered), 'l': min(r['low'] for r in ordered),
           'c': ordered[-1]['close'], 'v': volume}
    bar = normalize(ordered[0]['ticker'], raw, ready if observed is None else observed)
    require(bar is not None, 'OUTSIDE_REGULAR_SESSION')
    return bar, ready


def bridge_rows(rows: list[dict], month: str) -> dict:
    import exchange_calendars as calendars
    import pandas as pd

    require(month in {s.month for s in SOURCES}, 'DEVELOPMENT_MONTH_REQUIRED')
    first = pd.Timestamp(month + '-01')
    calendar = calendars.get_calendar('XNYS', start=first, end=first + pd.offsets.MonthEnd(1))
    schedule = {}
    for session in calendar.sessions:
        op = calendar.session_open(session).to_pydatetime()
        cl = calendar.session_close(session).to_pydatetime()
        expected = int((cl - op).total_seconds() // 60)
        require(expected % 5 == 0, 'CALENDAR_ALIGNMENT_REJECTED')
        schedule[str(session.date())] = (op, cl, expected)
    buckets: dict = defaultdict(list)
    counts: dict = defaultdict(int)
    seen = set()
    excluded = 0
    for row in rows:
        _minute(row, month)
        key = (row['ticker'], row['timestamp'])
        require(key not in seen, 'DUPLICATE_MINUTE')
        seen.add(key)
        stamp = row['timestamp']
        day = str(stamp.astimezone(NY).date())
        bounds = schedule.get(day)
        if bounds is None or not bounds[0] <= stamp < bounds[1]:
            excluded += 1
            continue
        offset = int((stamp - bounds[0]).total_seconds() // 60)
        buckets[(day, row['ticker'], offset // 5)].append(row)
        counts[(day, row['ticker'])] += 1
    days = []
    complete = {s: [] for s in SYMBOLS}
    minute_complete = {s: [] for s in SYMBOLS}
    regular = {s: 0 for s in SYMBOLS}
    missing = {s: 0 for s in SYMBOLS}
    for day, (op, cl, expected) in schedule.items():
        states = {}
        for symbol in SYMBOLS:
            full, zero = 0, 0
            for index in range(expected // 5):
                minutes = buckets[(day, symbol, index)]
                if len(minutes) != 5:
                    continue
                if sum(int(r['volume']) for r in minutes) == 0:
                    # Structurally present but rejected by the runtime's positive-volume rule.
                    full += 1
                    zero += 1
                    continue
                aggregate(minutes, op + timedelta(minutes=index * 5))
                full += 1
            n = counts[(day, symbol)]
            regular[symbol] += n
            missing[symbol] += expected - n
            usable = full - zero
            valid = usable == expected // 5
            if n == expected:
                minute_complete[symbol].append(day)
            if valid:
                complete[symbol].append(day)
            states[symbol] = dict(expected_minutes=expected, expected_bins=expected // 5,
                                  observed_minutes=n, complete_bins=full,
                                  missing_bins=expected // 5 - full,
                                  zero_volume_bins=zero, usable_bins=usable,
                                  minute_complete_session=n == expected,
                                  complete_session=valid)
        days.append({'day': day, 'opens_at_utc': op.isoformat(), 'closes_at_utc': cl.isoformat(),
                     'last_modeled_available_at_utc': (cl + timedelta(seconds=60)).isoformat(),
                     'symbols': states})
    joint = sorted(set.intersection(*(set(complete[s]) for s in SYMBOLS)))
    return dict(month=month, calendar_sessions=len(schedule), excluded_rows=excluded,
                regular_minutes_by_symbol=regular, missing_minutes_by_symbol=missing,
                complete_sessions_by_symbol=complete, common_complete_sessions=joint,
                minute_complete_sessions_by_symbol=minute_complete,
                common_complete_minute_sessions=sorted(set.intersection(*(
                    set(minute_complete[s]) for s in SYMBOLS))),
                sessions=days, timestamp_interpretation='UNVERIFIED_OPEN_TIME_MODEL',
                timestamp_semantics_verified=False, availability_lag_seconds=60,
                publish_delay_measured=False, runtime_normalization_checked=True,
                provider_eligible=False, strategy_eligible=False, promotion_eligible=False,
                orders_submitted=0, returns_examined=False)


def analyse(path: Path, month: str) -> dict:
    """Read only the runtime symbols internally; the output contains no prices or volumes."""
    import duckdb

    fingerprint(path)
    with duckdb.connect(config={'threads': 2, 'memory_limit': '2GB'}) as con:
        con.execute("SET TimeZone='UTC'")
        description = con.execute('DESCRIBE SELECT * FROM read_parquet(?)', [str(path)]).fetchall()
        require([(r[0], r[1]) for r in description] == [
            ('timestamp', 'TIMESTAMP WITH TIME ZONE'), ('open', 'DOUBLE'), ('high', 'DOUBLE'),
            ('low', 'DOUBLE'), ('close', 'DOUBLE'), ('volume', 'DOUBLE'), ('ticker', 'VARCHAR'),
        ], 'SCHEMA_REJECTED')
        values = con.execute('SELECT epoch_us(timestamp), open, high, low, close, volume, ticker '
                             'FROM read_parquet(?) WHERE ticker IN (?, ?, ?, ?, ?)',
                             [str(path), *SYMBOLS]).fetchall()
    rows = []
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    for row in values:
        require(row[0] is not None, 'MINUTE_TIME_REJECTED')
        item = dict(zip(FIELDS, row, strict=True))
        item['timestamp'] = epoch + timedelta(microseconds=row[0])
        rows.append(item)
    return bridge_rows(rows, month)
