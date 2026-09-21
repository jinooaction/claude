import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from auto_invest.analytics import earnings_event_inputs
from auto_invest.analytics.earnings_event_inputs import import_bundle, query_bundle


def fixture_input(tmp_path, suffix='1', supersedes=None, kind='scheduled'):
    raw = b'<html><body>TEST earnings January 23, 2014 after market close.</body></html>'
    source = tmp_path / f'source{suffix}.html'
    source.write_bytes(raw)
    event = {
        'id': f'e{suffix}', 'event_key': '2014-q2', 'issuer_cik': '0000789019',
        'kind': kind, 'report_period_end': None, 'event_date': '2014-01-23',
        'time_label': 'after_close', 'document_id': f'd{suffix}',
        'evidence_quotes': ['January 23, 2014 after market close.'],
        'supersedes': supersedes, 'symbol': 'MSFT', 'lineage_status': 'unverified',
    }
    data = {'schema_version': 1, 'issuers': ['0000789019', '0000320193'],
            'documents': [{'id': f'd{suffix}', 'path': source.name,
                           'sha256': hashlib.sha256(raw).hexdigest(),
                           'url': 'https://example.com/earnings',
                           'source_claims': ['published 2014-01-03', 'SEC accepted 2014-01-23']}],
            'events': [event]}
    path = tmp_path / f'input{suffix}.json'
    path.write_text(json.dumps(data))
    return path, data


def update(path, data):
    path.write_text(json.dumps(data))


def test_current_copy_does_not_become_historical_or_actual_release(tmp_path):
    path, _ = fixture_input(tmp_path)
    with freeze_time('2026-09-21T05:00:00Z'):
        import_bundle(path, tmp_path/'bundle')
    old = query_bundle(tmp_path/'bundle', '2014-01-24T00:00:00Z')
    assert old['events'] == []
    now = query_bundle(tmp_path/'bundle', '2026-09-21T05:00:00Z')
    assert len(now['events']) == 1
    assert now['events'][0]['kind'] == 'scheduled'
    assert now['events'][0]['lineage_status'] == 'unverified'
    assert now['coverage_unknown_issuers'] == ['0000789019', '0000320193']
    assert not now['source_authenticity_verified'] and not now['live_eligible']


def test_boundary_and_timezone(tmp_path):
    path, _ = fixture_input(tmp_path)
    with freeze_time('2026-09-21T05:00:00Z'):
        import_bundle(path, tmp_path/'bundle')
    assert not query_bundle(tmp_path/'bundle', '2026-09-21T04:59:59.999999Z')['events']
    assert len(query_bundle(tmp_path/'bundle', '2026-09-21T14:00:00+09:00')['events']) == 1
    with pytest.raises(ValueError, match='timezone'):
        query_bundle(tmp_path/'bundle', '2026-09-21T05:00:00')


def test_revision_preserves_old_asof_and_old_bundle(tmp_path):
    path, _ = fixture_input(tmp_path)
    with freeze_time('2026-09-21T05:00:00Z'):
        import_bundle(path, tmp_path/'first')
    original = (tmp_path/'first/manifest.json').read_bytes()
    before = query_bundle(tmp_path/'first', '2026-09-21T05:30:00Z')
    path2, data = fixture_input(tmp_path, '2', 'e1')
    data['events'][0]['event_date'] = '2014-01-24'
    update(path2, data)
    with freeze_time('2026-09-21T06:00:00Z'):
        import_bundle(path2, tmp_path/'second', previous=tmp_path/'first')
    after = query_bundle(tmp_path/'second', '2026-09-21T05:30:00Z')
    assert before['events'] == after['events']
    assert (tmp_path/'first/manifest.json').read_bytes() == original
    current = query_bundle(tmp_path/'second', '2026-09-21T06:00:00Z')
    assert [e['id'] for e in current['events']] == ['e2']
    assert current['events'][0]['event_date'] == '2014-01-24'


@pytest.mark.parametrize('mutation', [
    'bad_hash', 'missing_quote', 'naive_import_override', 'duplicate_id',
    'unknown_issuer', 'bad_kind', 'bad_date', 'bad_period', 'bad_lineage',
    'unknown_parent', 'bad_url', 'unsafe_id', 'bool_schema',
])
def test_bad_input_never_creates_success(tmp_path, mutation):
    path, data = fixture_input(tmp_path)
    event, doc = data['events'][0], data['documents'][0]
    if mutation == 'bad_hash':
        doc['sha256'] = '0'*64
    elif mutation == 'missing_quote':
        event['evidence_quotes'] = ['not in this source']
    elif mutation == 'naive_import_override':
        event['verified_at'] = '2014-01-01'
    elif mutation == 'duplicate_id':
        data['events'].append(dict(event))
    elif mutation == 'unknown_issuer':
        event['issuer_cik'] = '0000000001'
    elif mutation == 'bad_kind':
        event['kind'] = '8-K means earnings'
    elif mutation == 'bad_date':
        event['event_date'] = '2014-02-30'
    elif mutation == 'bad_period':
        event['report_period_end'] = 'tomorrow'
    elif mutation == 'bad_lineage':
        event['lineage_status'] = True
    elif mutation == 'unknown_parent':
        event['supersedes'] = 'absent'
    elif mutation == 'bad_url':
        doc['url'] = 'file:///etc/passwd'
    elif mutation == 'unsafe_id':
        doc['id'] = '../outside'
    elif mutation == 'bool_schema':
        data['schema_version'] = True
    update(path, data)
    with pytest.raises(ValueError):
        import_bundle(path, tmp_path/'bundle')
    assert not (tmp_path/'bundle/manifest.json').exists()


