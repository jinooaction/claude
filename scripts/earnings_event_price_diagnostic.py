"""Offline, development-only price diagnostic for preregistered 8-K events."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

ET = ZoneInfo('America/New_York')
CONTRACT = (
    Path(__file__).resolve().parents[1]
    / 'specs/202-earnings-event-price/contracts/preregistration.json'
)
REQUIRED_CLOCKS = ((9, 45), (9, 47), (15, 56))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_fixed_inputs(
    audit_path: Path, manifest_path: Path, contract_path: Path = CONTRACT
) -> tuple[dict, dict, dict]:
    contract = json.loads(contract_path.read_text())
    if (
        contract['family_id'] != 'earnings-filing-follow-through-long-v1'
        or contract['candidate_count'] != 1
    ):
        raise ValueError('unexpected preregistration')
    for path, field in (
        (audit_path, 'source_audit_sha256'),
        (manifest_path, 'price_manifest_sha256'),
    ):
        if sha256_file(path) != contract[field]:
            raise ValueError(f'{field} mismatch')
    audit = json.loads(audit_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if audit['historical_asof_proven'] or audit['strategy_admitted'] or audit['live_eligible']:
        raise ValueError('source safety flags changed')
    if manifest['calendar'] != 'XNYS' or len(manifest['files']) != 30:
        raise ValueError('unexpected price input')
    return contract, audit, manifest


def entry_session(acceptance_utc: str, calendar: object) -> str:
    when = datetime.fromisoformat(acceptance_utc.replace('Z', '+00:00'))
    if when.tzinfo is None:
        raise ValueError('acceptance time must have timezone')
    et = when.astimezone(ET)
    day = et.date().isoformat()
    next_or_same = calendar.date_to_session(day, direction='next')
    if next_or_same.date().isoformat() == day and et.time() < time(9, 30):
        return day
    if next_or_same.date().isoformat() == day:
        return calendar.next_session(next_or_same).date().isoformat()
    return next_or_same.date().isoformat()


def select_events(
    audit: dict, contract: dict, calendar: object
) -> tuple[list[dict], dict[str, int]]:
    excluded: Counter[str] = Counter()
    chosen: dict[tuple[str, str], dict] = {}
    first, last = contract['development_entry_sessions']
    for event in audit['events']:
        if not event['universe_known_at_acceptance']:
            excluded['before_universe_publication'] += 1
            continue
        if event['lineage_blocked'] or event['symbol'] in contract['excluded_symbols']:
            excluded['lineage_unverified'] += 1
            continue
        if event['is_amendment']:
            excluded['amendment'] += 1
            continue
        if event['publisher_knowledge_estimated']:
            excluded['estimated_knowledge_time'] += 1
            continue
        session = entry_session(event['source_claimed_acceptance_utc'], calendar)
        if not first <= session <= last:
            excluded['outside_development_entry_sessions'] += 1
            continue
        key = event['symbol'], session
        candidate = {
            'accession': event['accession'],
            'acceptance_utc': event['source_claimed_acceptance_utc'],
            'symbol': event['symbol'],
            'entry_session': session,
        }
        if key in chosen:
            excluded['duplicate_symbol_session'] += 1
            if (candidate['acceptance_utc'], candidate['accession']) < (
                chosen[key]['acceptance_utc'], chosen[key]['accession']
            ):
                chosen[key] = candidate
        else:
            chosen[key] = candidate
    return (
        sorted(chosen.values(), key=lambda row: (row['entry_session'], row['symbol'])),
        dict(sorted(excluded.items())),
    )


def utc_stamp(session: str, hour: int, minute: int) -> bytes:
    local = datetime.combine(datetime.fromisoformat(session).date(), time(hour, minute), tzinfo=ET)
    return local.astimezone(UTC).isoformat().encode()


def observe_symbol(
    path: Path, symbol: str, dates: set[str], calendar: object, expected_sha: str
) -> dict[str, dict]:
    expected_previous = {
        day: calendar.previous_session(day) for day in dates
    }
    expected_last_stamp = {
        day: (calendar.session_close(previous) - timedelta(minutes=1)).isoformat().encode()
        for day, previous in expected_previous.items()
    }
    clock_map = {
        day: {utc_stamp(day, *clock): clock for clock in REQUIRED_CLOCKS}
        for day in dates
    }
    observations = {day: {} for day in dates}
    digest = hashlib.sha256()
    prior_day = None
    last_close = None
    last_stamp = None
    current_day = None
    with path.open('rb') as handle:
        header = handle.readline()
        digest.update(header)
        if header.strip() != b'timestamp_utc,symbol,open,high,low,close,volume':
            raise ValueError(f'{symbol}: unexpected CSV header')
        for row in handle:
            digest.update(row)
            day = row[:10].decode('ascii')
            if day != current_day:
                prior_day, current_day = current_day, day
                if day in dates:
                    observations[day]['previous_close'] = (
                        last_close
                        if (
                            prior_day == expected_previous[day].date().isoformat()
                            and last_stamp == expected_last_stamp[day]
                        )
                        else None
                    )
            parts = row.rstrip(b'\r\n').split(b',')
            if len(parts) != 7 or parts[1].decode('ascii') != symbol:
                raise ValueError(f'{symbol}: malformed or mismatched price row')
            last_close = parts[5].decode('ascii')
            last_stamp = parts[0]
            if day in dates:
                clock = clock_map[day].get(parts[0])
                if clock is not None:
                    observations[day][f'{clock[0]:02d}{clock[1]:02d}'] = {
                        'open': parts[2].decode('ascii'),
                        'close': parts[5].decode('ascii'),
                        'volume': parts[6].decode('ascii'),
                    }
    if digest.hexdigest() != expected_sha:
        raise ValueError(f'{symbol}: price SHA-256 mismatch')
    return observations


def score_event(event: dict, observed: dict, costs: dict) -> dict:
    result = dict(event)
    needed = ('previous_close', '0945', '0947', '1556')
    missing = [name for name in needed if not observed.get(name)]
    if missing:
        result['status'] = 'MISSING_OBSERVATION'
        result['missing'] = missing
        return result
    previous = Decimal(observed['previous_close'])
    signal = Decimal(observed['0945']['close'])
    entry = Decimal(observed['0947']['open'])
    exit_price = Decimal(observed['1556']['open'])
    volumes = [Decimal(observed[name]['volume']) for name in ('0945', '0947', '1556')]
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


def file_symbol_matches(symbol: str, file_symbol: str) -> bool:
    """The UTX source was RTX-labeled; converted CSV rows retain the UTX member name."""
    return file_symbol == symbol or (symbol == 'UTX' and file_symbol == 'RTX')


def run(audit_path: Path, manifest_path: Path, bars_dir: Path, output_path: Path) -> dict:
    if output_path.exists():
        raise FileExistsError(output_path)
    contract, audit, manifest = load_fixed_inputs(audit_path, manifest_path)
    calendar = xcals.get_calendar('XNYS')
    events, excluded = select_events(audit, contract, calendar)
    by_symbol: dict[str, set[str]] = {}
    for event in events:
        by_symbol.setdefault(event['symbol'], set()).add(event['entry_session'])
    observations: dict[str, dict[str, dict]] = {}
    for symbol, info in sorted(manifest['files'].items()):
        relative = Path(info['path'])
        if relative.is_absolute() or len(relative.parts) != 1 or relative.name != f'{symbol}.csv':
            raise ValueError(f'{symbol}: unsafe manifest path')
        if (
            not file_symbol_matches(symbol, info['file_symbol'])
            or info['provider'] != 'hfdatalibrary-pitrading'
        ):
            raise ValueError(f'{symbol}: unexpected price identity')
        observations[symbol] = observe_symbol(
            bars_dir / relative,
            symbol,
            by_symbol.get(symbol, set()),
            calendar,
            info['sha256'],
        )
    rows = [
        score_event(
            event,
            observations[event['symbol']][event['entry_session']],
            contract['costs_per_side_bps'],
        )
        for event in events
    ]
    statuses = dict(sorted(Counter(row['status'] for row in rows).items()))
    pairs = [row for row in rows if row['status'] == 'REFERENCE_PAIR']
    summary = {}
    for name in ('gross', *contract['costs_per_side_bps']):
        values = [Decimal(row['returns'][name]) for row in pairs]
        summary[name] = {
            'mean_return': str(sum(values) / len(values)) if values else None,
            'positive_pairs': sum(value > 0 for value in values),
            'negative_pairs': sum(value < 0 for value in values),
        }
    report = {
        'schema_version': 1,
        'family_id': contract['family_id'],
        'contract_sha256': sha256_file(CONTRACT),
        'script_sha256': sha256_file(Path(__file__)),
        'source_audit_sha256': contract['source_audit_sha256'],
        'price_manifest_sha256': contract['price_manifest_sha256'],
        'development_entry_sessions': contract['development_entry_sessions'],
        'excluded_event_reasons': excluded,
        'event_status_counts': statuses,
        'reference_pair_count_not_fills': len(pairs),
        'equal_weighted_reference_pair_summary': summary,
        'events': rows,
        'historical_asof_proven': False,
        'fill_verified': False,
        'capacity_verified': False,
        'live_eligible': False,
        'promotion_allowed': False,
        'orders_submitted': 0,
        'actual_capital_fraction': 0,
    }
    with output_path.open('x') as handle:
        json.dump(report, handle, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        handle.write('\n')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--bars-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = run(args.audit, args.manifest, args.bars_dir, args.output)
    print(json.dumps({
        'event_status_counts': report['event_status_counts'],
        'reference_pair_count_not_fills': report['reference_pair_count_not_fills'],
        'equal_weighted_reference_pair_summary': report['equal_weighted_reference_pair_summary'],
        'live_eligible': report['live_eligible'],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
