import copy
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import respx

from auto_invest.analytics.intraday_paper_challenger import load_preregistration
from auto_invest.analytics.intraday_runtime import PaperRuntime
from auto_invest.market_data import intraday_attestation as a
from auto_invest.market_data.intraday import KIS_BARS, KIS_BASE, ReadTransport, iso

NOW = datetime(2026, 9, 8, 13, 35, 1, tzinfo=UTC)


def script(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[2] / "scripts" / (name + ".py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("change", [None, "bar", "time", "signature", "key", "code", "shape"])
def test_proof_binds_bars_clock_code_and_key(monkeypatch, change):
    monkeypatch.setattr(a, "_read_key", lambda: b"k" * 32)
    bars = {"SPY": {"volume": 100}}
    proof = a._seal(bars, NOW - timedelta(seconds=5), NOW, b"k" * 32)
    if change == "bar":
        bars["SPY"]["volume"] += 1
    if change == "time":
        proof = a._seal(bars, NOW, NOW + timedelta(seconds=1), b"k" * 32)
    if change == "signature":
        proof["signature"] = "0" * 64
    if change == "key":
        monkeypatch.setattr(a, "_read_key", lambda: b"z" * 32)
    if change == "code":
        monkeypatch.setattr(a, "_collector_digest", lambda: "changed")
    if change == "shape":
        proof["payload"]["operator_approved"] = True
    before = copy.deepcopy(proof)
    if change:
        with pytest.raises(a.DataError, match="COLLECTION_ATTESTATION_INVALID"):
            a.verify_collection(proof, bars, NOW)
    else:
        assert a.verify_collection(proof, bars, NOW)
    assert proof == before


def test_key_missing_public_or_link_refused(tmp_path, monkeypatch):
    key = tmp_path / "key"
    monkeypatch.setattr(a, "KEY_PATH", key)
    with pytest.raises(a.DataError, match="COLLECTION_KEY_UNAVAILABLE"):
        a._read_key()
    key.write_bytes(b"k" * 32)
    key.chmod(0o666)
    with pytest.raises(a.DataError, match="COLLECTION_KEY_INVALID"):
        a._read_key()
    link = tmp_path / "link"
    link.symlink_to(key)
    monkeypatch.setattr(a, "KEY_PATH", link)
    with pytest.raises(a.DataError, match="COLLECTION_KEY_UNAVAILABLE"):
        a._read_key()


@pytest.mark.asyncio
async def test_real_collector_to_persisted_group(tmp_path, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(a, "datetime", Clock)
    monkeypatch.setattr(a, "_read_key", lambda: b"k" * 32)
    monkeypatch.setattr(a, "ReadTransport", lambda client: ReadTransport(client, interval=0))
    seen = []

    def response(request):
        seen.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx.Response(200, json=dict(rt_cd="0", output2=[dict(
            xymd="20260908", xhms="093000", open="100", high="101", low="99",
            last="100", evol="100000",
        )]))

    with respx.mock(assert_all_called=True) as router:
        router.post(KIS_BASE + "/oauth2/tokenP").respond(
            200, json=dict(access_token="test-token", expires_in=86400),
        )
        router.get(KIS_BARS).mock(side_effect=response)
        batch = await a.collect_attested_kis(
            dict(KIS_APP_KEY="private-key", KIS_APP_SECRET="private-secret"),
            NOW.replace(minute=30, second=0), NOW, tmp_path / "token.json",
        )
    assert len(seen) == 5
    proof = batch["collection_proofs"]["2026-09-08T13:30:00Z"]
    path = tmp_path / "paper.db"
    config = load_preregistration(Path(
        "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"
    ))
    runtime = PaperRuntime(path, config, batch["provider"], False, "forward")
    try:
        script("intraday_runtime")._apply(
            runtime, batch["bars"], observed=NOW, collection_proofs=batch["collection_proofs"],
        )
    finally:
        runtime.close()
    runtime = PaperRuntime(path, config, batch["provider"], False, "forward")
    try:
        payload = json.loads(runtime.conn.execute(
            "SELECT payload FROM intraday_events").fetchone()[0])
        assert payload["collection_proof"] == proof
        assert a.verify_collection(payload["collection_proof"], payload["bars"], NOW)
        assert "private-key" not in json.dumps(payload)
        assert payload["observed"] == iso(NOW)
    finally:
        runtime.close()


@pytest.mark.asyncio
async def test_operator_flag_reaches_collector(tmp_path, monkeypatch):
    monkeypatch.setenv("KIS_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_APP_SECRET", "test-secret")
    operator = script("intraday_operator")
    runtime = script("intraday_runtime")
    captured = []

    async def collect(env, start, end, cache):
        captured.append((start, end, cache))
        return {"proof": "test-routing"}

    async def cycle(args):
        result = await runtime._collect(args, object(), NOW,
                                        NOW - timedelta(minutes=5), NOW)
        assert result == {"proof": "test-routing"}
        return dict(status="WAIT_SESSION", orders_submitted=0, live_eligible=False)

    monkeypatch.setattr(runtime, "collect_attested_kis", collect)
    monkeypatch.setattr(operator, "runtime_execute", lambda: cycle)
    await operator.execute(SimpleNamespace(
        command="run", root=tmp_path / "operator", poll_seconds=60, cycles=1,
        token_cache=tmp_path / "token", attest_market_data=True,
    ))
    assert captured == [(NOW - timedelta(minutes=5), NOW, tmp_path / "token")]
