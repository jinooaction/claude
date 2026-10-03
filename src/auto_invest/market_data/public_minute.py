"""Anonymous, pinned development-only source pilot. Never grants trading eligibility."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

REVISION = 'ef1551b11d8ee3e35c7521cf36deee155b43e77d'
REPOSITORY = 'ggaddam/OHLCV-1m'
HOSTS = frozenset({'huggingface.co', 'us.aws.cdn.hf.co'})
DEADLINE = 900
CHUNK = 1024 * 1024


class PilotError(ValueError):
    """Safe reason codes only; never include response text or signed addresses."""


@dataclass(frozen=True)
class SourceFile:
    month: str
    size: int
    sha256: str

    @property
    def name(self) -> str:
        return f'ohlcv_{self.month}.parquet'

    @property
    def url(self) -> str:
        return f'https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/data/{self.name}'


SOURCES = (
    SourceFile('2014-01', 256575689,
               '55925f7870effd4cad312f365133a7f405915d88130038791f28b6f6e5142871'),
    SourceFile('2019-12', 257874677,
               '6f7a8b521cd70c41ebf5296d9ee1920f8c41ccd6e376626e18798438471c3e1e'),
)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PilotError(code)


def safe_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == 'https' and parts.hostname in HOSTS and not parts.username
                 and not parts.password and parts.port in (None, 443) and not parts.fragment)
    except ValueError:
        valid = False
    require(valid, 'UNSAFE_ADDRESS')
    return url


def fingerprint(path: Path) -> tuple[int, str]:
    require(path.is_file() and not path.is_symlink(), 'NOT_REGULAR_FILE')
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as handle:
        while chunk := handle.read(CHUNK):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def collect(directory: Path, *, sources: tuple[SourceFile, ...] = SOURCES,
            clock: Callable[[], float] = time.monotonic,
            sleep: Callable[[float], None] = time.sleep) -> list[dict]:
    """Whole-source authentication; callers cannot supply an arbitrary network address."""
    started = clock()
    directory.mkdir(parents=True, exist_ok=True)
    require(all(not (directory / s.name).exists() for s in sources), 'OUTPUT_EXISTS')
    result: list[dict] = []
    last = -float('inf')

    def remaining() -> float:
        value = DEADLINE - (clock() - started)
        require(value > 0, 'DEADLINE_EXCEEDED')
        return value

    with httpx.Client(follow_redirects=False, trust_env=False,
                      headers={'User-Agent': 'public-minute-research/207'}) as client:
        for source in sources:
            partial = directory / (source.name + '.part')
            for attempt in range(3):
                try:
                    url = source.url
                    digest, size = hashlib.sha256(), 0
                    for _redirect in range(5):
                        remaining()
                        sleep(max(0., 1. - (clock() - last)))
                        remaining()
                        client.cookies.clear()
                        last = clock()
                        with client.stream('GET', safe_url(url),
                                           timeout=min(30., remaining())) as response:
                            if response.status_code in (301, 302, 303, 307, 308):
                                location = response.headers.get('location', '')
                                require(bool(location), 'MISSING_REDIRECT')
                                url = safe_url(urljoin(url, location))
                                continue
                            if response.status_code == 429 or response.status_code >= 500:
                                raise httpx.TransportError('TRANSIENT_STATUS')
                            require(response.status_code == 200, 'SOURCE_RESPONSE_REJECTED')
                            require(response.headers.get('content-encoding', 'identity')
                                    == 'identity', 'ENCODING_REJECTED')
                            length = response.headers.get('content-length')
                            require(length is None or length == str(source.size),
                                    'SIZE_MISMATCH')
                            with partial.open('xb') as handle:
                                for chunk in response.iter_raw():
                                    remaining()
                                    size += len(chunk)
                                    require(size <= source.size, 'SIZE_MISMATCH')
                                    digest.update(chunk)
                                    handle.write(chunk)
                            require(size == source.size and digest.hexdigest() == source.sha256,
                                    'SOURCE_FINGERPRINT_MISMATCH')
                            partial.rename(directory / source.name)
                            result.append({'month': source.month, 'size': size,
                                           'sha256': digest.hexdigest()})
                            break
                    else:
                        raise PilotError('REDIRECT_LIMIT')
                    break
                except httpx.TransportError:
                    partial.unlink(missing_ok=True)
                    if attempt == 2:
                        raise PilotError('TRANSIENT_ATTEMPTS_EXHAUSTED') from None
                    sleep(2. ** (attempt + 1))
                    remaining()
                except Exception:
                    partial.unlink(missing_ok=True)
                    raise
    return result


def diagnose(path: Path, month: str) -> dict:
    """Quality only, no prices/returns in the output. Whole raw file remains unchanged."""
    import duckdb
    import exchange_calendars as calendars
    import pandas as pd

    require(month in {s.month for s in SOURCES}, 'DEVELOPMENT_MONTH_REQUIRED')
    fingerprint(path)
    first = pd.Timestamp(month + '-01')
    end = first + pd.offsets.MonthEnd(1)
    calendar = calendars.get_calendar('XNYS', start=first, end=end)
    sessions = calendar.sessions
    schedule = pd.DataFrame([
        {'day': session.date(), 'opens': calendar.session_open(session),
         'closes': calendar.session_close(session),
         'expected': int((calendar.session_close(session) - calendar.session_open(session))
                         .total_seconds() / 60)}
        for session in sessions
    ])
    with duckdb.connect(config={'threads': 2, 'memory_limit': '2GB'}) as con:
        con.execute("SET TimeZone='UTC'")
        description = con.execute('DESCRIBE SELECT * FROM read_parquet(?)', [str(path)]).fetchall()
        require([(r[0], r[1]) for r in description] == [
            ('timestamp', 'TIMESTAMP WITH TIME ZONE'), ('open', 'DOUBLE'), ('high', 'DOUBLE'),
            ('low', 'DOUBLE'), ('close', 'DOUBLE'), ('volume', 'DOUBLE'), ('ticker', 'VARCHAR'),
        ], 'SCHEMA_REJECTED')
        con.from_parquet(str(path)).create_view('bars')
        con.register('schedule', schedule)
        fields = ['rows', 'null_rows', 'invalid_month', 'invalid_minute', 'invalid_symbol',
                  'invalid_price', 'invalid_volume']
        values = con.execute("""
            SELECT count(*), count_if(timestamp IS NULL OR ticker IS NULL OR open IS NULL
                OR high IS NULL OR low IS NULL OR close IS NULL OR volume IS NULL),
              count_if(strftime(timestamp AT TIME ZONE 'America/New_York','%Y-%m') != ?),
              count_if(timestamp != date_trunc('minute', timestamp)),
              count_if(ticker IS NULL OR NOT regexp_full_match(ticker,'[A-Z][A-Z0-9.]{0,14}')),
              count_if(NOT isfinite(open) OR NOT isfinite(high) OR NOT isfinite(low)
                OR NOT isfinite(close) OR least(open,high,low,close) <= 0 OR low > high
                OR open < low OR open > high OR close < low OR close > high),
              count_if(NOT isfinite(volume) OR volume < 0 OR floor(volume) != volume)
            FROM bars
        """, [month]).fetchone()
        result = dict(zip(fields, [int(x or 0) for x in values], strict=True))
        result['duplicate_rows'] = int(con.execute("""
            SELECT coalesce(sum(n-1),0) FROM
            (SELECT count(*) n FROM bars GROUP BY ticker,timestamp HAVING count(*)>1)
        """).fetchone()[0])
        con.execute("""CREATE TEMP TABLE counts AS
            SELECT ticker, day, expected, count(*) AS rows,
                   count(DISTINCT date_trunc('minute', timestamp)) AS minutes
            FROM bars JOIN schedule ON timestamp >= opens AND timestamp < closes
            WHERE regexp_full_match(ticker,'[A-Z][A-Z0-9.]{0,14}')
            GROUP BY ticker,day,expected
        """)
        result['regular_rows'] = int(con.execute(
            'SELECT coalesce(sum(rows),0) FROM counts').fetchone()[0])
        result['extended_rows'] = result['rows'] - result['regular_rows']
        symbols = con.execute("""
            WITH symbols AS (SELECT DISTINCT ticker FROM bars
                WHERE regexp_full_match(ticker,'[A-Z][A-Z0-9.]{0,14}'))
            SELECT symbols.ticker, coalesce(sum(counts.rows),0), count(counts.day),
              count_if(minutes=expected),
              (SELECT sum(expected) FROM schedule)-coalesce(sum(minutes),0)
            FROM symbols LEFT JOIN counts USING(ticker) GROUP BY symbols.ticker
            ORDER BY symbols.ticker
        """).fetchall()
        result['symbols'] = [dict(zip(
            ['symbol', 'regular_rows', 'observed_sessions', 'complete_sessions',
             'missing_regular_minutes'], [s[0], *[int(v or 0) for v in s[1:]]], strict=True))
            for s in symbols]
        result['calendar_sessions'] = len(sessions)
        result['regular_coverage_complete'] = bool(symbols) and all(
            s['missing_regular_minutes'] == 0 for s in result['symbols'])
        by_symbol = {s['symbol']: s for s in result['symbols']}
        result['runtime_universe_coverage'] = {
            symbol: by_symbol.get(symbol, {'symbol': symbol, 'regular_rows': 0,
                'observed_sessions': 0, 'complete_sessions': 0,
                'missing_regular_minutes': int(schedule['expected'].sum())})
            for symbol in ('SPY', 'QQQ', 'IWM', 'TLT', 'GLD')}
        result['availability_lag_seconds'] = 60
        result['month_basis'] = 'America/New_York'
        result['quality_accepted'] = result['regular_rows'] > 0 and all(
            result[key] == 0 for key in fields[1:] + ['duplicate_rows'])
        result['point_in_time_universe_verified'] = False
        return result
