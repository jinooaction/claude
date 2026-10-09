import copy
import fcntl
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_collection_record import (
    DETAILS,
    project_collection,
    read_recorded_status,
    unavailable_collection,
    validate_collection,
)
from auto_invest.analytics.intraday_diagnostic_receipt import build_receipt
from auto_invest.analytics.intraday_timing import project_timing

IDENTITY = "a" * 64
NOW = datetime(2026, 10, 6, 16, 58, 9, 171898, tzinfo=UTC)
STAMP = "2026-10-06T16:50:00Z"
OBSERVED = "2026-10-06T16:55:34Z"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def hashed(value):
    return "sha256:" + hashlib.sha256(encoded(value)).hexdigest()


def inputs():
    bars = {s: dict(symbol=s, timestamp_utc=STAMP, open=100.0, high=101.0,
                    low=99.0, close=100.2, volume=100000)
            for s in ("SPY", "QQQ", "IWM", "TLT", "GLD")}
    proof = dict(payload=dict(schema=1, scope="kis-server-collection",
                             collector_digest="sha256:" + "b" * 64, bars_digest=hashed(bars),
                             started_at="2026-10-06T16:54:50Z",
                             received_at="2026-10-06T16:55:12Z"), signature="c" * 64)
    event = dict(timestamp=STAMP, observed=OBSERVED, state=dict(last_bar=STAMP), bars=bars,
                 bar_digest=hashed(bars), collection_proof=proof,
                 actions=[{"PRIVATE_ACCOUNT": "SECRET_VALUE"}])
    status = dict(identity=IDENTITY, last_bar=STAMP, processed_bars=1,
                  observed_at_utc=NOW.isoformat())
    return event, status


def projected(event, status):
    result = project_collection(event, status, hashed(["genesis", event]))
    status = dict(status, timing=project_timing(event, status, hashed(["genesis", event])))
    assert validate_collection(result, status) == result
    return result


def store(tmp_path, event=None):
    original, status = inputs()
    event = original if event is None else event
    epoch = tmp_path / IDENTITY
    epoch.mkdir()
    (tmp_path / "service.lock").touch()
    path = epoch / "paper.db"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=181")
        conn.execute("CREATE TABLE intraday_meta(identity TEXT)")
        conn.execute("INSERT INTO intraday_meta VALUES(?)", (json.dumps(dict(
            mode="forward", synthetic=False, provider="kis-nasdaq-partial-unadjusted")),))
        conn.execute("CREATE TABLE intraday_events(id INTEGER PRIMARY KEY, timestamp TEXT, "
                     "previous_hash TEXT, hash TEXT, payload TEXT)")
        conn.execute("INSERT INTO intraday_events VALUES(1,?,?,?,?)",
                     (event["timestamp"], "genesis", hashed(["genesis", event]), encoded(event)))
    return path, status


def test_original_start_return_and_observation_are_distinct_without_authentication():
    event, status = inputs()
    original = copy.deepcopy(event)
    result = projected(event, status)
    assert result["status"] == "RECORDED_UNAUTHENTICATED"
    assert result["collection_started_at_utc"] == "2026-10-06T16:54:50Z"
    assert result["collection_returned_at_utc"] == "2026-10-06T16:55:12Z"
    assert result["collection_duration_seconds"] == 22
    assert result["return_to_observation_seconds"] == 22
    assert result["authentication_verified"] is False
    assert result["completion_time_assessed"] is False
    assert result["provider_publication_assessed"] is False
    assert event == original and len(encoded(result)) < 4096
    for private in ("PRIVATE", "SECRET_VALUE", '"bars"', '"signature"', "c" * 64):
        assert private not in json.dumps(result)


@pytest.mark.parametrize("seconds", [0, 1, 60])
def test_collection_duration_boundaries(seconds):
    event, status = inputs()
    from datetime import timedelta

    event["collection_proof"]["payload"]["started_at"] = (
        datetime(2026, 10, 6, 16, 55, 12, tzinfo=UTC) - timedelta(seconds=seconds)).isoformat()
    assert projected(event, status)["collection_duration_seconds"] == seconds


