"""Research access is bounded, private, and never trading authority."""

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import httpx
import pytest

from auto_invest.market_data.hf_research import (
    Collector,
    restore_state,
    stage_output,
    wall_timeout,
    write_json,
)

NOW = datetime(2026, 10, 2, 14, tzinfo=UTC)
KEY = "test_private_key_0123456789"


class Clock:
    def __init__(self):
        self.elapsed = 0.0

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds

    def utcnow(self):
        return NOW + timedelta(seconds=self.elapsed)


def history(previous=None, attempt=1):
    return {"schema_version": 1, "run_attempt": attempt, "previous": previous}


def previous(seconds=1000):
    return {"id": 17, "status": "completed",
            "updated_at": (NOW - timedelta(seconds=seconds)).isoformat()}


def catalogue():
    return {"count": 2, "symbols": [
        {"ticker": ticker, "size_bytes": 1000, "last_modified": NOW.isoformat()}
        for ticker in ("AMZN", "NVDA")]}


def run(tmp_path, handler, key=KEY, state=None, proof=None, **kwargs):
    clock = Clock()
    collector = Collector(tmp_path / "new", proof or history(), state,
                          clock=clock, transport=httpx.MockTransport(handler), **kwargs)
    result = collector.run(key)
    return result, clock, json.loads((tmp_path / "new" / "circuit-state.json").read_text())


@pytest.fixture
def parquet(tmp_path):
    output = tmp_path / "fixture.parquet"
    with duckdb.connect() as connection:
        connection.execute("COPY (SELECT TIMESTAMP '2020-01-02 09:30:00' AS datetime, "
                           "1.0::DOUBLE AS Open, 1.0::DOUBLE AS High, 1.0::DOUBLE AS Low, "
                           "1.0::DOUBLE AS Close, 1::BIGINT AS Volume, "
                           "'pitrading' AS source) TO ? (FORMAT PARQUET)", [str(output)])
    return output.read_bytes()


def test_missing_key_public_only_first_delay(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        assert "x-api-key" not in request.headers
        return httpx.Response(200, json=catalogue())

    result, clock, _ = run(tmp_path, handler, key="")
    assert result["result"] == "MISSING_KEY"
    assert len(calls) == 1 and clock.elapsed >= 1
    assert result["live_eligible"] is False and result["orders_submitted"] == 0
    assert (tmp_path / "new" / "catalogue.json").exists()


def test_complete_fixed_raw_and_exact_bytes(tmp_path, parquet):
    paths = []

    def handler(request):
        paths.append(str(request.url))
        if request.url.path.endswith("symbols"):
            return httpx.Response(200, json=catalogue())
        assert request.headers["x-api-key"] == KEY
        assert request.url.params["version"] == "raw"
        return httpx.Response(200, content=parquet,
                              headers={"content-type": "application/octet-stream"})

    result, clock, _ = run(tmp_path, handler)
    assert result["result"] == "COMPLETE" and len(paths) == 3
    assert clock.elapsed >= 3
    assert (tmp_path / "new" / "AMZN.parquet").read_bytes() == parquet
    assert result["files"]["NVDA"]["rows"] == 1
    assert result["returns_evaluated"] is False


@pytest.mark.parametrize("status", [301, 401, 403, 404])
def test_permanent_failure_stops_remaining_symbols(tmp_path, status):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("symbols"):
            return httpx.Response(200, json=catalogue())
        return httpx.Response(status, text=KEY,
                              headers={"location": "https://elsewhere.invalid/"})

    result, _, state = run(tmp_path, handler)
    assert result["result"] != "COMPLETE" and len(calls) == 2
    assert state["raw"]["failures"] == 3
    assert KEY not in json.dumps(result)
    assert not list((tmp_path / "new").glob("*.parquet"))


def test_raw_failures_survive_catalogue_success(tmp_path):
    state, _ = restore_state(history(), None, NOW)
    state["raw"]["failures"] = 2
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return (httpx.Response(200, json=catalogue()) if request.url.path.endswith("symbols")
                else httpx.Response(503))

    result, _, final = run(tmp_path, handler, state=state, proof=history(previous()))
    assert len(calls) == 2 and final["raw"]["failures"] == 3
    assert result["result"] != "COMPLETE"
    restored, _ = restore_state(history(previous(0)), final, NOW + timedelta(seconds=3))
    assert datetime.fromisoformat(restored["raw"]["blocked_until"]) > NOW


@pytest.mark.parametrize("proof,state", [
    (history(previous(10)), None),
    (history(previous(10)), {"malformed": True}),
    (history(previous(), attempt=2), None),
    (history({"id": 17, "status": "in_progress", "updated_at": NOW.isoformat()}), None),
])
def test_uncertain_history_makes_no_requests(tmp_path, proof, state):
    def handler(request):
        pytest.fail("history uncertainty cannot issue HTTP")

    result, _, _ = run(tmp_path, handler, proof=proof, state=state)
    assert result["result"] in {"HISTORY_COOLDOWN", "HISTORY_UNVERIFIED"}


def test_lost_old_state_is_half_open_not_fresh():
    state, reason = restore_state(history(previous()), None, NOW)
    assert reason == "RECOVERED_UNKNOWN_HISTORY"
    assert state["raw"]["failures"] == 3
    assert datetime.fromisoformat(state["raw"]["blocked_until"]) <= NOW


@pytest.mark.parametrize("value", ["3600", "Fri, 02 Oct 2026 16:00:00 GMT"])
def test_retry_after_no_early_request(tmp_path, value):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"retry-after": value})

    result, clock, final = run(tmp_path, handler)
    assert len(calls) == 1 and clock.elapsed < 180
    assert datetime.fromisoformat(final["catalogue"]["blocked_until"]) >= NOW + timedelta(hours=1)
    assert result["result"] == "RATE_LIMIT_DEFERRED"


