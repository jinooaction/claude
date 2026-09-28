"""Company releases retain a distinct, fixed source contract."""

import hashlib
from uuid import uuid4

import pytest

from auto_invest.analytics.filing_observations import Observation
from auto_invest.market_data.issuer_filings import parse_feed, validate_release

URL = 'https://news.microsoft.com/source/2026/07/29/microsoft-quarter-results/'
TITLE = 'Microsoft quarter results'


def feed(url=URL, title=TITLE, published='Wed, 29 Jul 2026 20:25:10 +0000'):
    return (f'<rss version="2.0"><channel><link>https://news.microsoft.com/source/'
            f'tag/press-releases/</link><item><title>{title}</title><link>{url}</link>'
            f'<pubDate>{published}</pubDate></item></channel></rss>').encode()


def receipt(**changes):
    value = dict(observation_id=str(uuid4()), issuer_cik='0000789019',
                 accession=hashlib.sha256(URL.encode()).hexdigest(),
                 source_kind='issuer_primary', url=URL, blob_sha256='a' * 64,
                 requested_at='2026-09-29T00:00:00Z', received_at='2026-09-29T00:00:01Z',
                 verified_at='2026-09-29T00:00:02Z', source_claims={
                     'title': TITLE, 'published_at': '2026-07-29T20:25:10Z'})
    value.update(changes)
    return Observation(**value)


def test_official_feed_and_receipt_preserve_source_claim_only():
    selected, ignored = parse_feed(feed())
    assert ignored == 0 and len(selected) == 1
    assert selected[0]['url'] == URL
    assert selected[0]['published_at'] == '2026-07-29T20:25:10Z'
    assert receipt().available_at == '2026-09-29T00:00:02Z'


@pytest.mark.parametrize('url', [
    'https://evil.example/source/2026/07/29/microsoft-quarter-results/',
    URL + '?redirect=evil', URL.replace('/07/29/', '/02/30/'),
    URL.replace('news.microsoft.com', 'news.microsoft.com.evil.example'),
])
def test_noncanonical_source_addresses_fail(url):
    with pytest.raises(ValueError):
        parse_feed(feed(url=url))
    with pytest.raises(ValueError):
        receipt(url=url, accession=hashlib.sha256(url.encode()).hexdigest())


@pytest.mark.parametrize('changes', [
    {'issuer_cik': '0000320193'}, {'accession': '0000789019-26-000001'},
    {'source_claims': {'acceptance_datetime': 'old SEC claim'}},
])
def test_company_receipt_cannot_impersonate_sec_or_another_issuer(changes):
    with pytest.raises(ValueError):
        receipt(**changes)


def test_duplicates_unsafe_xml_invalid_time_and_wrong_channel_rejected():
    item = feed().split(b'<item>')[1].split(b'</item>')[0]
    bad = [b'<!DOCTYPE rss>' + feed(), feed().replace(b'</channel>', b'<item>' + item
           + b'</item></channel>'), feed(published='yesterday'),
           feed().replace(b'tag/press-releases/', b'tag/unrelated/')]
    for raw in bad:
        with pytest.raises(ValueError):
            parse_feed(raw)


def test_unselected_press_release_is_counted_not_called_earnings():
    selected, ignored = parse_feed(feed(title='Microsoft announces a donation'))
    assert selected == [] and ignored == 1


def test_release_must_contain_visible_matching_title_and_complete_html():
    validate_release(f'<html><h1>{TITLE}</h1></html>'.encode(), TITLE)
    for raw in [b'<html>Wrong company</html>',
                f'<html><script>{TITLE}</script></html>'.encode(),
                f'<html><h1>{TITLE}</h1>'.encode()]:
        with pytest.raises(ValueError):
            validate_release(raw, TITLE)