def test_absent_proof_is_distinct_from_explicit_invalid_null():
    event, status = inputs()
    event.pop("collection_proof")
    result = projected(event, status)
    assert result["reason"] == "PROOF_ABSENT"
    assert all(result[key] is None for key in DETAILS)
    event["collection_proof"] = None
    assert projected(event, status)["reason"] == "PROOF_INVALID"


@pytest.mark.parametrize("field,value", [
    ("schema", True), ("schema", 2), ("scope", "broker-signed"),
    ("collector_digest", "masked"), ("collector_digest", None),
    ("bars_digest", "sha256:" + "d" * 64),
    ("started_at", None), ("started_at", True), ("started_at", "bad"),
    ("started_at", "2026-10-06T16:54:11Z"),
    ("started_at", "2026-10-06T16:55:13Z"),
    ("started_at", "2026-10-06T16:54:50"),
    ("started_at", "2026-10-06T16:54:50+09:00"),
    ("received_at", "2026-10-06T16:54:59Z"),
    ("received_at", "2026-10-06T16:55:35Z"), ("received_at", None),
    ("extra", "SECRET_VALUE"),
])
def test_malformed_payload_never_exposes_or_substitutes_times(field, value):
    event, status = inputs()
    event["collection_proof"]["payload"][field] = value
    assert projected(event, status)["reason"] == "PROOF_INVALID"


@pytest.mark.parametrize("signature", [None, False, "masked", "c" * 63, "C" * 64,
                                      "secret@example.com"])
def test_invalid_signature_format_is_not_authentication(signature):
    event, status = inputs()
    event["collection_proof"]["signature"] = signature
    assert projected(event, status)["reason"] == "PROOF_INVALID"


@pytest.mark.parametrize("failure", ["missing_symbol", "foreign_symbol", "symbol_label",
                                    "different_bar", "extra_field", "bad_ohlc", "zero_volume",
                                    "bool_volume", "string_price", "bool_price", "event_digest"])
def test_same_event_and_complete_group_are_required(failure):
    event, status = inputs()
    bars = event["bars"]
    if failure == "missing_symbol":
        bars.pop("GLD")
    elif failure == "foreign_symbol":
        bars["OTHER"] = bars.pop("GLD")
    elif failure == "event_digest":
        event["bar_digest"] = "sha256:" + "e" * 64
    else:
        key, value = {
            "symbol_label": ("symbol", "IWM"),
            "different_bar": ("timestamp_utc", "2026-10-06T16:45:00Z"),
            "extra_field": ("PRIVATE_PRICE", 99), "bad_ohlc": ("low", 200.0),
            "zero_volume": ("volume", 0), "bool_volume": ("volume", True),
            "string_price": ("open", "100"), "bool_price": ("open", True),
        }[failure]
        bars["SPY"][key] = value
    # Even an internally matching updated digest cannot repair wrong group/time fields.
    event["collection_proof"]["payload"]["bars_digest"] = hashed(bars)
    if failure != "event_digest":
        event["bar_digest"] = hashed(bars)
    assert projected(event, status)["reason"] == "PROOF_INVALID"


@pytest.mark.parametrize("field,value", [
    ("schema", True), ("scope", "REAL_ACCOUNT"), ("integrity_scope", "FULL_AUDIT"),
    ("authentication_verified", True), ("authentication_verified", 0),
    ("authority_assessed", True), ("completion_time_assessed", True),
    ("provider_publication_assessed", True), ("status", "PASS"), ("reason", "SECRET_VALUE"),
    ("bar_start_utc", "2026-10-06T16:45:00Z"),
    ("model_bar_end_utc", "2026-10-06T16:54:00Z"),
    ("runtime_observed_at_utc", "2026-10-06T16:55:33Z"),
    ("collection_returned_at_utc", "2026-10-06T16:55:35Z"),
    ("collection_duration_seconds", True), ("collection_duration_seconds", 21),
    ("return_to_observation_seconds", float("nan")),
    ("event_hash", "sha256:" + "e" * 64), ("PRIVATE", "SECRET_VALUE"),
])
def test_projection_cannot_promote_authenticate_or_change_link(field, value):
    event, status = inputs()
    result = projected(event, status)
    status["timing"] = project_timing(event, status, hashed(["genesis", event]))
    result[field] = value
    with pytest.raises(ValueError):
        validate_collection(result, status)


