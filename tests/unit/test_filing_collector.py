"""No network or real sleeps: exercise the bounded SEC collection protocol."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from auto_invest.analytics.filing_observations import RunStore
from auto_invest.market_data.filing_collector import Collector, Scope, parse_listing

CIK = "0000789019"
UA = "Research tests@example.invalid"
DOCUMENT = b"""<html><body>UNITED STATES SECURITIES AND EXCHANGE COMMISSION
FORM 8-K CURRENT REPORT MICROSOFT CORPORATION</body></html>"""


class FakeClock:
    def __init__(self):
        self.elapsed = 0.0
        self.waits = []

    def utc(self):
        return (datetime(2026, 9, 28, 12, tzinfo=UTC)
                + timedelta(seconds=self.elapsed)).isoformat().replace("+00:00", "Z")

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.elapsed += seconds


def listing(count=1, **changes):
    value = {"cik": 789019, "name": "MICROSOFT CORP", "filings": {"recent": {
        "accessionNumber": [f"0000789019-26-{i:06}" for i in range(count, 0, -1)],
        "form": ["8-K"] * count,
        "primaryDocument": [f"report{i}.htm" for i in range(count, 0, -1)],
        "filingDate": ["2026-09-28"] * count,
        "reportDate": ["2026-09-28"] * count,
        "acceptanceDateTime": ["2026-09-28T10:00:00Z"] * count,
    }, "files": []}}
    value.update(changes)
    return json.dumps(value).encode()


def collect(tmp_path, handler, scope=None, clock=None, run_id="test-1"):
    clock = clock or FakeClock()
    store = RunStore(tmp_path, clock=clock.utc)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        collector = Collector(store, scope or Scope(), user_agent=UA, client=client,
                              utc_now=clock.utc, monotonic=clock.monotonic, sleep=clock.sleep)
        result = collector.collect(run_id=run_id, source_commit="a" * 40)
    return store, result, clock


def test_success_preserves_received_bytes_and_limits_rate(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=listing() if len(seen) == 1 else DOCUMENT)

    store, result, clock = collect(tmp_path, handler)
    assert result["complete"] is True
    assert len(store.verify()[0]["manifest"]["observations"]) == 2
    assert len(seen) == 2
    assert clock.waits == [1.0]
    assert all(request.headers["User-Agent"] == UA for request in seen)
    assert UA not in repr(store.verify())


def test_bootstrap_reports_unobserved_matching_documents(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=listing(7) if len(calls) == 1 else DOCUMENT)

    store, result, _ = collect(tmp_path, handler)
    assert len(calls) == 6
    assert result["complete"] is False
    assert store.verify()[0]["manifest"]["coverage"]["skipped"] == 2
    assert result["historical_completeness"] == "unknown"


def test_forbidden_opens_persisted_circuit_without_retry(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(403, text=UA)

    clock = FakeClock()
    store, result, _ = collect(tmp_path, handler, clock=clock)
    assert len(calls) == 1 and result["complete"] is False
    assert store.verify()[0]["manifest"]["failures"][0]["code"] == "http_403"
    clock.elapsed += 10
    collect(tmp_path, handler, clock=clock, run_id="test-2")
    assert len(calls) == 1
    assert store.verify()[-1]["manifest"]["failures"][0]["code"] == "cooldown"
    assert UA not in repr(store.verify())


def test_three_failures_open_circuit_with_bounded_backoff(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    store, result, clock = collect(tmp_path, handler)
    assert len(calls) == 3
    assert clock.waits == [1.0, 2.0]
    assert store.verify()[0]["manifest"]["circuit"]["consecutive_failures"] == 3
    assert result["complete"] is False


def test_retry_recovers_but_attempt_failure_remains_evidence(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, content=listing(0))

    store, _, clock = collect(tmp_path, handler)
    assert len(calls) == 2 and clock.waits == [3.0]
    assert store.verify()[0]["manifest"]["failures"][0]["code"] == "http_429"
    assert store.verify()[0]["manifest"]["circuit"]["consecutive_failures"] == 0


@pytest.mark.parametrize("status", [301, 302, 404])
def test_redirect_or_client_error_is_not_followed(tmp_path, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://example.invalid/steal"})

    _, result, _ = collect(tmp_path, handler)
    assert len(calls) == 1 and result["complete"] is False


def test_network_error_never_leaks_exception_headers(tmp_path):
    def handler(request):
        raise httpx.ConnectError(UA, request=request)

    store, result, _ = collect(tmp_path, handler)
    assert result["complete"] is False
    assert UA not in repr(store.verify())


@pytest.mark.parametrize("body", [b"<html>blocked</html>", listing(cik=1), b'{"cik":1,"cik":2}'])
def test_bad_listing_is_failed_not_empty(tmp_path, body):
    store, result, _ = collect(tmp_path, lambda _: httpx.Response(200, content=body))
    manifest = store.verify()[0]["manifest"]
    assert result["complete"] is False
    assert manifest["observations"] == []
    assert manifest["failures"][0]["code"] == "invalid_response"


def test_listing_rejects_misaligned_columns_and_document_traversal():
    for mutate in (
        lambda rows: rows["form"].clear(),
        lambda rows: rows["primaryDocument"].__setitem__(0, "../bad.htm"),
        lambda rows: rows["accessionNumber"].append(rows["accessionNumber"][0]),
    ):
        value = json.loads(listing())
        mutate(value["filings"]["recent"])
        with pytest.raises(ValueError):
            parse_listing(json.dumps(value).encode(), CIK, ("8-K", "8-K/A"))


def test_bad_primary_does_not_erase_successful_listing(tmp_path):
    def handler(request):
        body = listing() if request.url.host == "data.sec.gov" else b"<html>error</html>"
        return httpx.Response(200, content=body)

    store, result, _ = collect(tmp_path, handler)
    assert result["complete"] is False
    assert store.verify()[0]["manifest"]["coverage"] == {"succeeded": 1, "failed": 1, "skipped": 0}
    failure = store.verify()[0]["manifest"]["failures"][0]
    assert failure["source_kind"] == "primary"
    assert failure["accession"] == "0000789019-26-000001"


def test_response_limit_rejects_before_storing(tmp_path):
    scope = Scope(max_bytes=32)
    store, result, _ = collect(tmp_path, lambda _: httpx.Response(200, content=b"x" * 33), scope)
    assert result["complete"] is False
    assert store.verify()[0]["manifest"]["failures"][0]["code"] == "size_limit"


def test_huge_retry_after_stops_without_sleeping_past_budget(tmp_path):
    store, result, clock = collect(
        tmp_path, lambda _: httpx.Response(429, headers={"Retry-After": "9999"}))
    assert result["complete"] is False
    assert not clock.waits
    assert store.verify()[0]["manifest"]["circuit"]["cooldown_until"] is not None


@pytest.mark.parametrize("changes", [
    {"ciks": ("789019",)}, {"forms": ("10-K",)}, {"interval_seconds": 0.1},
    {"max_documents": 6}, {"max_bytes": 0}, {"retries": 3}, {"budget_seconds": 181},
])
def test_scope_cannot_relax_collection_limits(changes):
    with pytest.raises(ValueError):
        Scope(**changes)


def test_circuit_poll_does_not_extend_cooldown_forever(tmp_path):
    clock = FakeClock()

    def handler(_):
        return httpx.Response(503)
    store, _, _ = collect(tmp_path, handler, clock=clock)
    original = store.verify()[-1]["manifest"]["circuit"]["cooldown_until"]
    clock.elapsed += 10
    collect(tmp_path, handler, clock=clock, run_id="test-2")
    assert store.verify()[-1]["manifest"]["circuit"]["cooldown_until"] == original
    clock.elapsed += 901
    calls = []

    def success(request):
        calls.append(request)
        return httpx.Response(200, content=listing(0))

    collect(tmp_path, success, clock=clock, run_id="test-3")
    assert len(calls) == 1
    assert store.verify()[-1]["manifest"]["circuit"]["cooldown_until"] is None


def test_trickling_response_hits_total_budget(tmp_path):
    clock = FakeClock()

    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(100):
                clock.elapsed += 0.8
                yield b"x"

    store, result, _ = collect(tmp_path, lambda _: httpx.Response(200, stream=SlowStream()),
                               scope=Scope(budget_seconds=2), clock=clock)
    assert result["complete"] is False
    assert clock.elapsed < 4
    assert store.verify()[0]["manifest"]["failures"][0]["code"] == "run_budget"


def test_truncated_content_length_rejected(tmp_path):
    store, result, _ = collect(tmp_path, lambda _: httpx.Response(
        200, content=listing(0), headers={"Content-Length": "9999"}))
    assert result["complete"] is False
    assert store.verify()[0]["manifest"]["observations"] == []


def test_wrong_issuer_in_primary_rejected(tmp_path):
    wrong = DOCUMENT.replace(b"MICROSOFT CORPORATION", b"ANOTHER CORPORATION")

    def handler(request):
        body = listing() if request.url.host == "data.sec.gov" else wrong
        return httpx.Response(200, content=body)

    store, result, _ = collect(tmp_path, handler)
    assert result["complete"] is False
    assert store.verify()[0]["manifest"]["coverage"]["succeeded"] == 1


def test_clock_reversal_is_not_persisted_as_valid_run(tmp_path):
    clock = FakeClock()

    def handler(request):
        clock.elapsed = -1
        return httpx.Response(200, content=listing(0))

    with pytest.raises(ValueError, match="clock reversal"):
        collect(tmp_path, handler, clock=clock)
    assert list((tmp_path / "runs").iterdir()) == []


def test_duplicate_run_is_refused_before_network(tmp_path):
    collect(tmp_path, lambda _: httpx.Response(200, content=listing(0)))

    def forbidden(request):
        raise AssertionError("duplicate run performed network access")

    with pytest.raises(ValueError, match="duplicate"):
        collect(tmp_path, forbidden)


def test_scope_round_trip_rejects_unexpected_fields():
    from dataclasses import asdict

    source = json.loads(json.dumps(asdict(Scope())))
    assert Scope.from_dict(source) == Scope()
    source["user_agent"] = UA
    with pytest.raises(ValueError, match="fields"):
        Scope.from_dict(source)


def test_reobserving_same_bytes_retains_both_receipts(tmp_path):
    def handler(request):
        return httpx.Response(200, content=listing(0))

    clock = FakeClock()
    store, _, _ = collect(tmp_path, handler, clock=clock)
    first = store.verify()[0]
    clock.elapsed += 60
    collect(tmp_path, handler, clock=clock, run_id="test-2")
    runs = store.verify()
    assert runs[0] == first
    assert len(list((tmp_path / "blobs").iterdir())) == 1
    assert len(list((tmp_path / "observations").iterdir())) == 2


def test_extreme_retry_after_never_shortens_to_one_day(tmp_path):
    store, result, clock = collect(tmp_path, lambda _: httpx.Response(
        429, headers={"Retry-After": str(10 ** 30)}))
    assert result["complete"] is False and not clock.waits
    assert store.verify()[0]["manifest"]["circuit"]["cooldown_until"].startswith("9999-")
