"""Pinned acceptance claims must not become historical publication proof."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import duckdb
import exchange_calendars
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/earnings_metadata_audit.py'


def _module():
    spec = importlib.util.spec_from_file_location('earnings_metadata_audit', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path):
    accession = '0001193125-14-018629'
    acceptance = tmp_path / 'acceptance.parquet'
    earnings = tmp_path / 'earnings.parquet'
    db = duckdb.connect(':memory:')
    db.execute(f"""
        COPY (SELECT '{accession}' AS accession_no, 789019::BIGINT AS cik,
                     '8-K' AS form, TIMESTAMPTZ '2014-01-23 21:06:07+00' AS stated_at,
                     -300::INTEGER AS stated_offset_minutes,
                     'edgar_company_feed' AS source,
                     TIMESTAMPTZ '2026-09-25 00:00:00+00' AS fetched_at)
        TO '{acceptance}' (FORMAT PARQUET)
    """)
    db.execute(f"""
        COPY (SELECT '{accession}' AS accession_no, '0000789019' AS cik,
                     '2.02' AS item_code,
                     TIMESTAMPTZ '2014-01-23 21:06:07+00' AS knowledge_date,
                     false AS knowledge_estimated, false AS is_amendment,
                     'after_market' AS market_session,
                     NULL::VARCHAR AS item_text, NULL::VARCHAR AS exhibit_text)
        TO '{earnings}' (FORMAT PARQUET)
    """)
    mirrors = tmp_path / 'mirrors'
    mirrors.mkdir()
    (mirrors / f'{accession}.json').write_text(json.dumps({
        'metadata_accession-number': accession,
        'metadata_filing-date': '20140124',
        'metadata_filer': json.dumps({'company-data': {'cik': '0000789019'}}),
    }))
    universe = [{'symbol': 'MSFT' if n == 1 else f'S{n}',
                 'cik': 789019 if n == 1 else n,
                 'lineage_blocked': n in (2, 3)} for n in range(1, 31)]
    universe[1]['symbol'] = 'DD'
    universe[2]['symbol'] = 'UTX'
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({
        'dataset': 'ZipLime/sec-8k-events', 'revision': 'a' * 40,
        'acceptance_sha256': hashlib.sha256(acceptance.read_bytes()).hexdigest(),
        'earnings_sha256': hashlib.sha256(earnings.read_bytes()).hexdigest(),
        'market_date_start': '2014-01-01', 'market_date_end': '2014-03-31',
        'universe_public_date': '2014-02-24', 'universe_public_source': 'https://sec.gov/example',
        'universe': universe,
    }))
    return manifest, acceptance, earnings, mirrors


def test_acceptance_join_keeps_claims_distinct_from_historical_publication(tmp_path):
    inputs = _fixture(tmp_path)
    report = _module().audit(*inputs)
    assert report['counts']['mirror_rows_matched'] == 1
    assert report['counts']['mirror_filing_date_differs_from_acceptance_et'] == 1
    assert report['counts']['universe_known_unestimated_nonamendment_by_session'] == {}
    assert report['counts']['before_universe_public_date'] == 1
    assert report['counts']['publisher_session_disagreements'] == 0
    assert len(report['mirror_json_sha256']) == 64
    event = report['events'][0]
    assert event['source_claimed_acceptance_utc'] == '2014-01-23T21:06:07Z'
    assert event['historical_asof_proven'] is False
    assert event['strategy_admitted'] is False
    assert event['live_eligible'] is False
    assert event['universe_known_at_acceptance'] is False


def test_public_universe_date_changes_only_research_count(tmp_path):
    manifest, acceptance, earnings, mirrors = _fixture(tmp_path)
    data = json.loads(manifest.read_text())
    data['universe_public_date'] = '2013-12-31'
    manifest.write_text(json.dumps(data))
    report = _module().audit(manifest, acceptance, earnings, mirrors)
    assert report['counts']['universe_known_unestimated_nonamendment_by_session'] == {
        'after_market': 1}
    assert report['events'][0]['historical_asof_proven'] is False


def test_exchange_calendar_handles_holiday_and_early_close():
    module = _module()
    calendar = exchange_calendars.get_calendar('XNYS')
    assert module._session_label('2016-03-25T19:34:12Z', calendar) == 'non_trading_day'
    assert module._session_label('2018-07-03T18:31:40Z', calendar) == 'after_market'


def test_modified_source_and_wrong_mirror_identity_are_refused(tmp_path):
    manifest, acceptance, earnings, mirrors = _fixture(tmp_path)
    module = _module()
    acceptance.write_bytes(acceptance.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='sha256'):
        module.audit(manifest, acceptance, earnings, mirrors)
    acceptance.write_bytes(acceptance.read_bytes()[:-7])
    path = next(mirrors.glob('*.json'))
    row = json.loads(path.read_text())
    row['metadata_filer'] = json.dumps({'company-data': {'cik': '12345'}})
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match='CIK'):
        module.audit(manifest, acceptance, earnings, mirrors)


def test_claimed_acceptance_cannot_be_missing_from_pinned_table(tmp_path):
    manifest, acceptance, earnings, mirrors = _fixture(tmp_path)
    path = next(mirrors.glob('*.json'))
    row = json.loads(path.read_text())
    row['metadata_accession-number'] = '0001193125-14-999999'
    path.unlink()
    (mirrors / '0001193125-14-999999.json').write_text(json.dumps(row))
    with pytest.raises(ValueError, match='mirror accession'):
        _module().audit(manifest, acceptance, earnings, mirrors)


def test_cli_refuses_to_replace_an_existing_evidence_file(tmp_path, monkeypatch):
    manifest, acceptance, earnings, mirrors = _fixture(tmp_path)
    output = tmp_path / 'existing.json'
    output.write_text('original evidence')
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--manifest', str(manifest),
                        '--acceptance', str(acceptance), '--earnings', str(earnings),
                        '--mirror-dir', str(mirrors), '--output', str(output)])
    assert _module().main() == 2
    assert output.read_text() == 'original evidence'
