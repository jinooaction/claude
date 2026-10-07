import copy
import fcntl
import hashlib
import json
import sqlite3
import subprocess
import sys
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_timing import (
    project_timing,
    read_timed_status,
    read_timing,
    unavailable,
    validate_timing,
)

NOW = datetime(2026, 10, 6, 16, 58, 9, 171898, tzinfo=UTC)
IDENTITY = "a" * 64


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def hashed(value):
    return "sha256:" + hashlib.sha256(encoded(value)).hexdigest()


def inputs(lag=34):
    observed = "2026-10-06T16:55:34Z" if lag == 34 else "2026-10-06T16:56:31Z"
    event = dict(timestamp="2026-10-06T16:50:00Z", observed=observed,
                 state=dict(last_bar="2026-10-06T16:50:00Z"),
                 bars={"PRIVATE_PRICE": 789}, actions=[{"PRIVATE_ACCOUNT": 123}])
    status = dict(identity=IDENTITY, last_bar=event["timestamp"], processed_bars=1,
                  observed_at_utc=NOW.isoformat())
    return event, status


def store(tmp_path):
    event, status = inputs()
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
    return path, event, status


def test_original_observation_is_not_publication_or_completion():
    event, status = inputs()
    original = copy.deepcopy(event)
    result = project_timing(event, status, hashed(["genesis", event]))
    assert result["runtime_observation_lag_seconds"] == 34
    assert result["status_publication_lag_seconds"] == 189.171898
    assert result["runtime_observation_within_90s"] is True
    assert result["completion_time_assessed"] is False
    assert result["collection_times_assessed"] is False
    assert result["authority_assessed"] is False
    assert event == original
    assert "PRIVATE" not in json.dumps(result)
    assert validate_timing(result, status) == result


@pytest.mark.parametrize("reason", ["RECORD_UNAVAILABLE", "READER_BUSY", "NO_RECORDED_BAR"])
def test_unavailable_preserves_unknown_values(reason):
    result = unavailable(reason)
    assert validate_timing(result, {}) == result
    result["runtime_observed_at_utc"] = NOW.isoformat()
    with pytest.raises(ValueError):
        validate_timing(result, {})


def test_status_wrapper_keeps_original_status_and_shared_writer_lock(tmp_path):
    path, event, status = store(tmp_path)
    original = copy.deepcopy(status)
    def reader(root, now):
        with (root / "service.lock").open("rb") as handle, pytest.raises(BlockingIOError):
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert now == NOW
        return status
    result = read_timed_status(tmp_path, NOW, reader)
    assert result["timing"]["status"] == "RECORDED"
    assert status == original
    assert {k: v for k, v in result.items() if k != "timing"} == status


@pytest.mark.parametrize("failure", ["wal", "shm", "empty", "extra_table", "meta_duplicate",
                                    "meta_size", "duplicate_json", "nonfinite", "broken_link"])
def test_database_format_and_local_link_boundaries(tmp_path, failure):
    path, event, status = store(tmp_path)
    if failure in {"wal", "shm"}:
        path.with_name("paper.db-" + failure).touch()
    else:
        with sqlite3.connect(path) as conn:
            if failure == "empty":
                conn.execute("DELETE FROM intraday_events")
            elif failure == "extra_table":
                conn.execute("CREATE TABLE unexpected(data)")
            elif failure == "meta_duplicate":
                conn.execute("INSERT INTO intraday_meta SELECT * FROM intraday_meta")
            elif failure == "meta_size":
                conn.execute("UPDATE intraday_meta SET identity=?", ("x" * 16385,))
            elif failure == "duplicate_json":
                conn.execute('UPDATE intraday_meta SET identity=?',
                             ('{"mode":"forward","mode":"replay"}',))
            elif failure == "nonfinite":
                conn.execute('UPDATE intraday_events SET payload=?', ('{"price":NaN}',))
            else:
                second = copy.deepcopy(event)
                second.update(timestamp="2026-10-06T16:55:00Z",
                              observed="2026-10-06T17:00:00Z")
                second["state"]["last_bar"] = second["timestamp"]
                conn.execute("INSERT INTO intraday_events VALUES(2,?,?,?,?)",
                             (second["timestamp"], "wrong", hashed(["wrong", second]),
                              encoded(second)))
                status.update(last_bar=second["timestamp"], processed_bars=2,
                              observed_at_utc="2026-10-06T17:01:00Z")
    assert read_timing(tmp_path, status)["status"] == "UNAVAILABLE"