def test_shared_read_keeps_status_prices_keys_files_and_lock_unchanged(tmp_path, monkeypatch):
    import auto_invest.market_data.intraday_attestation as attestation

    def forbidden(*args, **kwargs):
        raise AssertionError("must not read key, issue or verify HMAC")
    monkeypatch.setattr(attestation, "_read_key", forbidden)
    monkeypatch.setattr(attestation, "verify_collection", forbidden)
    monkeypatch.setattr(attestation, "collect_attested_kis", forbidden)
    path, status = store(tmp_path)
    original, files = path.read_bytes(), set(tmp_path.rglob("*"))
    def reader(root, now):
        with (root / "service.lock").open("rb") as handle, pytest.raises(BlockingIOError):
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert now == NOW
        return status
    result = read_recorded_status(tmp_path, NOW, reader)
    assert result["timing"]["status"] == "RECORDED"
    assert result["collection_record"]["status"] == "RECORDED_UNAUTHENTICATED"
    assert {k: v for k, v in result.items() if k not in {"timing", "collection_record"}} == status
    assert "collection_record" not in status and path.read_bytes() == original
    assert set(tmp_path.rglob("*")) == files


@pytest.mark.parametrize("failure", ["lock", "wal", "hash", "meta", "missing", "empty"])
def test_reader_failures_preserve_nulls_and_same_reason(tmp_path, failure):
    path, status = store(tmp_path)
    if failure == "wal":
        path.with_name("paper.db-wal").touch()
    elif failure == "missing":
        path.unlink()
    elif failure == "empty":
        status["last_bar"] = None
    elif failure in {"hash", "meta"}:
        with sqlite3.connect(path) as conn:
            if failure == "hash":
                conn.execute("UPDATE intraday_events SET hash='wrong'")
            else:
                conn.execute("UPDATE intraday_meta SET identity='{}'")
    with (tmp_path / "service.lock").open("rb") as handle:
        if failure == "lock":
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = read_recorded_status(tmp_path, NOW, lambda root, now: status)
    assert result["timing"]["status"] == result["collection_record"]["status"] == "UNAVAILABLE"
    assert result["timing"]["reason"] == result["collection_record"]["reason"]
    assert all(result["collection_record"][key] is None for key in DETAILS)
    assert validate_collection(result["collection_record"], result) == result["collection_record"]


def test_invalid_proof_does_not_hide_valid_timing(tmp_path):
    event, _ = inputs()
    event["collection_proof"]["signature"] = "wrong"
    _, status = store(tmp_path, event)
    result = read_recorded_status(tmp_path, NOW, lambda root, now: status)
    assert result["timing"]["runtime_observation_lag_seconds"] == 34
    assert result["collection_record"]["reason"] == "PROOF_INVALID"


@pytest.mark.parametrize("initial_proof", [False, True])
def test_real_runtime_recollection_cannot_replace_first_processing(tmp_path, initial_proof):
    from auto_invest.analytics.intraday_paper_challenger import load_preregistration
    from auto_invest.analytics.intraday_runtime import PaperRuntime

    event, _ = inputs()
    epoch = tmp_path / IDENTITY
    epoch.mkdir()
    (tmp_path / "service.lock").touch()
    path = epoch / "paper.db"
    config = load_preregistration(Path(
        "specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json"))
    runtime = PaperRuntime(path, config, "kis-nasdaq-partial-unadjusted", False, "forward")
    try:
        kwargs = dict(collection_proof=event["collection_proof"]) if initial_proof else {}
        assert runtime.process(list(event["bars"].values()), datetime.fromisoformat(OBSERVED),
                               **kwargs) is True
        original = runtime.conn.execute("SELECT payload FROM intraday_events").fetchone()[0]
        later = copy.deepcopy(event["collection_proof"])
        later["payload"].update(started_at="2026-10-06T16:57:00Z",
                                received_at="2026-10-06T16:57:20Z")
        assert runtime.process(list(event["bars"].values()), NOW, collection_proof=later) is False
        assert runtime.conn.execute("SELECT payload FROM intraday_events").fetchone()[0] == original
        status = dict(runtime.status(), identity=IDENTITY, observed_at_utc=NOW.isoformat())
    finally:
        runtime.close()
    result = read_recorded_status(tmp_path, NOW, lambda root, now: status)
    if initial_proof:
        assert result["collection_record"]["collection_returned_at_utc"] == "2026-10-06T16:55:12Z"
    else:
        assert result["collection_record"]["reason"] == "PROOF_ABSENT"
    assert result["timing"]["runtime_observed_at_utc"] == OBSERVED


