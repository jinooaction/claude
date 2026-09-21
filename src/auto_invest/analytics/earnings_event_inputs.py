"""Offline, locally observed earnings claims; never a historical publication certificate."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

MAX_BYTES = 10 * 1024 * 1024
DOC_FIELDS = {'id', 'path', 'sha256', 'url', 'source_claims'}
EVENT_FIELDS = {'id', 'event_key', 'issuer_cik', 'kind', 'report_period_end', 'event_date',
                'time_label', 'document_id', 'evidence_quotes', 'supersedes',
                'symbol', 'lineage_status'}
OBSERVATION_FIELDS = {'observed_start', 'observed_end'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _fields(value, fields):
    _require(isinstance(value, dict) and set(value) == fields, 'invalid fields')


def _identifier(value):
    _require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value),
             'invalid identifier')


def _stamp(value):
    _require(isinstance(value, str), 'timestamp string required')
    stamp = datetime.fromisoformat(value)
    _require(stamp.tzinfo is not None and stamp.utcoffset() is not None, 'timezone required')
    return stamp.astimezone(UTC)


def _day(value):
    _require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value),
             'invalid date')
    return date.fromisoformat(value)


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    _require(len(raw) <= MAX_BYTES, 'file too large')
    return raw


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique)


def _strings(values, allow_empty=False):
    _require(isinstance(values, list) and (allow_empty or bool(values))
             and all(isinstance(v, str) and v.strip() for v in values), 'invalid text list')


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _normalize(text):
    return ' '.join(text.split())


def _text(raw):
    parser = _Text()
    parser.feed(raw.decode('utf-8'))
    parser.close()
    return _normalize(' '.join(parser.parts))


def _validate(data, snapshots, observed):
    expected = {'schema_version', 'issuers', 'documents', 'events'}
    _fields(data, expected | ({'previous_sha256'} if observed else set()))
    _require(type(data['schema_version']) is int and data['schema_version'] == 1,
             'invalid schema')
    issuers = data['issuers']
    _strings(issuers)
    _require(len(set(issuers)) == len(issuers)
             and all(re.fullmatch(r'\d{10}', v) for v in issuers), 'invalid issuer scope')
    _require(isinstance(data['documents'], list) and isinstance(data['events'], list),
             'document and event lists required')
    if observed:
        prior = data['previous_sha256']
        _require(prior is None or isinstance(prior, str) and re.fullmatch(r'[0-9a-f]{64}', prior),
                 'invalid previous fingerprint')
    documents, texts = {}, {}
    for doc in data['documents']:
        _fields(doc, DOC_FIELDS | (OBSERVATION_FIELDS if observed else set()))
        _identifier(doc['id'])
        _require(doc['id'] not in documents, 'duplicate document')
        _require(isinstance(doc['path'], str) and bool(doc['path']), 'invalid path')
        _require(isinstance(doc['url'], str), 'invalid source URL')
        url = urlsplit(doc['url'])
        _require(url.scheme == 'https' and url.hostname and not url.username and not url.password,
                 'invalid source URL')
        _strings(doc['source_claims'], allow_empty=True)
        raw = snapshots[doc['id']]
        _require(doc['sha256'] == _hash(raw), 'source fingerprint mismatch')
        if observed:
            _require(doc['path'] == f"documents/{doc['id']}.html", 'invalid bundle path')
            _require(_stamp(doc['observed_start']) <= _stamp(doc['observed_end']),
                     'reversed observation interval')
        documents[doc['id']] = doc
        texts[doc['id']] = _text(raw)
    versions, latest = {}, {}
    for event in data['events']:
        _fields(event, EVENT_FIELDS | ({'verified_at'} if observed else set()))
        for key in ('id', 'event_key', 'document_id'):
            _identifier(event[key])
        _require(event['id'] not in versions, 'duplicate event')
        _require(event['issuer_cik'] in issuers, 'unknown issuer')
        _require(event['kind'] in ('scheduled', 'reported'), 'invalid event kind')
        _require(event['time_label'] in ('date_only', 'before_open', 'after_close', 'unspecified'),
                 'invalid time label')
        _day(event['event_date'])
        if event['report_period_end'] is not None:
            _day(event['report_period_end'])
        _require(event['lineage_status'] in ('verified', 'unverified'), 'invalid lineage status')
        symbol = event['symbol']
        _require(symbol is None or isinstance(symbol, str)
                 and re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,19}', symbol), 'invalid symbol')
        _require(symbol is not None or event['lineage_status'] == 'unverified',
                 'missing verified symbol')
        _require(event['document_id'] in documents, 'missing document')
        _strings(event['evidence_quotes'])
        _require(all(_normalize(q) in texts[event['document_id']]
                     for q in event['evidence_quotes']), 'evidence quote absent')
        if observed:
            _require(_stamp(event['verified_at']) >=
                     _stamp(documents[event['document_id']]['observed_end']),
                     'verification precedes observation')
        key = (event['issuer_cik'], event['event_key'], event['kind'])
        parent = event['supersedes']
        _require(parent is None or isinstance(parent, str), 'invalid parent')
        if parent is None:
            _require(key not in latest, 'duplicate event root')
        else:
            _require(latest.get(key) == parent and parent in versions, 'invalid revision parent')
            if observed:
                _require(_stamp(event['verified_at']) > _stamp(versions[parent]['verified_at']),
                         'revision time not strictly later')
        versions[event['id']] = event
        latest[key] = event['id']


def _load_bundle(directory):
    raw = _read(directory/'manifest.json')
    data = _json(raw)
    _require(isinstance(data, dict) and isinstance(data.get('documents'), list), 'invalid bundle')
    snapshots = {}
    for doc in data['documents']:
        _require(isinstance(doc, dict), 'invalid document')
        _identifier(doc.get('id'))
        _require(doc.get('path') == f"documents/{doc['id']}.html", 'invalid bundle path')
        snapshots[doc['id']] = _read(directory/doc['path'])
    _validate(data, snapshots, observed=True)
    return data, snapshots, _hash(raw)


def import_bundle(path: Path, output: Path, previous: Path | None = None) -> dict:
    """Record present local observation. No option to supply a historical receipt time."""
    if output.exists():
        raise FileExistsError('output already exists')
    data = _json(_read(path))
    _fields(data, {'schema_version', 'issuers', 'documents', 'events'})
    _require(isinstance(data['documents'], list) and isinstance(data['events'], list),
             'lists required')
    snapshots, intervals = {}, {}
    for doc in data['documents']:
        _fields(doc, DOC_FIELDS)
        _identifier(doc['id'])
        _require(doc['id'] not in snapshots, 'duplicate document')
        _require(isinstance(doc['path'], str) and bool(doc['path']), 'invalid path')
        start = datetime.now(UTC)
        snapshots[doc['id']] = _read(path.parent/doc['path'])
        end = datetime.now(UTC)
        _require(start <= end, 'clock moved backwards during observation')
        intervals[doc['id']] = (start.isoformat(), end.isoformat())
    # Check new claims together with old claims, so revisions may name older bundles.
    old, old_snapshots, previous_sha = None, {}, None
    if previous is not None:
        old, old_snapshots, previous_sha = _load_bundle(previous)
        _require(data['issuers'] == old['issuers'], 'issuer scope changed')
        _require(not set(snapshots) & set(old_snapshots), 'duplicate document')
    validation = dict(data)
    if old:
        validation['documents'] = [{k: d[k] for k in DOC_FIELDS} for d in old['documents']]
        validation['documents'] += data['documents']
        validation['events'] = [{k: e[k] for k in EVENT_FIELDS} for e in old['events']]
        validation['events'] += data['events']
    all_snapshots = old_snapshots | snapshots
    _validate(validation, all_snapshots, observed=False)
    verified = datetime.now(UTC).isoformat()
    docs = [dict(d, path=f"documents/{d['id']}.html",
                 observed_start=intervals[d['id']][0], observed_end=intervals[d['id']][1])
            for d in data['documents']]
    events = [dict(e, verified_at=verified) for e in data['events']]
    bundle = {'schema_version': 1, 'issuers': data['issuers'],
              'documents': (old['documents'] if old else []) + docs,
              'events': (old['events'] if old else []) + events,
              'previous_sha256': previous_sha}
    _validate(bundle, all_snapshots, observed=True)
    if old:
        old_times = [e['verified_at'] for e in old['events']]
        old_times += [d['observed_end'] for d in old['documents']]
        _require(all(_stamp(verified) > _stamp(t) for t in old_times),
                 'clock must advance beyond previous bundle')
    serialized = (json.dumps(bundle, indent=2, sort_keys=True)+'\n').encode('utf-8')
    _require(len(serialized) <= MAX_BYTES, 'serialized bundle too large')
    output.mkdir(parents=True, exist_ok=False)
    (output/'documents').mkdir()
    for doc in bundle['documents']:
        with (output/doc['path']).open('xb') as handle:
            handle.write(all_snapshots[doc['id']])
    with (output/'manifest.json').open('xb') as handle:
        handle.write(serialized)
    return {'documents': len(bundle['documents']), 'events': len(bundle['events']),
            'verified_at': verified, 'local_observation_only': True,
            'source_authenticity_verified': False, 'live_eligible': False}


def query_bundle(directory: Path, as_of: str) -> dict:
    at = _stamp(as_of)
    data, _, digest = _load_bundle(directory)
    docs = {d['id']: d for d in data['documents']}
    selected = {}
    for event in data['events']:
        doc = docs[event['document_id']]
        available = max(_stamp(event['verified_at']), _stamp(doc['observed_end']))
        if available <= at:
            key = (event['issuer_cik'], event['event_key'], event['kind'])
            selected[key] = dict(event, available_at=available.isoformat(),
                                 observation_available=True,
                                 evidence_semantics='manually_reviewed_claim',
                                 source_url=doc['url'], source_sha256=doc['sha256'],
                                 source_claims=doc['source_claims'])
    return {'schema_version': 1, 'as_of': at.isoformat(), 'bundle_sha256': digest,
            'events': [selected[k] for k in sorted(selected)],
            'coverage_unknown_issuers': data['issuers'],
            'local_observation_only': True, 'source_authenticity_verified': False,
            'live_eligible': False, 'strategy_admitted': False, 'orders_submitted': 0}