def test_valid_second_record_has_only_local_link_scope(tmp_path):
    path, event, status = store(tmp_path)
    with sqlite3.connect(path) as conn:
        previous = hashed(["genesis", event])
        event.update(timestamp="2026-10-06T16:55:00Z", observed="2026-10-06T17:00:00Z")
        event["state"]["last_bar"] = event["timestamp"]
        conn.execute("INSERT INTO intraday_events VALUES(2,?,?,?,?)",
                     (event["timestamp"], previous, hashed([previous, event]), encoded(event)))
    status.update(last_bar=event["timestamp"], processed_bars=2,
                  observed_at_utc="2026-10-06T17:01:00Z")
    result = read_timing(tmp_path, status)
    assert result["status"] == "RECORDED"
    assert result["source_integrity_scope"] == "LATEST_RECORD_LOCAL_LINK"


@pytest.mark.parametrize("column", ["hash", "previous_hash", "timestamp"])
def test_sqlite_itself_bounds_corrupt_metadata_columns(tmp_path, column):
    path, event, status = store(tmp_path)
    with sqlite3.connect(path) as conn:
        conn.execute(f"UPDATE intraday_events SET {column}=?", ("x" * (1024 * 1024 + 16385),))
    tracemalloc.start()
    try:
        result = read_timing(tmp_path, status)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 512 * 1024
    assert result["status"] == "UNAVAILABLE"
    assert result["event_hash"] is None


def test_timing_is_preserved_in_existing_price_free_receipt():
    from auto_invest.analytics.intraday_diagnostic_receipt import build_receipt

    event, status = inputs()
    status.update(schema_version="1.1", scope="DIAGNOSTIC_PAPER_SERVICE",
                  program_readiness="NOT_ASSESSED", status="DIAGNOSTIC_PAPER",
                  age_seconds=0, orders_submitted=0, qualified_forward_sessions=0,
                  live_eligible=False, forward_promotion_eligible=False,
                  blockers=["DIAGNOSTIC_PAPER_ONLY"], simulated_fills=0,
                  open_quantity=0, halt_reasons=[])
    status["timing"] = project_timing(event, status, hashed(["genesis", event]))
    raw = ("INTRADAY_TIMER=active\nINTRADAY_SERVICE_RESULT=success\n"
           + "INTRADAY_PRODUCTION_COMMIT=" + "b" * 40 + "\n" + json.dumps(status))
    result = build_receipt(raw, source_sha="b" * 40, run_id="123", identity=IDENTITY,
                           captured=NOW)
    assert result["diagnostic"]["timing"] == status["timing"]
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("installed", [False, True])
def test_fixed_helper_preserves_pre_checkout_fallback(tmp_path, installed):
    source = Path("deploy/observe-on-instance.sh").read_text()
    body = source.split("intraday-paper-status)", 1)[1].split(";;", 1)[0]
    (tmp_path / "scripts").mkdir()
    if installed:
        (tmp_path / "scripts/intraday_timing_status.py").touch()
    script = ('set -e\nAPP_USER=test\nrequire_repo() { :; }\n'
              'systemctl() { :; }\nsudo() { printf "%s " "$@"; printf "\\n"; }\n'
              + body)
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0
    name = "intraday_timing_status.py" if installed else "intraday_runtime.py"
    assert "scripts/" + name + " service-status" in result.stdout
    assert " start " not in result.stdout


@pytest.mark.parametrize("args", [["bad"], ["service-status", "extra"],
                                  ["service-status", "--root", "/tmp"]])
