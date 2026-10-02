"""Audit pinned public 8-K event metadata without granting historical trading authority."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import exchange_calendars


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if manifest['dataset'] != 'ZipLime/sec-8k-events':
        raise ValueError('unexpected dataset')
    if len(manifest['revision']) != 40:
        raise ValueError('revision must be a fixed commit')
    if not manifest['universe_public_date'] or not manifest['universe_public_source']:
        raise ValueError('universe publication evidence missing')
    universe = manifest['universe']
    if len(universe) != 30 or len({row['symbol'] for row in universe}) != 30:
        raise ValueError('universe must contain 30 unique symbols')
    if len({int(row['cik']) for row in universe}) != 30:
        raise ValueError('universe must contain 30 unique CIKs')
    if {row['symbol'] for row in universe if row['lineage_blocked']} != {'DD', 'UTX'}:
        raise ValueError('corporate lineage exclusions changed')
    return manifest


def _read_mirrors(directory: Path) -> dict[str, int]:
    mirrors = {}
    for path in sorted(directory.glob('*.json')):
        row = json.loads(path.read_text())
        accession = row['metadata_accession-number']
        if accession != path.stem or accession in mirrors:
            raise ValueError('mirror accession mismatch or duplicate')
        filer = json.loads(row['metadata_filer'])
        mirrors[accession] = int(filer['company-data']['cik'])
    if not mirrors:
        raise ValueError('mirror directory has no source rows')
    return mirrors


def _mirror_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.glob('*.json')):
        digest.update(path.name.encode('utf-8'))
        digest.update(b'\x00')
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _session_label(utc: str, calendar) -> str:
    instant = datetime.fromisoformat(utc.replace('Z', '+00:00'))
    day = instant.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    if not calendar.is_session(day):
        return 'non_trading_day'
    if instant < calendar.session_open(day):
        return 'pre_market'
    if instant >= calendar.session_close(day):
        return 'after_market'
    return 'regular_session'


def audit(manifest_path: Path, acceptance_path: Path, earnings_path: Path,
          mirror_dir: Path) -> dict:
    manifest = _load_manifest(manifest_path)
    for path, key in ((acceptance_path, 'acceptance_sha256'),
                      (earnings_path, 'earnings_sha256')):
        if _sha256(path) != manifest[key]:
            raise ValueError(f'{key} mismatch')
    mirrors = _read_mirrors(mirror_dir)
    by_cik = {int(row['cik']): row for row in manifest['universe']}
    calendar = exchange_calendars.get_calendar('XNYS')
    db = duckdb.connect(':memory:')
    db.from_parquet(str(acceptance_path)).create_view('acceptance')
    db.from_parquet(str(earnings_path)).create_view('earnings')
    ciks = ', '.join(str(cik) for cik in sorted(by_cik))
    start, end = manifest['market_date_start'], manifest['market_date_end']
    acceptance_rows = db.execute(f"""
        SELECT accession_no, cik, form,
               strftime(stated_at AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ'),
               strftime(stated_at AT TIME ZONE 'America/New_York', '%Y-%m-%dT%H:%M:%S'),
               stated_offset_minutes, source
        FROM acceptance
        WHERE cik IN ({ciks}) AND form IN ('8-K', '8-K/A')
          AND CAST(stated_at AT TIME ZONE 'America/New_York' AS DATE) BETWEEN ? AND ?
        ORDER BY accession_no
    """, [start, end]).fetchall()
    by_accession = {}
    for accession, cik, form, utc, et, offset, source in acceptance_rows:
        if not accession or accession in by_accession or not utc or not et:
            raise ValueError('ambiguous acceptance metadata')
        if int(cik) not in by_cik or offset not in (-240, -300):
            raise ValueError('unexpected CIK or timezone offset')
        actual_offset = datetime.fromisoformat(utc.replace('Z', '+00:00')).astimezone(
            ZoneInfo('America/New_York')).utcoffset()
        if actual_offset is None or int(actual_offset.total_seconds() / 60) != offset:
            raise ValueError('claimed ET offset disagrees with calendar')
        by_accession[accession] = (int(cik), form, utc, et, offset, source)
    missing_mirrors = sorted(set(mirrors) - set(by_accession))
    wrong_cik = sorted(accession for accession, cik in mirrors.items()
                       if accession in by_accession and by_accession[accession][0] != cik)
    if missing_mirrors or wrong_cik:
        raise ValueError('mirror accession or CIK does not match pinned acceptance')

    earnings_rows = db.execute(f"""
        SELECT accession_no, CAST(cik AS BIGINT),
               strftime(knowledge_date AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ'),
               knowledge_estimated, is_amendment, market_session,
               item_text IS NOT NULL, exhibit_text IS NOT NULL
        FROM earnings
        WHERE CAST(cik AS BIGINT) IN ({ciks}) AND item_code = '2.02'
          AND CAST(knowledge_date AT TIME ZONE 'America/New_York' AS DATE)
              BETWEEN ? AND ?
        ORDER BY accession_no
    """, [start, end]).fetchall()
    events = []
    seen = set()
    for (accession, cik, knowledge, estimated, amendment, claimed_session,
         item_text_present, exhibit_text_present) in earnings_rows:
        if not accession or accession in seen or accession not in by_accession:
            raise ValueError('missing or duplicate Item 2.02 acceptance')
        seen.add(accession)
        accepted_cik, form, accepted_utc, accepted_et, offset, source = by_accession[accession]
        if cik != accepted_cik or not knowledge or estimated is None or amendment is None:
            raise ValueError('Item 2.02 identity or timestamp claim is incomplete')
        session = _session_label(accepted_utc, calendar)
        lineage_blocked = by_cik[cik]['lineage_blocked']
        universe_known = accepted_et[:10] > manifest['universe_public_date']
        events.append({
            'accession': accession,
            'symbol': by_cik[cik]['symbol'],
            'cik': cik,
            'form': form,
            'source_claimed_acceptance_utc': accepted_utc,
            'source_claimed_acceptance_et': accepted_et,
            'source_claimed_et_offset_minutes': offset,
            'source_claimed_acceptance_provider': source,
            'publisher_claimed_knowledge_utc': knowledge,
            'publisher_knowledge_estimated': estimated,
            'publisher_claim_matches_acceptance': knowledge == accepted_utc,
            'publisher_market_session': claimed_session,
            'acceptance_time_session': session,
            'is_amendment': amendment,
            'lineage_blocked': lineage_blocked,
            'universe_known_at_acceptance': universe_known,
            'publisher_item_text_present': item_text_present,
            'publisher_exhibit_text_present': exhibit_text_present,
            'historical_asof_proven': False,
            'strategy_admitted': False,
            'live_eligible': False,
        })
    counts = Counter(row['acceptance_time_session'] for row in events
                     if row['universe_known_at_acceptance']
                     and not row['lineage_blocked'] and not row['is_amendment']
                     and not row['publisher_knowledge_estimated'])
    publisher_session_disagreements = sorted(
        row['accession'] for row in events
        if row['publisher_market_session'] != row['acceptance_time_session'])
    filing_date_mismatches = []
    for path in sorted(mirror_dir.glob('*.json')):
        row = json.loads(path.read_text())
        accession = row['metadata_accession-number']
        if row['metadata_filing-date'] != by_accession[accession][3][:10].replace('-', ''):
            filing_date_mismatches.append(accession)
    return {
        'schema': 'earnings-metadata-audit-v1',
        'source': {'dataset': manifest['dataset'], 'revision': manifest['revision'],
                   'acceptance_sha256': manifest['acceptance_sha256'],
                   'earnings_sha256': manifest['earnings_sha256']},
        'market_date_range_et': [start, end],
        'universe_public_date': manifest['universe_public_date'],
        'universe_public_source': manifest['universe_public_source'],
        'mirror_json_sha256': _mirror_digest(mirror_dir),
        'counts': {'universe': len(by_cik), 'acceptance_rows': len(acceptance_rows),
                   'mirror_rows_matched': len(mirrors), 'item_202_events': len(events),
                   'before_universe_public_date': sum(
                       not row['universe_known_at_acceptance'] for row in events),
                   'universe_known_unestimated_nonamendment_by_session': dict(
                       sorted(counts.items())),
                   'publisher_session_disagreements': len(publisher_session_disagreements),
                   'mirror_filing_date_differs_from_acceptance_et': len(filing_date_mismatches)},
        'mirror_filing_date_mismatch_accessions': filing_date_mismatches,
        'publisher_session_disagreement_accessions': publisher_session_disagreements,
        'exchange_calendar': f'XNYS/exchange_calendars/{exchange_calendars.__version__}',
        'historical_asof_proven': False,
        'strategy_admitted': False,
        'live_eligible': False,
        'events': events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--acceptance', type=Path, required=True)
    parser.add_argument('--earnings', type=Path, required=True)
    parser.add_argument('--mirror-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.manifest, args.acceptance, args.earnings, args.mirror_dir)
        with args.output.open('x') as target:
            json.dump(result, target, indent=2, sort_keys=True)
            target.write('\n')
        print(json.dumps(result['counts'], sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, duckdb.Error) as exc:
        print(f'metadata audit refused: {type(exc).__name__}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
