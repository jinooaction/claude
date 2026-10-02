"""Offline development-only price diagnostic for fixed BLS announcement dates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

ET = ZoneInfo('America/New_York')
CONTRACT = (
    Path(__file__).resolve().parents[1]
    / 'specs/203-macro-release-price/contracts/preregistration.json'
)
PREREGISTERED_CONTRACT_SHA256 = '7adfbd7dfe1d0acf89844e64cae59fe78275977560179dc3011a0f8d10e7a3f1'
CALENDAR_FILES = {
    'hf_calendar_api_json': 'hf-calendar-api-export.json',
    'hf_calendar_parquet': 'hf-calendar.parquet',
    'alfred_cpi_dates': 'alfred-cpi-dates.txt',
    'alfred_employment_dates': 'alfred-employment-dates.txt',
}
CLOCKS = {'signal': (9, 45), 'entry': (9, 55), 'exit': (15, 55)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _source_path(directory: Path, name: str) -> Path:
    if Path(name).name != name:
        raise ValueError('unsafe source filename')
    return directory / name


def load_inputs(calendar_dir: Path, bars_dir: Path) -> tuple[dict, list[dict], dict, dict]:
    if sha256_file(CONTRACT) != PREREGISTERED_CONTRACT_SHA256:
        raise ValueError('preregistration SHA-256 mismatch')
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    if (
        contract['family_id'] != 'bls-release-follow-through-long-v1'
        or contract['candidate_count'] != 1
        or contract['minimum_prior_trials'] < 32
        or contract['safety']['orders_submitted'] != 0
        or contract['safety']['live_eligible']
        or contract['safety']['promotion_allowed']
    ):
        raise ValueError('unexpected preregistration')
    for key, name in CALENDAR_FILES.items():
        if sha256_file(_source_path(calendar_dir, name)) != contract['source_sha256'][key]:
            raise ValueError(f'{key} SHA-256 mismatch')
    manifest_path = bars_dir / 'manifest.json'
    if sha256_file(manifest_path) != contract['source_sha256']['price_manifest']:
        raise ValueError('price manifest SHA-256 mismatch')
    rows = json.loads((calendar_dir / CALENDAR_FILES['hf_calendar_api_json']).read_text())
    if not isinstance(rows, list) or len(rows) != 898:
        raise ValueError('unexpected calendar row count')
    dates = {}
    for family, key in (('CPI', 'alfred_cpi_dates'), ('EMPLOYMENT', 'alfred_employment_dates')):
        raw = (calendar_dir / CALENDAR_FILES[key]).read_text(encoding='utf-8')
        release_name = 'Consumer Price Index' if family == 'CPI' else 'Employment Situation'
        if f'Release: {release_name}' not in raw:
            raise ValueError(f'{family}: wrong ALFRED release')
        dates[family] = set(re.findall(r'(?m)^20\d{2}-\d{2}-\d{2}$', raw))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (
        manifest['dataset_id'] != 'hf-pitrading-coverage-frozen-20130823-20200306'
        or manifest['sessions'] != 1645
        or set(manifest['files']) != set(contract['universe'])
        or manifest['synthetic']
    ):
        raise ValueError('unexpected price manifest')
    return contract, rows, dates, manifest


def select_events(
    rows: list[dict], official_dates: dict[str, set[str]], contract: dict, calendar: object
) -> tuple[list[dict], dict[str, int]]:
    excluded: Counter[str] = Counter()
    selected = []
    seen = set()
    first, last = contract['development_sessions']
    for row in rows:
        family = row['release_family']
        if family not in contract['allowed_release_families']:
            excluded['other_family'] += 1
            continue
        day = row['scheduled_date_et']
        if (
            row['scheduled_time_et'] != contract['event_clock_et']
            or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', day)
            or row['reference_period'] is None
            or not re.fullmatch(r'20\d{2}-\d{2}', str(row['reference_period']))
        ):
            excluded['nonstandard_clock_or_identity'] += 1
            continue
        if day not in official_dates[family]:
            excluded['not_in_official_dates'] += 1
            continue
        source = urlparse(row['source_url'])
        if source.scheme != 'https' or source.netloc != 'www.bls.gov':
            raise ValueError('unexpected announcement source URL')
        when = datetime.fromisoformat(row['scheduled_at'].replace('Z', '+00:00'))
        local = when.astimezone(ET)
        if local.date().isoformat() != day or local.time() != time(8, 30):
            raise ValueError('announcement timezone mismatch')
        key = family, day
        if key in seen:
            raise ValueError('duplicate family/date announcement')
        seen.add(key)
        if not calendar.is_session(day):
            excluded['market_closed'] += 1
            continue
        if not first <= day <= last:
            excluded['outside_development'] += 1
            continue
        selected.append({'family': family, 'date_et': day, 'calendar_id': row['calendar_id']})
    selected.sort(key=lambda item: (item['date_et'], item['family']))
    if len({item['date_et'] for item in selected}) != len(selected):
        raise ValueError('two announcements on one session')
    return selected, dict(sorted(excluded.items()))


def _utc_stamp(day: str, hour: int, minute: int) -> str:
    local = datetime.combine(datetime.fromisoformat(day).date(), time(hour, minute), tzinfo=ET)
    return local.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def _decimal(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError('invalid price or volume') from None
    if not number.is_finite():
        raise ValueError('nonfinite price or volume')
    return number


def observe_symbol(
    path: Path, symbol: str, dates: set[str], calendar: object, expected_sha: str,
    expected_rows: int,
) -> dict[str, dict]:
    wanted: dict[str, list[tuple[str, str]]] = {}
    for day in dates:
        previous = calendar.previous_session(day)
        prior_stamp = (calendar.session_close(previous) - timedelta(minutes=5)).strftime(
            '%Y-%m-%dT%H:%M:%SZ'
        )
        wanted.setdefault(prior_stamp, []).append((day, 'previous'))
        for name, (hour, minute) in CLOCKS.items():
            wanted.setdefault(_utc_stamp(day, hour, minute), []).append((day, name))
    observed: dict[str, dict] = {day: {} for day in dates}
    digest = hashlib.sha256()
    row_count = 0
    prior_stamp = ''
    with path.open('rb') as handle:
        header = handle.readline()
        digest.update(header)
        if header.strip() != b'timestamp_utc,symbol,open,high,low,close,volume':
            raise ValueError(f'{symbol}: unexpected CSV header')
        for raw in handle:
            digest.update(raw)
            parts = raw.rstrip(b'\r\n').split(b',')
            if len(parts) != 7 or parts[1].decode('ascii') != symbol:
                raise ValueError(f'{symbol}: malformed row')
            stamp = parts[0].decode('ascii')
            if stamp <= prior_stamp:
                raise ValueError(f'{symbol}: duplicate or unordered timestamp')
            prior_stamp = stamp
            row_count += 1
            for day, name in wanted.get(stamp, ()):
                if name in observed[day]:
                    raise ValueError(f'{symbol}: duplicate observation')
                observed[day][name] = {
                    'open': parts[2].decode('ascii'),
                    'close': parts[5].decode('ascii'),
                    'volume': parts[6].decode('ascii'),
                }
    if digest.hexdigest() != expected_sha or row_count != expected_rows:
        raise ValueError(f'{symbol}: price source mismatch')
    return observed


def score_pair(event: dict, symbol: str, observed: dict, costs: dict) -> dict:
    result = {**event, 'symbol': symbol}
    missing = [name for name in ('previous', 'signal', 'entry', 'exit') if not observed.get(name)]
    if missing:
        result.update(status='MISSING_OBSERVATION', missing=missing)
        return result
    previous = _decimal(observed['previous']['close'])
    signal = _decimal(observed['signal']['close'])
    entry = _decimal(observed['entry']['open'])
    exit_price = _decimal(observed['exit']['open'])
    volumes = [_decimal(observed[name]['volume']) for name in ('signal', 'entry', 'exit')]
    if min(previous, signal, entry, exit_price, *volumes) <= 0:
        result['status'] = 'INVALID_PRICE_OR_VOLUME'
        return result
    if signal <= previous:
        result['status'] = 'NO_LONG_SIGNAL'
        return result
    result['status'] = 'REFERENCE_PAIR'
    result['prices'] = {
        'previous_close': str(previous), 'signal_close': str(signal),
        'entry_open': str(entry), 'exit_open': str(exit_price),
    }
    result['returns'] = {'gross': str(exit_price / entry - 1)}
    for label, bps in costs.items():
        side = Decimal(bps) / Decimal(10000)
        result['returns'][label] = str(exit_price * (1 - side) / (entry * (1 + side)) - 1)
    return result


def run(calendar_dir: Path, bars_dir: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    contract, rows, official_dates, manifest = load_inputs(calendar_dir, bars_dir)
    calendar = xcals.get_calendar('XNYS')
    events, excluded = select_events(rows, official_dates, contract, calendar)
    dates = {item['date_et'] for item in events}
    observations = {}
    for symbol in contract['universe']:
        info = manifest['files'][symbol]
        name = info['path']
        if name != f'{symbol}.csv' or Path(name).name != name:
            raise ValueError(f'{symbol}: unsafe price path')
        expected = info['sha256'].removeprefix('sha256:')
        observations[symbol] = observe_symbol(
            bars_dir / name, symbol, dates, calendar, expected, info['rows']
        )
    pairs = [
        score_pair(
            event, symbol, observations[symbol][event['date_et']],
            contract['costs_per_side_bps'],
        )
        for event in events for symbol in contract['universe']
    ]
    reference = [item for item in pairs if item['status'] == 'REFERENCE_PAIR']
    means = {}
    if reference:
        for key in ('gross', 'base', 'stress'):
            total = sum(Decimal(item['returns'][key]) for item in reference)
            means[key] = str(total / len(reference))
    if len(reference) < contract['minimum_base_cost_closed_trades']:
        decision = 'INSUFFICIENT_EVIDENCE'
    elif Decimal(means['base']) <= 0 or Decimal(means['stress']) <= 0:
        decision = 'REJECTED_DEVELOPMENT'
    else:
        decision = 'POSITIVE_DEVELOPMENT_DIAGNOSTIC_ONLY'
    payload = {
        'schema_version': 1,
        'family_id': contract['family_id'],
        'preregistration_sha256': sha256_file(CONTRACT),
        'source_sha256': contract['source_sha256'],
        'development_sessions': contract['development_sessions'],
        'blocked_and_final_returns_opened': False,
        'event_count': len(events),
        'event_family_count': dict(sorted(Counter(e['family'] for e in events).items())),
        'excluded_event_count': excluded,
        'pair_status_count': dict(sorted(Counter(p['status'] for p in pairs).items())),
        'reference_pair_count': len(reference),
        'equal_weight_mean_returns': means,
        'decision': decision,
        'safety': contract['safety'],
        'pairs': pairs,
    }
    with output.open('x', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        handle.write('\n')
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calendar-dir', type=Path, required=True)
    parser.add_argument('--bars-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.calendar_dir, args.bars_dir, args.output)
    print(json.dumps({
        'decision': result['decision'],
        'event_count': result['event_count'],
        'reference_pair_count': result['reference_pair_count'],
        'equal_weight_mean_returns': result['equal_weight_mean_returns'],
        'output_sha256': sha256_file(args.output),
    }, sort_keys=True))


if __name__ == '__main__':
    main()