def test_fixed_wrapper_denies_paths_and_extra_arguments(args):
    result = subprocess.run([sys.executable, "scripts/intraday_timing_status.py", *args],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ""


def test_late_runtime_observation_survives_fresh_publication():
    event, status = inputs(91)
    result = project_timing(event, status, hashed(["genesis", event]))
    assert result["runtime_observation_lag_seconds"] == 91
    assert result["runtime_observation_within_90s"] is False


@pytest.mark.parametrize("stamp", [None, True, "bad", "2026-10-06T16:54:59Z",
                                  "2026-10-06T16:59:00Z", "2026-10-06T16:55:34",
                                  "2026-10-06T16:55:34+09:00"])
def test_invalid_runtime_observation_is_rejected(stamp):
    event, status = inputs()
    event["observed"] = stamp
    with pytest.raises(ValueError):
        project_timing(event, status, hashed(["genesis", event]))


@pytest.mark.parametrize("field,value", [
    ("schema", True), ("scope", "REAL_ACCOUNT"), ("authority_assessed", True),
    ("collection_times_assessed", True), ("completion_time_assessed", True),
    ("provider_publication_assessed", True), ("source_integrity_scope", "FULL_AUDIT"),
    ("runtime_observation_lag_seconds", 35), ("status_publication_lag_seconds", 2),
    ("runtime_observation_within_90s", 1), ("event_hash", "masked"),
    ("bar_start_utc", "2026-10-06T16:45:00Z"),
    ("model_bar_end_utc", "2026-10-06T16:54:00Z"),
    ("status_published_at_utc", "2026-10-06T16:59:00Z"),
    ("runtime_observed_at_utc", "2026-10-06T16:59:00Z"),
    ("reason", "PRIVATE_SECRET"), ("status", "PASSED_STRATEGY"),
])
def test_report_cannot_claim_more_than_original_records(field, value):
    event, status = inputs()
    result = project_timing(event, status, hashed(["genesis", event]))
    result[field] = value
    with pytest.raises(ValueError):
        validate_timing(result, status)


def test_read_only_original_database_and_files_are_unchanged(tmp_path):
    path, event, status = store(tmp_path)
    before = path.read_bytes()
    files = set(tmp_path.rglob("*"))
    assert read_timing(tmp_path, status)["status"] == "RECORDED"
    assert read_timing(tmp_path, status)["runtime_observation_lag_seconds"] == 34
    assert path.read_bytes() == before
    assert set(tmp_path.rglob("*")) == files


@pytest.mark.parametrize("failure", ["hash", "previous", "version", "mode", "synthetic",
                                    "provider", "timestamp", "observed", "last", "count",
                                    "identity", "size", "symlink", "lock", "missing"])
def test_original_evidence_failures_never_produce_guessed_times(tmp_path, failure):
    path, event, status = store(tmp_path)
    if failure in {"hash", "previous", "timestamp", "observed", "size"}:
        with sqlite3.connect(path) as conn:
            if failure == "hash":
                conn.execute("UPDATE intraday_events SET hash='bad'")
            elif failure == "previous":
                conn.execute("UPDATE intraday_events SET previous_hash='wrong'")
            elif failure == "timestamp":
                conn.execute("UPDATE intraday_events SET timestamp='wrong'")
            else:
                event["observed"] = "2099-01-01T00:00:00Z"
                if failure == "size":
                    event["extra"] = "x" * (1024 * 1024)
                conn.execute("UPDATE intraday_events SET payload=?, hash=?",
                             (encoded(event), hashed(["genesis", event])))
    elif failure in {"mode", "synthetic", "provider", "version"}:
        with sqlite3.connect(path) as conn:
            if failure == "version":
                conn.execute("PRAGMA user_version=99")
            else:
                meta = dict(mode="forward", synthetic=False,
                            provider="kis-nasdaq-partial-unadjusted")
                meta[failure] = {"mode": "replay", "synthetic": True, "provider": "other"}[failure]
                conn.execute("UPDATE intraday_meta SET identity=?", (json.dumps(meta),))
    elif failure == "last":
        status["last_bar"] = "2026-10-06T16:45:00Z"
    elif failure == "count":
        status["processed_bars"] = 2
    elif failure == "identity":
        status["identity"] = "../escape"
    elif failure == "symlink":
        other = path.with_name("original.db")
        path.rename(other)
        path.symlink_to(other)
    elif failure == "missing":
        path.unlink()
    if failure == "lock":
        with (tmp_path / "service.lock").open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = read_timing(tmp_path, status)
    else:
        result = read_timing(tmp_path, status)
    assert result["status"] == "UNAVAILABLE"
    assert result["runtime_observed_at_utc"] is None
    assert result["event_hash"] is None
    assert result["authority_assessed"] is False
    assert "PRIVATE" not in json.dumps(result)