@pytest.mark.parametrize("proof_present", [False, True])
def test_original_collection_projection_survives_price_free_receipt(tmp_path, proof_present):
    event, _ = inputs()
    if not proof_present:
        event.pop("collection_proof")
    _, status = store(tmp_path, event)
    status.update(schema_version="1.1", scope="DIAGNOSTIC_PAPER_SERVICE",
                  program_readiness="NOT_ASSESSED", status="DIAGNOSTIC_PAPER",
                  age_seconds=0, orders_submitted=0, qualified_forward_sessions=0,
                  live_eligible=False, forward_promotion_eligible=False,
                  blockers=["DIAGNOSTIC_PAPER_ONLY"], simulated_fills=0,
                  open_quantity=0, halt_reasons=[])
    result = read_recorded_status(tmp_path, NOW, lambda root, now: status)
    raw = ("INTRADAY_TIMER=active\nINTRADAY_SERVICE_RESULT=success\n"
           + "INTRADAY_PRODUCTION_COMMIT=" + "b" * 40 + "\n" + json.dumps(result))
    receipt = build_receipt(raw, source_sha="b" * 40, run_id="123", identity=IDENTITY, captured=NOW)
    assert receipt["diagnostic"]["collection_record"] == result["collection_record"]
    assert "PRIVATE" not in json.dumps(receipt) and "signature" not in json.dumps(receipt)
    result["collection_record"]["authentication_verified"] = True
    with pytest.raises(ValueError):
        build_receipt(raw.rsplit("\n", 1)[0] + "\n" + json.dumps(result), source_sha="b" * 40,
                      run_id="123", identity=IDENTITY, captured=NOW)


def test_absent_record_cannot_supply_fake_times_or_absence_with_failed_timing():
    event, status = inputs()
    status["timing"] = project_timing(event, status, hashed(["genesis", event]))
    value = unavailable_collection("PROOF_ABSENT")
    value["collection_started_at_utc"] = STAMP
    with pytest.raises(ValueError):
        validate_collection(value, status)
    from auto_invest.analytics.intraday_timing import unavailable

    status["timing"] = unavailable("READER_BUSY")
    with pytest.raises(ValueError):
        validate_collection(unavailable_collection("PROOF_ABSENT"), status)


def test_late_runtime_observation_is_not_hidden_by_valid_collection():
    event, status = inputs()
    event["observed"] = "2026-10-06T16:56:31Z"
    result = projected(event, status)
    assert result["return_to_observation_seconds"] == 79
    timing = project_timing(event, status, hashed(["genesis", event]))
    assert timing["runtime_observation_within_90s"] is False
    assert result["authentication_verified"] is False


@pytest.mark.parametrize("proof", [[], {"payload": {}},
                                   {"payload": {}, "signature": "x" * 4097}])
def test_partial_or_oversized_proof_is_bounded_and_unavailable(proof):
    event, status = inputs()
    event["collection_proof"] = proof
    assert projected(event, status)["reason"] == "PROOF_INVALID"


def test_fixed_cli_uses_combined_read_without_new_arguments(monkeypatch, capsys):
    import runpy
    import sys

    import auto_invest.analytics.intraday_collection_record as records

    calls = []
    def fake(root, now, reader):
        calls.append((str(root), now, reader.__name__))
        return dict(collection_record=unavailable_collection("PROOF_ABSENT"))
    monkeypatch.setattr(records, "read_recorded_status", fake)
    monkeypatch.setattr(sys, "argv", ["intraday_timing_status.py", "service-status"])
    runpy.run_path("scripts/intraday_timing_status.py", run_name="__main__")
    assert calls[0][0] == "/var/lib/auto-invest-intraday"
    assert calls[0][2] == "read_service_status" and len(calls) == 1
    assert json.loads(capsys.readouterr().out)["collection_record"]["reason"] == "PROOF_ABSENT"
