"""Issuer collection shares limits but never SEC identity or circuit state."""

import importlib.util
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from auto_invest.analytics.filing_observations import ISSUER_FEED, RunStore, utc
from auto_invest.market_data.filing_collector import Collector, Scope
from auto_invest.market_data.issuer_filings import USER_AGENT, IssuerCollector, IssuerScope

URL = 'https://news.microsoft.com/source/2026/07/29/microsoft-quarter-results/'
TITLE = 'Microsoft quarter results'
FEED = (f'<rss version="2.0"><channel><link>https://news.microsoft.com/source/tag/'
        f'press-releases/</link><item><title>{TITLE}</title><link>{URL}</link>'
        '<pubDate>Wed, 29 Jul 2026 20:25:10 +0000</pubDate></item>'
        '<item><title>Microsoft donation</title><link>https://news.microsoft.com/source/'
        '2026/07/29/donation/</link><pubDate>Wed, 29 Jul 2026 20:00:00 +0000</pubDate>'
        '</item></channel></rss>').encode()
DOCUMENT = f'<html><h1>{TITLE}</h1></html>'.encode()


class Clock:
    elapsed = 0.0

    def utc(self):
        return (datetime(2026, 9, 29, tzinfo=UTC) + timedelta(
            seconds=self.elapsed)).isoformat().replace('+00:00', 'Z')

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds


def run(store, clock, client, identity='one', cls=IssuerCollector, reuse=False):
    collector = cls(store, IssuerScope() if cls is IssuerCollector else Scope(),
                    user_agent=USER_AGENT if cls is IssuerCollector else 'Test a@example.invalid',
                    client=client, utc_now=clock.utc, monotonic=clock.monotonic, sleep=clock.sleep)
    options = {'reuse_unchanged': reuse} if cls is IssuerCollector else {}
    return collector.collect(run_id=identity, source_commit='a' * 40, **options)


def test_collect_two_runs_preserves_bytes_and_reports_selection(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers['User-Agent'] == USER_AGENT
        assert '@' not in request.headers['User-Agent']
        return httpx.Response(200, content=FEED if str(request.url) == ISSUER_FEED else DOCUMENT)

    clock = Clock()
    store = RunStore(tmp_path, clock=clock.utc)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run(store, clock, client)
        first = (tmp_path/'runs/one.json').read_bytes()
        clock.sleep(2)
        run(store, clock, client, 'two')
    assert result['complete'] and result['coverage'] == {'succeeded': 2, 'failed': 0, 'skipped': 1}
    assert store.verify()[0]['manifest']['selection'] == {'unselected': 1, 'limit_skipped': 0}
    assert len(store.query(clock.utc())['observations']) == 4
    assert (tmp_path/'runs/one.json').read_bytes() == first and len(seen) == 4


def test_server_reuse_skips_only_recent_identical_complete_primaries(tmp_path):
    seen = []
    feed = [FEED]

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, content=feed[0] if str(request.url) == ISSUER_FEED
                              else DOCUMENT)

    clock = Clock()
    store = RunStore(tmp_path, clock=clock.utc)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run(store, clock, client, 'first', reuse=True)
        clock.sleep(900)
        run(store, clock, client, 'same', reuse=True)
        assert len(seen) == 3
        assert store.verify()[-1]['manifest']['selection'] == {
            'unselected': 1, 'limit_skipped': 0, 'unchanged': 1,
        }
        feed[0] = FEED.replace(b'<rss', b'<rss  ')
        clock.sleep(900)
        run(store, clock, client, 'changed', reuse=True)
        assert len(seen) == 5
        clock.sleep(24 * 3600)
        run(store, clock, client, 'expired', reuse=True)
    assert len(seen) == 7
    assert [item['manifest']['selection']['unchanged'] for item in store.verify()] == [
        0, 1, 0, 0,
    ]


def test_server_retries_primary_after_previous_failure(tmp_path):
    seen = []
    valid = [False]

    def handler(request):
        seen.append(str(request.url))
        if str(request.url) == ISSUER_FEED:
            return httpx.Response(200, content=FEED)
        return httpx.Response(200, content=DOCUMENT if valid[0] else b'<html>wrong</html>')

    clock = Clock()
    store = RunStore(tmp_path, clock=clock.utc)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert not run(store, clock, client, 'failed', reuse=True)['complete']
        valid[0] = True
        clock.sleep(900)
        assert run(store, clock, client, 'retried', reuse=True)['complete']
    assert len(seen) == 4
    assert store.verify()[-1]['manifest']['selection']['unchanged'] == 0


def test_403_persists_and_rejects_switching_collectors_before_http(tmp_path):
    calls = []
    clock = Clock()
    store = RunStore(tmp_path, clock=clock.utc)
    with httpx.Client(transport=httpx.MockTransport(
            lambda request: calls.append(request) or httpx.Response(403))) as client:
        assert not run(store, clock, client)['complete']
        run(store, clock, client, 'two')
        with pytest.raises(ValueError, match='separate'):
            run(store, clock, client, 'sec-wrong-store', cls=Collector)
    assert len(calls) == 1
    assert store.verify()[-1]['manifest']['failures'][0]['code'] == 'cooldown'


