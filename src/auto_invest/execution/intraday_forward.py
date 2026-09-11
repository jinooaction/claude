"""Independent forward-log replay; does not authenticate a freeze or grant authority."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_invest.analytics.intraday_paper_challenger import load_preregistration
from auto_invest.analytics.intraday_runtime import PaperRuntime, _connect, _verify
from auto_invest.execution.intraday_selection import ResearchSelection
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import CALENDAR, NY, DataError, iso, utc
from auto_invest.market_data.intraday_attestation import verify_collection


def assess_forward(database: Path, selection: ResearchSelection, preregistration: Path,
                   *, frozen_at, now, include_interval_bars=False):
    """The launching integration must authenticate frozen_at separately.

    This function establishes log consistency and temporal coverage, not that an
    editable file or caller-supplied timestamp is a genuine prior registration.
    """
    if (not isinstance(selection, ResearchSelection) or selection.candidate is None
            or selection.verdict != "PAPER_CHALLENGER"
            or selection.provider != "kis-nasdaq-partial-unadjusted"
            or selection.execution_identity != execution_fingerprint(
                selection.candidate, selection.provider,
            )):
        raise DataError("FORWARD_SELECTION_INVALID")
    if any(not isinstance(t, datetime) or t.utcoffset() is None for t in (frozen_at, now)):
        raise DataError("FORWARD_TIME_INVALID")
    frozen, clock = utc(iso(frozen_at)), utc(iso(now))
    if frozen > clock:
        raise DataError("FORWARD_FREEZE_IN_FUTURE")
    config = load_preregistration(preregistration)
    required = config["forward_observation"]["required_sessions"]
    with TemporaryDirectory(prefix="intraday-forward-check-") as directory:
        snapshot = sqlite3.connect(Path(directory) / "snapshot.db")
        source = None
        replay = None
        try:
            source = _connect(database, readonly=True)
            source.backup(snapshot)
            source.close()
            source = None
            snapshot.row_factory = sqlite3.Row
            _verify(snapshot)
            identities = snapshot.execute("SELECT identity FROM intraday_meta").fetchall()
            replay = PaperRuntime(Path(directory) / "replay.db", config,
                                  selection.provider, False, "forward")
            if len(identities) != 1 or json.loads(identities[0][0]) != replay.identity:
                raise DataError("FORWARD_SOURCE_IDENTITY_INVALID")
            registry = {c.candidate_id: c for c in replay.candidates}
            candidate = registry.get(selection.candidate.candidate_id)
            if candidate is None or candidate.as_dict() != selection.candidate.as_dict():
                raise DataError("FORWARD_REGISTRATION_MISMATCH")
            sessions = {}
            interval_bars = []
            count = 0
            for row in snapshot.execute("SELECT * FROM intraday_events ORDER BY id"):
                count += 1
                if count > 160000 or row["id"] != count:
                    raise DataError("FORWARD_EVENT_SEQUENCE_INVALID")
                payload = json.loads(row["payload"])
                observed, stamp = utc(payload["observed"]), utc(payload["timestamp"])
                if observed > clock:
                    raise DataError("FORWARD_OBSERVATION_IN_FUTURE")
                proof = payload.get("collection_proof")
                replay.process(list(payload["bars"].values()), observed, collection_proof=proof)
                actual = replay.conn.execute(
                    "SELECT hash FROM intraday_events ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if actual[0] != row["hash"]:
                    raise DataError("FORWARD_REPLAY_MISMATCH")
                session = stamp.astimezone(NY).date()
                opening = CALENDAR.session_open(str(session)).to_pydatetime()
                closing = CALENDAR.session_close(str(session)).to_pydatetime()
                # Existing diagnostic history can precede registration; it is
                # replayed for integrity but never counted as forward evidence.
                if opening < frozen:
                    continue
                if include_interval_bars:
                    interval_bars.extend(payload["bars"].values())
                entry = sessions.setdefault(session, dict(
                    stamps=[], bad=False, closed=False, source_verified=True,
                ))
                entry["source_verified"] &= bool(
                    proof is not None and verify_collection(proof, payload["bars"], observed)
                )
                entry["stamps"].append(stamp)
                state = payload["state"]
                account = state["accounts"][candidate.candidate_id]
                entry["bad"] |= bool(
                    not 0 <= (observed - stamp - timedelta(minutes=5)).total_seconds() <= 90
                    or state["halt_reasons"] or account["halt_reasons"]
                )
                if stamp + timedelta(minutes=5) == closing:
                    entry["closed"] = (
                        not any(account["positions"].values()) and not account["pending"]
                    )
            complete, invalid, partial = [], [], []
            for session, entry in sorted(sessions.items()):
                opening = CALENDAR.session_open(str(session)).to_pydatetime()
                closing = CALENDAR.session_close(str(session)).to_pydatetime()
                expected = [opening + timedelta(minutes=5 * i)
                            for i in range(int((closing - opening).total_seconds() // 300))]
                if closing > clock:
                    partial.append(str(session))
                elif entry["bad"] or not entry["closed"] or entry["stamps"] != expected:
                    invalid.append(str(session))
                else:
                    complete.append(str(session))
            result = dict(
                status="FORWARD_LOG_REPLAYED", replayed_events=count,
                complete_sessions=len(complete), invalid_sessions=len(invalid),
                partial_sessions=len(partial), required_sessions=required,
                missing_sessions=max(0, required - len(complete)),
                session_dates=complete, invalid_session_dates=invalid,
                minimum_observation_count_met=len(complete) >= required,
                freeze_authentication_verified=False, execution_parity_verified=False,
                live_eligible=False, orders_submitted=0,
                market_source_authentication_verified=bool(complete) and all(
                    entry["source_verified"] for session, entry in sessions.items()
                    if str(session) in complete
                ),
            )
            if include_interval_bars:
                complete_dates = set(complete)
                result["_interval_bars_json"] = json.dumps([
                    bar for bar in interval_bars
                    if str(utc(bar["timestamp_utc"]).astimezone(NY).date()) in complete_dates
                ], sort_keys=True, separators=(",", ":"), allow_nan=False)
            return result
        except (sqlite3.Error, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
            raise DataError("FORWARD_LOG_INVALID") from exc
        finally:
            if source is not None:
                source.close()
            if replay is not None:
                replay.close()
            snapshot.close()