@pytest.mark.parametrize("kind", ["length", "oversize", "json", "reflected"])
def test_bad_raw_never_completed(tmp_path, parquet, kind):
    def handler(request):
        if request.url.path.endswith("symbols"):
            return httpx.Response(200, json=catalogue())
        data = KEY.encode() + parquet if kind == "reflected" else parquet
        if kind == "json":
            return httpx.Response(200, json={"error": KEY})
        headers = {"content-type": "application/octet-stream"}
        if kind == "length":
            headers["content-length"] = str(len(data) + 1)
        return httpx.Response(200, content=data, headers=headers)

    limit = 10 if kind == "oversize" else 128 * 1024 * 1024
    result, _, _ = run(tmp_path, handler, raw_limit=limit)
    assert result["result"] != "COMPLETE"
    assert KEY.encode() not in b"".join(p.read_bytes() for p in (tmp_path / "new").iterdir())
    assert not list((tmp_path / "new").glob("*.partial"))


def test_actual_wall_timeout_interrupts_drip():
    started = time.monotonic()
    with pytest.raises(TimeoutError), wall_timeout(0.025):
        while True:
            time.sleep(0.01)
    assert time.monotonic() - started < 0.5


def test_existing_output_never_rewritten(tmp_path):
    (tmp_path / "new").mkdir()
    (tmp_path / "new" / "original").write_text("keep")
    with pytest.raises(ValueError):
        run(tmp_path, lambda request: httpx.Response(503))
    assert (tmp_path / "new" / "original").read_text() == "keep"


def test_finalization_failure_has_no_completion_marker(tmp_path, monkeypatch):
    import auto_invest.market_data.hf_research as module

    def failed_fsync(descriptor):
        raise OSError(KEY)

    monkeypatch.setattr(module.os, "fsync", failed_fsync)
    with pytest.raises(OSError):
        write_json(tmp_path / "manifest.json", {"result": "COMPLETE"})
    assert not list(tmp_path.iterdir())


def test_artifact_stage_rehashes_and_refuses_tamper(tmp_path):
    run(tmp_path, lambda request: httpx.Response(200, json=catalogue()), key="")
    source = tmp_path / "new"
    stage_output(source, tmp_path / "verified")
    assert (tmp_path / "verified" / "catalogue.json").read_bytes() == (
        source / "catalogue.json").read_bytes()
    (source / "catalogue.json").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        stage_output(source, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def test_unlisted_or_cancelled_file_cannot_be_uploaded(tmp_path):
    run(tmp_path, lambda request: httpx.Response(200, json=catalogue()), key="")
    (tmp_path / "new" / "NVDA.parquet.partial").write_bytes(KEY.encode())
    with pytest.raises(ValueError):
        stage_output(tmp_path / "new", tmp_path / "artifact")
    assert not (tmp_path / "artifact").exists()


@pytest.mark.parametrize("field,value", [
    ("result", "COMPLETE"), ("result", KEY), ("source_commit", KEY),
    ("returns_evaluated", True), ("source_parity_verified", True), ("live_eligible", True),
])
def test_tampered_authority_or_private_metadata_cannot_be_uploaded(tmp_path, field, value):
    run(tmp_path, lambda request: httpx.Response(200, json=catalogue()), key="")
    path = tmp_path / "new" / "manifest.json"
    changed = json.loads(path.read_text())
    changed[field] = value
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError):
        stage_output(tmp_path / "new", tmp_path / "artifact")
    assert not (tmp_path / "artifact").exists()


