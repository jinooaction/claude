"""Small synthetic lifecycle checks, never actual research acceptance or authority."""
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from freezegun import freeze_time

from auto_invest.analytics.intraday_archive import review_archives
from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.analytics.intraday_research_identity import (
    archive_input_identity,
    research_content_digest,
)
from auto_invest.execution import intraday_registration as registration
from auto_invest.execution import intraday_selection as selection
from auto_invest.market_data.intraday import (
    CALENDAR,
    SYMBOLS,
    DataError,
    digest,
    encode,
    iso,
    write_batch,
)

PREREG = Path('specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json')
COMMIT = 'a' * 40


def make_archive(root, *, volume=10000, retrieval_seconds=60, synthetic=True):
    opening = CALENDAR.session_open('2026-09-08').to_pydatetime()
    closing = CALENDAR.session_close('2026-09-08').to_pydatetime()
    rows = [dict(symbol=s, timestamp_utc=iso(opening+timedelta(minutes=5*i)),
                 open=100, high=101, low=99, close=100, volume=volume)
            for i in range(78) for s in SYMBOLS]
    write_batch(root/'2026-09-08', dict(provider='kis-nasdaq-partial-unadjusted',
        synthetic=synthetic, pages=[], bars=rows,
        retrieved_at_utc=iso(closing+timedelta(seconds=retrieval_seconds))))
    return root


