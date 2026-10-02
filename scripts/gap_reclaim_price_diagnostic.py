"""Fixed, offline opening-gap price screen. No executable trading authority."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from datetime import time as clock_time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'specs/204-gap-reclaim-price/contracts/preregistration.json'
CONTRACT_SHA = 'c70380833a8d954f68ffc9dc2b42e233da25eb57921edfc06c95416edf56655c'
LOCK = CONTRACT.parent / 'input-lock.json'
LOCK_SHA = '1a8e387d5dd1dd072da8ff2fc94165b32c6b6b1be752d0104a8cc073f3eca2cb'
HEADER = b'timestamp_utc,symbol,open,high,low,close,volume'
ET = ZoneInfo('America/New_York')
MAX_SLICE = 64 * 1024 * 1024


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read_contract():
    if digest(CONTRACT) != CONTRACT_SHA:
        raise ValueError('preregistration changed')
    return json.loads(CONTRACT.read_text())


def clock_plan(calendar, dates):
    result = {}
    for day in dates:
        prior = calendar.previous_session(day)
        previous_close = calendar.session_close(prior) - timedelta(minutes=1)
        clocks = {'previous': previous_close.isoformat().encode()}
        for name, hour, minute in (
            ('opening', 9, 30), ('signal', 9, 45), ('entry', 9, 47), ('exit', 15, 56),
        ):
            local = datetime.combine(datetime.fromisoformat(day).date(),
                                     clock_time(hour, minute), tzinfo=ET)
            clocks[name] = local.astimezone(UTC).isoformat().encode()
        result[day] = clocks
    return result


def allowed_stamps(calendar, plan):
    stamps = set()
    for day, clocks in plan.items():
        stamps.add(clocks['previous'])
        closing = calendar.session_close(day).isoformat().encode()
        stamps.update(stamp for name, stamp in clocks.items()
                      if name != 'previous' and stamp < closing)
    return stamps


def calendar_plan(contract):
    calendar = xcals.get_calendar('XNYS')
    dates = [x.date().isoformat() for x in calendar.sessions_in_range(
        *contract['development_sessions'])]
    return calendar, clock_plan(calendar, dates)


def parse_bar(parts):
    if len(parts) != 7:
        raise ValueError('malformed price row')
    try:
        opening, high, low, close, volume = map(Decimal, [x.decode('ascii') for x in parts[2:]])
    except (InvalidOperation, UnicodeError):
        raise ValueError('invalid price encoding') from None
    if (not all(x.is_finite() for x in (opening, high, low, close, volume))
            or not 0 < low <= min(opening, close) <= max(opening, close) <= high or volume < 0):
        raise ValueError('invalid OHLCV')
    return {'open': str(opening), 'close': str(close), 'volume': str(volume)}


def write_json(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, sort_keys=True, separators=(',', ':'))
        handle.write('\n')


def stage(manifest_path, bars_dir, output_dir, throttle_seconds):
    contract = read_contract()
    if not 0 <= throttle_seconds <= 1:
        raise ValueError('invalid preparation throttle')
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if digest(manifest_path) != contract['price_manifest_sha256']:
        raise ValueError('source manifest mismatch')
    manifest = json.loads(manifest_path.read_text())
    if (manifest['calendar'] != 'XNYS' or set(manifest['files']) !=
            set(contract['universe'] + contract['excluded_symbols'])):
        raise ValueError('unexpected source universe')
    calendar, plan = calendar_plan(contract)
    wanted = allowed_stamps(calendar, plan)
    output_dir.mkdir()
    (output_dir / 'source-manifest.json').write_bytes(manifest_path.read_bytes())
    index = {'schema_version': 1, 'contract_sha256': CONTRACT_SHA,
             'source_manifest_sha256': contract['price_manifest_sha256'], 'files': {}}
    for symbol, info in sorted(manifest['files'].items()):
        if (info['path'] != f'{symbol}.csv' or info['provider'] != 'hfdatalibrary-pitrading'
                or info['adjustment'] != 'source-split-dividend-adjusted'):
            raise ValueError('unexpected source identity')
        source = bars_dir / info['path']
        if source.is_symlink():
            raise ValueError('source symlink refused')
        selected = symbol in contract['universe']
        # All 30 full-file fingerprints are checked, including excluded lineage.
        output = output_dir / f'{symbol}.csv.gz'
        raw_digest, full_digest = hashlib.sha256(), hashlib.sha256()
        raw_size = count = budget = 0
        previous = None
        with source.open('rb') as handle:
            header = handle.readline()
            if header.rstrip(b'\r\n') != HEADER:
                raise ValueError('unexpected source header')
            full_digest.update(header)
            target = output.open('xb') if selected else None
            zipped = (gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0)
                      if target else None)
            try:
                if zipped:
                    zipped.write(header)
                    raw_digest.update(header)
                    raw_size += len(header)
                for row in handle:
                    full_digest.update(row)
                    budget += len(row)
                    parts = row.rstrip(b'\r\n').split(b',')
                    if len(parts) != 7 or parts[1] != symbol.encode():
                        raise ValueError('source row identity mismatch')
                    stamp = parts[0]
                    if previous is not None and stamp <= previous:
                        raise ValueError('duplicate or out-of-order source timestamp')
                    previous = stamp
                    if zipped and stamp in wanted:
                        parse_bar(parts)
                        zipped.write(row)
                        raw_digest.update(row)
                        raw_size += len(row)
                        count += 1
                        if raw_size > MAX_SLICE:
                            raise ValueError('slice size limit')
                    if budget >= 1024 * 1024:
                        time.sleep(throttle_seconds)
                        budget = 0
            finally:
                if zipped:
                    zipped.close()
                    target.close()
        if full_digest.hexdigest() != info['sha256']:
            raise ValueError(f'{symbol}: full source SHA mismatch')
        if selected:
            index['files'][symbol] = {
                'source_sha256': info['sha256'], 'gzip_sha256': digest(output),
                'raw_sha256': raw_digest.hexdigest(), 'raw_bytes': raw_size, 'rows': count,
            }
    # No completed index is published if any full source fails verification.
    write_json(output_dir / 'index.json', index)
    return {'prepared': True, 'index_sha256': digest(output_dir / 'index.json'),
            'symbols': len(index['files']), 'returns_computed': False}


def read_views(fixture, contract):
    if not LOCK.exists() or digest(LOCK) != LOCK_SHA:
        raise ValueError('input not locked before score')
    lock = json.loads(LOCK.read_text())
    if digest(fixture / 'index.json') != lock['index_sha256']:
        raise ValueError('slice index mismatch')
    index = json.loads((fixture / 'index.json').read_text())
    if (index['contract_sha256'] != CONTRACT_SHA
            or digest(fixture / 'source-manifest.json') != contract['price_manifest_sha256']
            or index['source_manifest_sha256'] != contract['price_manifest_sha256']
            or set(index['files']) != set(contract['universe'])):
        raise ValueError('slice source mismatch')
    calendar, plan = calendar_plan(contract)
    allowed = allowed_stamps(calendar, plan)
    by_stamp = {}
    for day, clocks in plan.items():
        for name, stamp in clocks.items():
            by_stamp.setdefault(stamp, []).append((day, name))
    source = json.loads((fixture / 'source-manifest.json').read_text())
    views = {}
    for symbol, info in sorted(index['files'].items()):
        path = fixture / f'{symbol}.csv.gz'
        if (path.is_symlink() or digest(path) != info['gzip_sha256']
                or info['source_sha256'] != source['files'][symbol]['sha256']):
            raise ValueError('slice file mismatch')
        if not 0 <= info['raw_bytes'] <= MAX_SLICE:
            raise ValueError('slice declared size limit')
        view = {day: dict.fromkeys(plan[day]) for day in plan}
        raw_digest, raw_size, count, previous = hashlib.sha256(), 0, 0, None
        with gzip.open(path, 'rb') as handle:
            header = handle.readline(256)
            if header.rstrip(b'\r\n') != HEADER:
                raise ValueError('slice header mismatch')
            raw_digest.update(header)
            raw_size += len(header)
            while row := handle.readline(1025):
                raw_size += len(row)
                if len(row) > 1024 or raw_size > MAX_SLICE:
                    raise ValueError('slice actual size limit')
                raw_digest.update(row)
                parts = row.rstrip(b'\r\n').split(b',')
                if len(parts) != 7 or parts[1] != symbol.encode():
                    raise ValueError('slice row identity mismatch')
                stamp = parts[0]
                if stamp not in allowed or (previous is not None and stamp <= previous):
                    raise ValueError('unexpected, duplicate or out-of-order slice timestamp')
                previous = stamp
                bar = parse_bar(parts)
                for day, name in by_stamp[stamp]:
                    view[day][name] = bar
                count += 1
        if (raw_digest.hexdigest() != info['raw_sha256'] or raw_size != info['raw_bytes']
                or count != info['rows']):
            raise ValueError('uncompressed slice mismatch')
        views[symbol] = view
    return views


def score_day(symbol, day, observed, costs):
    row = {'symbol': symbol, 'session': day}
    needed = ('previous', 'opening', 'signal')
    missing = [k for k in needed if not observed.get(k)
               or Decimal(observed[k]['volume']) <= 0]
    if missing:
        return row | {'status': 'MISSING_SIGNAL_OBSERVATION', 'missing': missing}
    prior = Decimal(observed['previous']['close'])
    opening = Decimal(observed['opening']['open'])
    signal = Decimal(observed['signal']['close'])
    row['signal_observations'] = {k: observed[k] for k in needed}
    if opening > prior * Decimal('.98') or signal <= opening:
        return row | {'status': 'NO_SIGNAL'}
    missing = [k for k in ('entry', 'exit') if not observed.get(k)
               or Decimal(observed[k]['volume']) <= 0]
    if missing:
        return row | {'status': 'MISSING_REFERENCE', 'missing': missing}
    entry, exit_price = (Decimal(observed[k]['open']) for k in ('entry', 'exit'))
    returns = {'gross': str(exit_price / entry - 1)}
    for name, basis_points in costs.items():
        cost = Decimal(basis_points) / 10000
        returns[name] = str(exit_price * (1 - cost) / (entry * (1 + cost)) - 1)
    return row | {'status': 'REFERENCE_PAIR', 'entry': str(entry),
                  'exit': str(exit_price), 'returns': returns}


def summarize(rows, minimum):
    pairs = [row for row in rows if row['status'] == 'REFERENCE_PAIR']
    means = {}
    for key in ('gross', 'base', 'stress'):
        values = [Decimal(row['returns'][key]) for row in pairs]
        means[key] = str(sum(values) / len(values)) if values else None
    verdict = 'EXECUTION_MODEL_REQUIRED'
    if len(pairs) < minimum:
        verdict = 'INSUFFICIENT_REFERENCE_PAIRS'
    elif any(Decimal(means[k]) <= 0 for k in ('base', 'stress')):
        verdict = 'REJECTED_DEVELOPMENT'
    return {'verdict': verdict, 'reference_pairs_not_fills': len(pairs),
            'equal_weighted_mean_reference_returns': means,
            'state_counts': dict(sorted(Counter(row['status'] for row in rows).items())),
            'orders_submitted': 0, 'actual_capital_fraction': 0,
            'live_eligible': False, 'promotion_allowed': False,
            'historical_asof_proven': False, 'fill_verified': False, 'capacity_verified': False}


def calculate(fixture):
    contract = read_contract()
    views = read_views(fixture, contract)
    rows = [score_day(symbol, day, view, contract['costs_per_side_bps'])
            for symbol in sorted(views) for day, view in sorted(views[symbol].items())]
    return {'schema_version': 1, 'family_id': contract['family_id'],
            'contract_sha256': CONTRACT_SHA, 'input_lock_sha256': LOCK_SHA,
            'script_sha256': digest(Path(__file__)),
            'minimum_prior_trials': contract['minimum_prior_trials'],
            'development_sessions': contract['development_sessions'],
            'summary': summarize(rows, contract['minimum_reference_pairs']), 'observations': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('stage')
    for name in ('manifest', 'bars-dir', 'output-dir'):
        prepare.add_argument('--' + name, type=Path, required=True)
    prepare.add_argument('--throttle-seconds', type=float, default=.05)
    for name, argument in (('score', 'output'), ('verify', 'evidence')):
        command = commands.add_parser(name)
        command.add_argument('--fixture-dir', type=Path, required=True)
        command.add_argument('--' + argument, type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'stage':
        print(json.dumps(stage(args.manifest, args.bars_dir, args.output_dir,
                               args.throttle_seconds), sort_keys=True))
    elif args.command == 'score':
        if args.output.exists():
            raise FileExistsError(args.output)
        report = calculate(args.fixture_dir)
        write_json(args.output, report)
        print(json.dumps(report['summary'], sort_keys=True))
    else:
        report = calculate(args.fixture_dir)
        if report != json.loads(args.evidence.read_text()):
            raise ValueError('evidence differs from fixed-input replay')
        print(json.dumps({'verified': True, 'summary': report['summary']}, sort_keys=True))


if __name__ == '__main__':
    main()