def test_key_split_at_stream_chunk_boundary_never_saved(tmp_path, parquet):
    reflected = b"x" * (64 * 1024 - 4) + KEY.encode() + parquet

    def handler(request):
        if request.url.path.endswith("symbols"):
            return httpx.Response(200, json=catalogue())
        return httpx.Response(200, content=reflected,
                              headers={"content-type": "application/octet-stream"})

    result, _, _ = run(tmp_path, handler)
    assert result["result"] == "PRIVATE_RESPONSE_REJECTED"
    assert KEY.encode() not in b"".join(p.read_bytes() for p in (tmp_path / "new").iterdir())


def test_client_does_not_trust_proxy_or_redirects(tmp_path, monkeypatch):
    import auto_invest.market_data.hf_research as module

    original = module.httpx.Client
    options = []

    def client(**kwargs):
        options.append(kwargs)
        return original(**kwargs)

    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted.invalid:1234")
    monkeypatch.setattr(module.httpx, "Client", client)
    run(tmp_path, lambda request: httpx.Response(200, json=catalogue()), key="")
    assert options[0]["trust_env"] is False
    assert options[0]["follow_redirects"] is False and options[0]["verify"] is True


def test_partial_real_files_remain_partial(tmp_path, parquet):
    def handler(request):
        if request.url.path.endswith("symbols"):
            return httpx.Response(200, json=catalogue())
        if request.url.path.endswith("AMZN"):
            return httpx.Response(200, content=parquet,
                                  headers={"content-type": "application/octet-stream"})
        return httpx.Response(403, text=KEY)

    result, _, _ = run(tmp_path, handler)
    assert result["result"] == "HTTP_ACCESS_REFUSED"
    assert set(result["files"]) == {"catalogue", "AMZN"}
    stage_output(tmp_path / "new", tmp_path / "artifact")
    assert not (tmp_path / "artifact" / "NVDA.parquet").exists()


def test_symlink_output_and_unverified_first_history_refused(tmp_path):
    (tmp_path / "target").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "target", target_is_directory=True)
    with pytest.raises(ValueError):
        Collector(tmp_path / "link" / "new", history(), None)
    with pytest.raises(ValueError):
        restore_state({"schema_version": 1, "run_attempt": 1}, None, NOW)


def test_slow_byte_stream_has_actual_request_deadline(tmp_path, monkeypatch):
    import auto_invest.market_data.hf_research as module

    original = module.wall_timeout
    monkeypatch.setattr(module, "wall_timeout", lambda seconds: original(
        0.025 if seconds <= 20 else seconds))

    class Drip(httpx.SyncByteStream):
        def __iter__(self):
            while True:
                time.sleep(0.01)
                yield b"P"

    def handler(request):
        if request.url.path.endswith("symbols"):
            return httpx.Response(200, json=catalogue())
        return httpx.Response(200, stream=Drip(),
                              headers={"content-type": "application/octet-stream"})

    started = time.monotonic()
    result, _, final = run(tmp_path, handler)
    assert result["result"] == "NETWORK_OR_TIMEOUT" and final["raw"]["failures"] == 3
    assert time.monotonic() - started < 1


def test_workflow_is_manual_private_serial_and_preserves_history():
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/collect-hf-research.yml").read_text()
    assert "workflow_dispatch:" in workflow and "schedule:" not in workflow
    assert "cancel-in-progress: false" in workflow
    assert "secrets.HF_DATA_API_KEY" in workflow
    assert "listWorkflowRuns" in workflow and "status: 'success'" not in workflow
    assert "SEC_USER_AGENT" not in workflow and "VULTR_SSH" not in workflow