def test_actual_small_recomputation_only_changes_generated_artifact_time(tmp_path):
    root = make_archive(tmp_path/'archives')
    before = {p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with freeze_time('2026-10-10T15:00:00Z'):
        first = selection.select_research(root, PREREG, COMMIT)
    with freeze_time('2026-10-10T15:00:01Z'):
        second = selection.select_research(root, PREREG, COMMIT)
    assert first.dataset_fingerprint == second.dataset_fingerprint
    assert first.research_digest == second.research_digest
    assert first.candidate is second.candidate is None
    assert first.verdict == second.verdict == 'INSUFFICIENT_EVIDENCE'
    assert all(p.read_bytes()==raw for p,raw in before.items())


def test_reports_retain_real_generation_time_and_original_input_binding(tmp_path):
    root = make_archive(tmp_path/'archives')
    reports = []
    for index in range(2):
        out = tmp_path/str(index)
        with freeze_time(f'2026-10-10T15:00:0{index}Z'):
            review_archives(root, out, PREREG, COMMIT)
        reports.append(json.loads((out/'research.json').read_bytes()))
    assert reports[0]['generated_at_utc'] != reports[1]['generated_at_utc']
    assert (reports[0]['data_quality']['dataset_fingerprint']
            == reports[1]['data_quality']['dataset_fingerprint'])
    assert reports[0]['archive_input_identity'] == reports[1]['archive_input_identity']
    assert reports[0]['archive_input_identity']['scope'] == 'intraday-archive-input-v1'


@pytest.mark.parametrize('changed', ['volume', 'retrieval_seconds', 'synthetic'])
def test_original_source_change_still_changes_data_identity(tmp_path, changed):
    first = make_archive(tmp_path/'first')
    second = make_archive(tmp_path/'second', **{changed: {
        'volume':10001, 'retrieval_seconds':61, 'synthetic':False}[changed]})
    with freeze_time('2026-10-10T15:00:00Z'):
        a = selection.select_research(first, PREREG, COMMIT)
        b = selection.select_research(second, PREREG, COMMIT)
    assert a.dataset_fingerprint != b.dataset_fingerprint
    assert a.research_digest != b.research_digest
    assert a.candidate is b.candidate is None


def evaluation(monkeypatch, *, changes=None):
    """Accepted-result fixture only to isolate registration binding, no real prices."""
    candidate = build_candidate_registry(load_preregistration(PREREG))[0]
    reports = []

    def review(archives, output, prereg, commit):
        output.mkdir()
        report = dict(generated_at_utc=iso(datetime.now(UTC)), code_commit=commit,
                      selection={'selected_candidate_id':candidate.candidate_id},
                      decision={'passed':True, 'verdict':'PAPER_CHALLENGER'},
                      cost_models={'base':31,'stress':40}, ledger_sha256='fixed',
                      preregistration_sha256='fixed')
        if changes:
            report.update(changes)
        raw = encode(report)
        reports.append(raw)
        (output/'research.json').write_bytes(raw)
        return dict(decision=report['decision'], synthetic=False,
                    provider='kis-nasdaq-partial-unadjusted',
                    dataset_fingerprint='sha256:'+'b'*64, session_count=756, missing_sessions=0)

    monkeypatch.setattr(selection, 'review_archives', review)
    return reports


def test_registered_fixture_can_be_recomputed_at_a_later_time(tmp_path, monkeypatch):
    evaluation(monkeypatch)
    monkeypatch.setattr(registration, '_read_key', lambda:b'k'*32)
    monkeypatch.setattr(registration.subprocess, 'check_output', lambda *a,**k:COMMIT)
    with freeze_time('2026-10-10T15:00:00Z'):
        record = registration.register(tmp_path, PREREG)
    with freeze_time('2026-10-10T15:00:01Z'):
        selected = selection.select_research(tmp_path, PREREG, COMMIT)
        assert (registration.verify_registration(record, selected, PREREG)
                == datetime(2026,10,10,15,tzinfo=UTC))
    assert selected.public()['live_eligible'] is False
    assert selected.public()['orders_submitted'] == 0


@pytest.mark.parametrize('changes', [
    {'code_commit':'c'*40}, {'ledger_sha256':'changed'},
    {'cost_models':{'base':1,'stress':2}}, {'preregistration_sha256':'changed'},
    {'unknown_claim':True}, {'decision':{'passed':False,'verdict':'NO_INTRADAY_EDGE'}},
])
def test_every_non_generation_field_remains_bound(tmp_path, monkeypatch, changes):
    evaluation(monkeypatch)
    with freeze_time('2026-10-10T15:00:00Z'):
        first = selection.select_research(tmp_path, PREREG, COMMIT)
    evaluation(monkeypatch, changes=changes)
    with freeze_time('2026-10-10T15:00:00Z'):
        second = selection.select_research(tmp_path, PREREG, COMMIT)
    assert first.research_digest != second.research_digest


def test_prior_raw_report_digest_cannot_be_accepted_as_current_registration(tmp_path, monkeypatch):
    reports = evaluation(monkeypatch)
    monkeypatch.setattr(registration, '_read_key', lambda:b'k'*32)
    monkeypatch.setattr(registration.subprocess, 'check_output', lambda *a,**k:COMMIT)
    with freeze_time('2026-10-10T15:00:00Z'):
        selected = selection.select_research(tmp_path, PREREG, COMMIT)
        prior = replace(selected, research_digest=digest(reports[-1]))
        assert prior.research_digest != selected.research_digest
        monkeypatch.setattr(registration, 'select_research', lambda *args:prior)
        record = registration.register(tmp_path, PREREG)
        with pytest.raises(DataError, match='REGISTRATION_IDENTITY_CHANGED'):
            registration.verify_registration(record, selected, PREREG)


def test_content_digest_canonicalizes_representation_but_only_ignores_generation():
    original = {'generated_at_utc':'first', 'selection':{'candidate':'same'}, 'observed':'original'}
    reordered = {'observed':'original', 'selection':{'candidate':'same'},
                 'generated_at_utc':'second'}
    assert research_content_digest(original) == research_content_digest(reordered)
    assert (research_content_digest(original)
            != research_content_digest(dict(original, observed='changed')))
    assert original['generated_at_utc'] == 'first'


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_content_cannot_receive_a_digest(value):
    with pytest.raises(ValueError):
        research_content_digest({'decision':{'statistic':value}})


@pytest.mark.parametrize('changed', ['provider', 'synthetic', 'adjustment_policy', 'lineage'])
def test_input_scope_and_original_lineage_stay_bound(changed):
    fields = dict(provider='kis-nasdaq-partial-unadjusted', synthetic=True,
                  adjustment_policy='unadjusted', lineage=[{'session':'2026-09-08',
                  'raw_sha256':'sha256:'+'a'*64,'manifest_sha256':'sha256:'+'b'*64}])
    first = encode(archive_input_identity(**fields))
    other = dict(fields)
    other[changed] = {'provider':'alpaca-sip-split','synthetic':False,
                      'adjustment_policy':'split','lineage':[]}[changed]
    assert first != encode(archive_input_identity(**other))