def test_personal_agent_and_extra_configuration_are_rejected(tmp_path):
    with httpx.Client() as client, pytest.raises(ValueError):
        IssuerCollector(RunStore(tmp_path), IssuerScope(),
                        user_agent='Private a@example.invalid', client=client)
    with pytest.raises(ValueError):
        IssuerScope.from_dict({'url': 'https://evil.example'})


def test_issuer_cli_ignores_sec_secret_and_exports_original(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts/filing_observations.py'
    spec = importlib.util.spec_from_file_location('issuer_cli', path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=FEED if str(request.url) == ISSUER_FEED else DOCUMENT)

    native_client = httpx.Client
    monkeypatch.setattr(cli.httpx, 'Client',
                        lambda **kwargs: native_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(cli, 'source_commit', lambda: 'a' * 40)
    monkeypatch.setattr(IssuerCollector, '_wait', lambda self, seconds: None)
    monkeypatch.setenv('SEC_USER_AGENT', 'Private private@example.invalid')
    config = tmp_path/'config.json'
    config.write_text(json.dumps(asdict(IssuerScope())))
    root = tmp_path/'store'
    assert cli.main(['collect-issuer', '--store', str(root), '--config', str(config),
                     '--run-id', 'cli']) == 0
    assert len(requests) == 2
    assert all(request.headers['User-Agent'] == USER_AGENT for request in requests)
    store = RunStore(root, read_only=True)
    rows = store.query(store.verify()[-1]['finalized_at'])['observations']
    identity = next(item['observation_id'] for item in rows
                    if item['source_kind'] == 'issuer_primary')
    output = tmp_path/'exported'
    assert cli.main(['export', '--store', str(root), '--observation', identity,
                     '--output', str(output)]) == 0
    assert (output/'source.bin').read_bytes() == DOCUMENT
    assert not json.loads((output/'metadata.json').read_bytes())['reviewed_event']


def test_server_cli_keeps_sec_contact_out_and_skips_verified_primary(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'scripts/filing_observations.py'
    spec = importlib.util.spec_from_file_location('issuer_server_cli', path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=FEED if str(request.url) == ISSUER_FEED else DOCUMENT)

    native_client = httpx.Client
    monkeypatch.setattr(cli.httpx, 'Client',
                        lambda **kwargs: native_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(cli, 'source_commit', lambda: 'a' * 40)
    monkeypatch.setattr(IssuerCollector, '_wait', lambda self, seconds: None)
    monkeypatch.setenv('SEC_USER_AGENT', 'Private private@example.invalid')
    config = tmp_path/'config.json'
    config.write_text(json.dumps(asdict(IssuerScope())))
    root = tmp_path/'store'
    for run_id in ('server-' + 'a' * 32, 'server-' + 'b' * 32):
        assert cli.main(['collect-issuer-server', '--store', str(root),
                         '--config', str(config), '--run-id', run_id]) == 0
    assert len(requests) == 3
    assert all(request.headers['User-Agent'] == USER_AGENT for request in requests)
    read_only = RunStore(root, read_only=True)
    assert read_only.verify()[-1]['manifest']['selection']['unchanged'] == 1
    state = cli.server_status(read_only, utc(read_only.verify()[-1]['finalized_at'])
                              + timedelta(minutes=20))
    assert state['source'] == 'server_issuer_observations_only'
    assert state['completed_runs'] == 2
    assert state['attempted_slots_24h'] == 1
    assert state['missing_slots_24h'] == 95
    assert len(state['slots_24h']) == 96
    assert [slot['state'] for slot in state['slots_24h']].count('success') == 1
    assert [slot['state'] for slot in state['slots_24h']].count('missing') == 95
    assert state['backup_status'] == 'not_checked_locally'
    assert cli.main(['collect-issuer-server', '--store', str(root),
                     '--config', str(config), '--run-id', 'actions-wrong']) == 2
    assert len(requests) == 3


def test_server_status_marks_actual_failed_slot_without_backdating(tmp_path):
    path = Path(__file__).resolve().parents[2] / 'scripts/filing_observations.py'
    spec = importlib.util.spec_from_file_location('issuer_status_cli', path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    clock = Clock()
    store = RunStore(tmp_path, clock=clock.utc)
    with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(403))) as client:
        assert not run(store, clock, client, 'server-' + 'a' * 32, reuse=True)['complete']
    status = cli.server_status(store, utc(store.verify()[-1]['finalized_at'])
                               + timedelta(minutes=20))
    assert status['attempted_slots_24h'] == 1
    assert status['within_20_minutes_24h'] == 1
    assert [slot['state'] for slot in status['slots_24h']].count('failed') == 1
    assert [slot['state'] for slot in status['slots_24h']].count('missing') == 95


def test_failed_primary_remains_identifiable_and_not_success(tmp_path):
    clock = Clock()
    store = RunStore(tmp_path, clock=clock.utc)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, content=FEED if str(request.url) == ISSUER_FEED else b'<html>wrong</html>'))
            ) as client:
        result = run(store, clock, client)
    assert not result['complete']
    failure = store.verify()[0]['manifest']['failures'][0]
    assert failure['source_kind'] == 'issuer_primary' and len(failure['accession']) == 64
    assert failure['code'] == 'invalid_response'
