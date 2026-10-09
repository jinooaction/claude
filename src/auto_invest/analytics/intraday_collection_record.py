"""Stored collection fields linked locally; never HMAC verification or authority."""

from __future__ import annotations

import math
import re

from auto_invest.analytics.intraday_timing import (
    _encoded,
    _hash,
    _read_timing,
    _utc,
    project_timing,
    require,
    timing_lock,
    unavailable,
    validate_timing,
)

BASE = dict(schema=1, scope="DIAGNOSTIC_COLLECTION_RECORD",
            integrity_scope="LATEST_RECORD_LOCAL_LINK", authentication_verified=False,
            authority_assessed=False, completion_time_assessed=False,
            provider_publication_assessed=False)
DETAILS = ("bar_start_utc", "model_bar_end_utc", "runtime_observed_at_utc",
           "collection_started_at_utc", "collection_returned_at_utc",
           "collection_duration_seconds", "return_to_observation_seconds", "event_hash")
REASONS = {"PROOF_ABSENT", "PROOF_INVALID", "RECORD_UNAVAILABLE", "READER_BUSY",
           "NO_RECORDED_BAR"}
SYMBOLS = {"SPY", "QQQ", "IWM", "TLT", "GLD"}


def unavailable_collection(reason="RECORD_UNAVAILABLE"):
    require(reason in REASONS)
    return dict(BASE, status="UNAVAILABLE", reason=reason,
                **{key: None for key in DETAILS})


def _fields(timing, started_text, returned_text):
    start, returned, observed, end = map(_utc, (
        started_text, returned_text, timing["runtime_observed_at_utc"],
        timing["model_bar_end_utc"],
    ))
    duration = (returned - start).total_seconds()
    require(start <= returned <= observed and end <= returned and 0 <= duration <= 60)
    return dict(BASE, status="RECORDED_UNAUTHENTICATED", reason="LOCAL_COLLECTION_FIELDS_ONLY",
                **{key: timing[key] for key in (
                    "bar_start_utc", "model_bar_end_utc", "runtime_observed_at_utc", "event_hash")},
                collection_started_at_utc=started_text, collection_returned_at_utc=returned_text,
                collection_duration_seconds=duration,
                return_to_observation_seconds=(observed - returned).total_seconds())


def project_collection(event, status, event_hash):
    """Check fields in this event only. Never search later batches or read a key."""
    timing = project_timing(event, status, event_hash)
    if "collection_proof" not in event:
        return unavailable_collection("PROOF_ABSENT")
    try:
        proof, bars = event["collection_proof"], event["bars"]
        require(isinstance(proof, dict) and set(proof) == {"payload", "signature"}
                and len(_encoded(proof)) <= 4096)
        payload = proof["payload"]
        require(isinstance(payload, dict) and set(payload) == {
            "schema", "scope", "collector_digest", "bars_digest", "started_at", "received_at"})
        require(type(payload["schema"]) is int and payload["schema"] == 1
                and payload["scope"] == "kis-server-collection"
                and isinstance(payload["collector_digest"], str)
                and re.fullmatch("sha256:[0-9a-f]{64}", payload["collector_digest"])
                and isinstance(proof["signature"], str)
                and re.fullmatch("[0-9a-f]{64}", proof["signature"]))
        require(isinstance(bars, dict) and set(bars) == SYMBOLS)
        for symbol, bar in bars.items():
            require(isinstance(bar, dict) and set(bar) == {
                "symbol", "timestamp_utc", "open", "high", "low", "close", "volume"})
            require(bar["symbol"] == symbol and bar["timestamp_utc"] == event["timestamp"])
            prices = [bar[key] for key in ("open", "high", "low", "close")]
            require(all(type(p) in {int, float} and math.isfinite(p) and p > 0 for p in prices)
                    and type(bar["volume"]) is int and bar["volume"] > 0)
            op, hi, lo, cl = prices
            require(lo <= min(op, cl) <= max(op, cl) <= hi)
        require(payload["bars_digest"] == event["bar_digest"] == _hash(bars))
        return _fields(timing, payload["started_at"], payload["received_at"])
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return unavailable_collection("PROOF_INVALID")


def validate_collection(value, status):
    """Validate the safe projection; does not reauthenticate omitted raw evidence."""
    require(isinstance(value, dict) and set(value) == set(BASE) | set(DETAILS) | {
        "status", "reason"})
    for key, expected in BASE.items():
        require(type(value[key]) is type(expected) and value[key] == expected)
    timing = validate_timing(status["timing"], status)
    if value["status"] == "UNAVAILABLE":
        require(value["reason"] in REASONS and all(value[key] is None for key in DETAILS))
        if value["reason"] in {"PROOF_ABSENT", "PROOF_INVALID"}:
            require(timing["status"] == "RECORDED")
        else:
            require(timing["status"] == "UNAVAILABLE" and value["reason"] == timing["reason"])
    else:
        require(value["status"] == "RECORDED_UNAUTHENTICATED" and timing["status"] == "RECORDED")
        require(value == _fields(timing, value["collection_started_at_utc"],
                                value["collection_returned_at_utc"]))
        for key in ("collection_duration_seconds", "return_to_observation_seconds"):
            require(type(value[key]) in {int, float} and math.isfinite(value[key]))
    require(len(_encoded(value)) <= 4096)
    return dict(value)


def _project_records(event, status, event_hash):
    return dict(timing=project_timing(event, status, event_hash),
                collection_record=project_collection(event, status, event_hash))


def read_recorded_status(root, now, reader):
    """One existing shared lock and bounded latest-record query for both projections."""
    with timing_lock(root) as acquired:
        status = reader(root, now)
        projected = (_read_timing(root, status, projector=_project_records)
                     if acquired else unavailable("READER_BUSY"))
        if "timing" not in projected:
            projected = dict(timing=projected,
                             collection_record=unavailable_collection(projected["reason"]))
        return dict(status, **projected)
