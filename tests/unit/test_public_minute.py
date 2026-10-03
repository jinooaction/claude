from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta

import duckdb
import pytest
import respx

from auto_invest.market_data.public_minute import (
    SOURCES,
    PilotError,
    collect,
    diagnose,
    safe_url,
)


@pytest.mark.parametrize('url', [
    'http://huggingface.co/x', 'https://attacker.test/x',
    'https://huggingface.co.attacker.test/x', 'https://user@huggingface.co/x',
    'https://huggingface.co:444/x', 'https://127.0.0.1/x',
])
def test_unsafe_redirect_is_rejected(url):
    with pytest.raises(PilotError):
        safe_url(url)


def test_fixed_sources_exclude_holdout():
    assert [s.month for s in SOURCES] == ['2014-01', '2019-12']
    assert sum(s.size for s in SOURCES) == 514450366
    assert all('ef1551b11d8ee3e35c7521cf36deee155b43e77d' in s.url for s in SOURCES)


@respx.mock
def test_whole_hash_verified_not_footer(tmp_path):
    raw = b'PAR1tiny-fixturePAR1'
    source = replace(SOURCES[0], size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    respx.get(source.url).respond(302, headers={'location': 'https://us.aws.cdn.hf.co/fixture'})
    respx.get('https://us.aws.cdn.hf.co/fixture').respond(200, content=raw)
    result = collect(tmp_path, sources=(source,), sleep=lambda _: None)
    assert result[0]['sha256'] == source.sha256
    assert (tmp_path / source.name).read_bytes() == raw


@pytest.mark.parametrize('status', [206, 403, 404, 500, 429])
@respx.mock
def test_partial_or_failed_response_never_becomes_source(tmp_path, status):
    source = replace(SOURCES[0], size=3, sha256=hashlib.sha256(b'abc').hexdigest())
    route = respx.get(source.url).respond(status, content=b'abc')
    with pytest.raises(PilotError):
        collect(tmp_path, sources=(source,), sleep=lambda _: None)
    assert route.call_count == (3 if status in (429, 500) else 1)
    assert not (tmp_path / source.name).exists()
    assert not list(tmp_path.glob('*.part'))


@pytest.mark.parametrize('raw', [b'a', b'abcd', b'bad'])
@respx.mock
def test_size_and_hash_mismatch_fail_closed(tmp_path, raw):
    source = replace(SOURCES[0], size=3, sha256=hashlib.sha256(b'abc').hexdigest())
    respx.get(source.url).respond(200, content=raw)
    with pytest.raises(PilotError):
        collect(tmp_path, sources=(source,), sleep=lambda _: None)
    assert not (tmp_path / source.name).exists()


@respx.mock
def test_untrusted_signed_url_not_in_error(tmp_path):
    source = SOURCES[0]
    respx.get(source.url).respond(302, headers={'location': 'https://evil.test/?secret=private'})
    with pytest.raises(PilotError) as caught:
        collect(tmp_path, sources=(source,), sleep=lambda _: None)
    assert 'private' not in str(caught.value) and 'evil.test' not in str(caught.value)


@respx.mock
def test_deadline_and_existing_output_do_not_request(tmp_path):
    ticks = iter([0.0, 1000.0])
    with pytest.raises(PilotError):
        collect(tmp_path, sources=SOURCES, clock=lambda: next(ticks), sleep=lambda _: None)
    assert not respx.calls
    (tmp_path / SOURCES[0].name).write_bytes(b'existing')
    with pytest.raises(PilotError):
        collect(tmp_path, sources=SOURCES, sleep=lambda _: None)
    assert not respx.calls


def parquet(tmp_path, rows, *, timezone=True):
    path = tmp_path / 'tiny.parquet'
    with duckdb.connect() as con:
        con.execute('CREATE TABLE bars(timestamp TIMESTAMPTZ, open DOUBLE, high DOUBLE, '
                    'low DOUBLE, close DOUBLE, volume DOUBLE, ticker VARCHAR)')
        con.executemany('INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?)', rows)
        if not timezone:
            con.execute('ALTER TABLE bars ALTER timestamp TYPE TIMESTAMP')
        con.execute('COPY bars TO ? (FORMAT PARQUET)', [str(path)])
    return path


def row(timestamp='2014-01-02T14:30:00Z', **changes):
    data = dict(timestamp=timestamp, open=10., high=11., low=9., close=10., volume=100.,
                ticker='SPY')
    data.update(changes)
    return tuple(data.values())


def test_exchange_month_preserves_next_utc_month(tmp_path):
    path = parquet(tmp_path, [row(), row('2014-02-01T00:59:00Z')])
    result = diagnose(path, '2014-01')
    assert result['invalid_month'] == 0
    assert result['regular_rows'] == 1 and result['extended_rows'] == 1
    assert result['availability_lag_seconds'] == 60
    assert result['symbols'][0]['missing_regular_minutes'] > 0
    assert result['symbols'][0]['complete_sessions'] == 0


@pytest.mark.parametrize(('change', 'field'), [
    ({'timestamp': '2014-02-03T14:30:00Z'}, 'invalid_month'),
    ({'timestamp': '2014-01-02T14:30:01Z'}, 'invalid_minute'),
    ({'timestamp': None}, 'null_rows'),
    ({'open': float('nan')}, 'invalid_price'),
    ({'low': 12.}, 'invalid_price'),
    ({'open': 0.}, 'invalid_price'),
    ({'volume': 1.5}, 'invalid_volume'),
    ({'volume': -1.}, 'invalid_volume'),
    ({'ticker': 'private@example.test'}, 'invalid_symbol'),
])
def test_quality_counterexamples(tmp_path, change, field):
    result = diagnose(parquet(tmp_path, [row(**change)]), '2014-01')
    assert result[field] > 0
    assert not result['quality_accepted']
    assert 'private@example.test' not in str(result)


def test_duplicate_and_timezone_are_not_accepted(tmp_path):
    result = diagnose(parquet(tmp_path, [row(), row()]), '2014-01')
    assert result['duplicate_rows'] == 1
    assert not result['quality_accepted']
    path = tmp_path / 'tiny.parquet'
    path.unlink()
    with pytest.raises(PilotError):
        diagnose(parquet(tmp_path, [row()], timezone=False), '2014-01')


def test_one_complete_session_does_not_claim_whole_month_or_strategy(tmp_path):
    start = datetime.fromisoformat('2014-01-02T14:30:00+00:00')
    result = diagnose(parquet(tmp_path, [row((start + timedelta(minutes=i)).isoformat())
                                      for i in range(390)]), '2014-01')
    assert result['quality_accepted']
    assert result['symbols'][0]['complete_sessions'] == 1
    assert not result['regular_coverage_complete']
    assert result['runtime_universe_coverage']['QQQ']['regular_rows'] == 0
    assert not result['point_in_time_universe_verified']
