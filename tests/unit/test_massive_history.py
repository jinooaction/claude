import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from auto_invest.market_data.intraday import CALENDAR, DataError
from auto_invest.market_data.massive_history import acquire_and_review

KEY = "test_key_never_persist_1234567890"
NOW = datetime(2026, 9, 14, tzinfo=UTC)


def response(symbol, day="2026-09-11"):
    opening = CALENDAR.session_open(day).to_pydatetime()
    close = CALENDAR.session_close(day).to_pydatetime()
    rows = [dict(t=int((opening + timedelta(minutes=i * 5)).timestamp() * 1000),
                 o=100, h=102, l=99, c=101, v=1000)
            for i in range(int((close - opening).total_seconds() / 300))]
    return dict(status="OK", ticker=symbol, adjusted=False, resultsCount=len(rows), results=rows)


async def run(tmp_path, handler, **options):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await acquire_and_review(start=options.pop("start", "2026-09-11"),
            end="2026-09-11", output=tmp_path / "job", api_key=options.pop("key", KEY),
            client=client, now=NOW, interval=0, **options)


@pytest.mark.asyncio
async def test_real_format_reaches_independent_research_and_resume_preserves_source(tmp_path):
    calls = []

    def handler(request):
        assert request.method == "GET" and request.url.host == "api.massive.com"
        assert request.headers["Authorization"] == "Bearer " + KEY
        assert request.url.params["adjusted"] == "false"
        assert "apiKey" not in request.url.params
        calls.append(request.url)
        return httpx.Response(200, json=response(request.url.path.split("/")[4]))

    result = await run(tmp_path, handler)
    assert result["complete_sessions"] == 1 and result["independent_evidence_valid"] is True
    assert result["decision"]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert result["provider"] == "massive-sip-unadjusted" and result["live_eligible"] is False
    assert len(calls) == 5
    files = {p: p.read_bytes() for p in (tmp_path / "job/pages").glob("*.json")}
    second = await run(tmp_path, handler)
    assert second["complete_sessions"] == 1 and len(calls) == 5
    assert all(p.read_bytes() == raw and KEY.encode() not in raw for p, raw in files.items())
    assert len(list((tmp_path / "job").glob("research-*"))) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["ticker", "adjusted", "next_url", "count", "volume", "range"])
async def test_bad_supplier_results_never_create_completed_research(tmp_path, change):
    def handler(request):
        body = response(request.url.path.split("/")[4])
        if change == "ticker":
            body["ticker"] = "OTHER"
        elif change == "adjusted":
            body["adjusted"] = True
        elif change == "next_url":
            body["next_url"] = "https://other.invalid/leak"
        elif change == "count":
            body["resultsCount"] += 1
        elif change == "volume":
            body["results"][0]["v"] = 0.5
        else:
            body = response(body["ticker"], "2026-09-10")
        return httpx.Response(200, json=body)

    with pytest.raises(DataError):
        await run(tmp_path, handler)
    assert not list((tmp_path / "job").glob("research-*/completed.json"))


@pytest.mark.asyncio
async def test_missing_key_makes_no_output_or_request(tmp_path):
    def handler(request):
        pytest.fail("No network without key")

    with pytest.raises(DataError, match="API_KEY_REQUIRED"):
        await run(tmp_path, handler, key=None)
    assert not (tmp_path / "job").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 401, 403])
async def test_auth_redirect_and_error_bodies_are_not_exposed(tmp_path, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": KEY},
                              headers={"Location": "https://other.invalid/leak"})

    with pytest.raises(DataError, match=f"HISTORY_HTTP_{status}") as exc:
        await run(tmp_path, handler)
    assert KEY not in str(exc.value) and len(calls) == 1
    assert not list((tmp_path / "job/pages").glob("*.json"))


@pytest.mark.asyncio
async def test_missing_calendar_day_stays_missing_not_filled(tmp_path):
    def handler(request):
        return httpx.Response(200, json=response(request.url.path.split("/")[4]))

    result = await run(tmp_path, handler, start="2026-09-10")
    assert result["requested_sessions"] == 2 and result["missing_sessions"] == 1
    assert result["decision"]["passed"] is False


@pytest.mark.asyncio
async def test_cache_corruption_is_not_overwritten(tmp_path):
    def handler(request):
        return httpx.Response(200, json=response(request.url.path.split("/")[4]))

    await run(tmp_path, handler)
    page = next((tmp_path / "job/pages").glob("*.json"))
    record = json.loads(page.read_bytes())
    record["response"]["results"][0]["c"] = 100
    page.write_text(json.dumps(record))
    with pytest.raises(DataError, match="CACHE_INVALID"):
        await run(tmp_path, handler)
    assert json.loads(page.read_bytes())["response"]["results"][0]["c"] == 100


@pytest.mark.asyncio
async def test_longer_range_is_chunked_without_following_pagination(tmp_path):
    calls = []

    def handler(request):
        pieces = request.url.path.split("/")
        left, right = datetime.fromisoformat(pieces[-2]), datetime.fromisoformat(pieces[-1])
        assert (right - left).days <= 13
        calls.append(request.url)
        return httpx.Response(200, json=response(pieces[4], pieces[-1]))

    result = await run(tmp_path, handler, start="2026-08-15")
    assert len(calls) == 10 and result["complete_sessions"] == 2
    assert result["missing_sessions"] > 0 and result["decision"]["passed"] is False


@pytest.mark.asyncio
async def test_credential_reflection_is_rejected_before_persistence(tmp_path):
    def handler(request):
        return httpx.Response(200, json=dict(response(request.url.path.split("/")[4]), echoed=KEY))

    with pytest.raises(DataError, match="RESPONSE_REJECTED"):
        await run(tmp_path, handler)
    assert not list((tmp_path / "job/pages").glob("*.json"))


@pytest.mark.asyncio
async def test_output_link_and_changed_request_are_refused(tmp_path):
    def handler(request):
        return httpx.Response(200, json=response(request.url.path.split("/")[4]))

    await run(tmp_path, handler)
    with pytest.raises(DataError, match="EXISTING_DATA_CHANGED"):
        await run(tmp_path, handler, start="2026-09-10")
    (tmp_path / "job").rename(tmp_path / "original")
    (tmp_path / "job").symlink_to(tmp_path / "original", target_is_directory=True)
    with pytest.raises(DataError, match="LINK_DENIED"):
        await run(tmp_path, handler)