def test_tampering_is_rejected_on_query(tmp_path):
    path, _ = fixture_input(tmp_path)
    import_bundle(path, tmp_path/'bundle')
    (tmp_path/'bundle/documents/d1.html').write_text('changed')
    with pytest.raises(ValueError, match='fingerprint'):
        query_bundle(tmp_path/'bundle', datetime.now(UTC).isoformat())


def test_invalid_observation_interval(tmp_path):
    path, _ = fixture_input(tmp_path)
    import_bundle(path, tmp_path/'bundle')
    manifest = tmp_path/'bundle/manifest.json'
    data = json.loads(manifest.read_text())
    data['documents'][0]['observed_end'] = '2014-01-01T00:00:00Z'
    update(manifest, data)
    with pytest.raises(ValueError, match='observation'):
        query_bundle(tmp_path/'bundle', datetime.now(UTC).isoformat())


@pytest.mark.parametrize('later', ['2026-09-21T05:00:00Z', '2026-09-21T06:00:00Z'])
def test_new_bundle_refuses_clock_rollback_or_tied_revision_time(tmp_path, later):
    path, _ = fixture_input(tmp_path)
    with freeze_time('2026-09-21T06:00:00Z'):
        import_bundle(path, tmp_path/'first')
    path2, _ = fixture_input(tmp_path, '2', 'e1')
    with freeze_time(later), pytest.raises(ValueError):
        import_bundle(path2, tmp_path/'second', previous=tmp_path/'first')


def test_serialized_bundle_limit_checked_before_creating_output(tmp_path, monkeypatch):
    path, _ = fixture_input(tmp_path)
    monkeypatch.setattr(earnings_event_inputs, 'MAX_BYTES', len(path.read_bytes())+1)
    with pytest.raises(ValueError, match='large'):
        import_bundle(path, tmp_path/'bundle')
    assert not (tmp_path/'bundle').exists()


def test_parse_completion_delays_visibility(tmp_path):
    path, _ = fixture_input(tmp_path)
    with freeze_time('2026-09-21T05:00:00Z'):
        import_bundle(path, tmp_path/'bundle')
    manifest = tmp_path/'bundle/manifest.json'
    data = json.loads(manifest.read_text())
    data['events'][0]['verified_at'] = '2026-09-21T05:02:00Z'
    update(manifest, data)
    assert not query_bundle(tmp_path/'bundle', '2026-09-21T05:01:00Z')['events']
    assert len(query_bundle(tmp_path/'bundle', '2026-09-21T05:02:00Z')['events']) == 1


def test_scope_change_and_branching_revision_are_rejected(tmp_path):
    path, _ = fixture_input(tmp_path)
    with freeze_time('2026-09-21T05:00:00Z'):
        import_bundle(path, tmp_path/'first')
    path2, data = fixture_input(tmp_path, '2', 'e1')
    data['issuers'] = ['0000789019']
    update(path2, data)
    with pytest.raises(ValueError, match='scope'):
        import_bundle(path2, tmp_path/'second', previous=tmp_path/'first')
    data['issuers'].append('0000320193')
    data['events'].append(dict(data['events'][0], id='e3'))
    update(path2, data)
    with pytest.raises(ValueError, match='parent'):
        import_bundle(path2, tmp_path/'second', previous=tmp_path/'first')


def test_empty_events_do_not_claim_no_earnings(tmp_path):
    path, data = fixture_input(tmp_path)
    data['documents'] = []
    data['events'] = []
    update(path, data)
    import_bundle(path, tmp_path/'bundle')
    result = query_bundle(tmp_path/'bundle', (datetime.now(UTC)+timedelta(seconds=1)).isoformat())
    assert result['events'] == []
    assert result['coverage_unknown_issuers'] == data['issuers']


def test_existing_output_is_preserved(tmp_path):
    path, _ = fixture_input(tmp_path)
    import_bundle(path, tmp_path/'bundle')
    original = (tmp_path/'bundle/manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        import_bundle(path, tmp_path/'bundle')
    assert (tmp_path/'bundle/manifest.json').read_bytes() == original
