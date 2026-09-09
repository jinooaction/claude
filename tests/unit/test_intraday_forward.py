import json
import sqlite3
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from auto_invest.analytics.intraday_paper_challenger import (
    build_candidate_registry,
    load_preregistration,
)
from auto_invest.analytics.intraday_runtime import PaperRuntime, _verify, encode
from auto_invest.execution.intraday_forward import assess_forward
from auto_invest.execution.intraday_selection import ResearchSelection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import CALENDAR, SYMBOLS, DataError, digest, iso

PREREG = Path("specs/177-intraday-paper-challenger/contracts/intraday-preregistration.json")
PROVIDER = "kis-nasdaq-partial-unadjusted"
OPEN = CALENDAR.session_open("2026-09-08").to_pydatetime()
CLOSE = CALENDAR.session_close("2026-09-08").to_pydatetime()


def selection():
    candidate = build_candidate_registry(load_preregistration(PREREG))[-1]
    return ResearchSelection(candidate, PROVIDER, "a" * 40, "fixture", "fixture",
                             execution_fingerprint(candidate, PROVIDER),
                             "PAPER_CHALLENGER", 756, 0)


def make_log(path, *, count=78, mode="forward", synthetic=False, delay=0):
    runtime = PaperRuntime(path, load_preregistration(PREREG), PROVIDER, synthetic, mode)
    try:
        for n in range(count):
            stamp = OPEN + timedelta(minutes=5 * n)
            bars = [dict(symbol=s, timestamp_utc=iso(stamp), open=100, high=101,
                         low=99, close=100, volume=100000) for s in SYMBOLS]
            runtime.process(bars, stamp + timedelta(minutes=5, seconds=delay))
    finally:
        runtime.close()


def check(path, **kwargs):
    return assess_forward(path, selection(), PREREG,
                          frozen_at=kwargs.get("frozen_at", OPEN),
                          now=kwargs.get("now", CLOSE + timedelta(minutes=5)))


def test_complete_session_replays_and_preserves_original(tmp_path):
    path = tmp_path / "paper.db"
    make_log(path)
    before = path.read_bytes()
    result = check(path)
    assert result["complete_sessions"] == 1
    assert result["missing_sessions"] == 59
    assert result["replayed_events"] == 78
    assert result["invalid_sessions"] == 0
    assert result["live_eligible"] is False
    assert result["freeze_authentication_verified"] is False
    assert result["execution_parity_verified"] is False
    assert path.read_bytes() == before
    assert check(path, frozen_at=CLOSE)["complete_sessions"] == 0


@pytest.mark.parametrize("mode,synthetic", [("replay", False), ("forward", True)])
def test_diagnostic_identity_cannot_become_forward_evidence(tmp_path, mode, synthetic):
    path = tmp_path / "paper.db"
    make_log(path, count=1, mode=mode, synthetic=synthetic)
    with pytest.raises(DataError, match="FORWARD_SOURCE_IDENTITY_INVALID"):
        check(path)


def test_partial_and_late_days_are_not_complete(tmp_path):
    path = tmp_path / "partial.db"
    make_log(path, count=1)
    assert check(path)["invalid_sessions"] == 1
    assert check(path, now=OPEN + timedelta(minutes=5))["partial_sessions"] == 1
    with pytest.raises(DataError, match="FORWARD_OBSERVATION_IN_FUTURE"):
        check(path, now=OPEN)
    late = tmp_path / "late.db"
    make_log(late, delay=91)
    result = check(late)
    assert result["complete_sessions"] == 0
    assert result["invalid_sessions"] == 1


def test_rehashed_forged_state_fails_independent_replay(tmp_path):
    path = tmp_path / "forged.db"
    make_log(path, count=1)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
            conn.execute('DROP TRIGGER "' + row[0].replace('"', '""') + '"')
        row = conn.execute("SELECT * FROM intraday_events").fetchone()
        payload = json.loads(row["payload"])
        account = next(iter(payload["state"]["accounts"].values()))
        account["cash"] += 1
        conn.execute("UPDATE intraday_events SET payload=?, hash=?",
                     (encode(payload).decode(), digest(encode(["genesis", payload]))))
        _verify(conn)
    with pytest.raises(DataError, match="FORWARD_REPLAY_MISMATCH"):
        check(path)


def test_missing_source_is_not_created_and_naive_time_is_rejected(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(DataError, match="STATE_NOT_INITIALIZED"):
        check(path)
    assert not path.exists()
    with pytest.raises(DataError, match="FORWARD_TIME_INVALID"):
        check(path, frozen_at=OPEN.replace(tzinfo=None))


def test_unaccepted_selection_future_freeze_and_invalid_schema(tmp_path):
    path = tmp_path / "foreign.db"
    with pytest.raises(DataError, match="FORWARD_SELECTION_INVALID"):
        assess_forward(path, replace(selection(), verdict="NO_EDGE"), PREREG,
                       frozen_at=OPEN, now=CLOSE)
    with pytest.raises(DataError, match="FORWARD_FREEZE_IN_FUTURE"):
        check(path, frozen_at=CLOSE + timedelta(days=1))
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=181")
    with pytest.raises(DataError, match="^FORWARD_LOG_INVALID$"):
        check(path)


def test_symlink_source_is_rejected(tmp_path):
    path = tmp_path / "original.db"
    make_log(path, count=1)
    link = tmp_path / "link.db"
    link.symlink_to(path)
    with pytest.raises(DataError):
        check(link)
