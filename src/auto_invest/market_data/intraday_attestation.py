"""Trusted-server collection attestations, not broker signatures or authority.

The key holder and its clock are trusted. There is no file-signing command or
caller-supplied transport/clock in the issuing entry point.
"""

import asyncio
import hashlib
import hmac
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import httpx

from auto_invest.market_data.intraday import (
    SYMBOLS,
    DataError,
    ReadTransport,
    collect_kis,
    digest,
    encode,
    iso,
    utc,
)

KEY_PATH = Path("/etc/auto-invest/intraday-market-data.key")


def _read_key():
    try:
        fd = os.open(KEY_PATH, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0
                    or stat.S_IMODE(before.st_mode) & 0o137 or before.st_size != 32
                    or before.st_nlink != 1):
                raise DataError("COLLECTION_KEY_INVALID")
            key = os.read(fd, 33)
            after = os.fstat(fd)
            if len(key) != 32 or any(getattr(before, k) != getattr(after, k) for k in (
                    "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
                raise DataError("COLLECTION_KEY_INVALID")
            return key
        finally:
            os.close(fd)
    except OSError:
        raise DataError("COLLECTION_KEY_UNAVAILABLE") from None


def _collector_digest():
    return digest(encode([digest(path.read_bytes()) for path in (
        Path(__file__), Path(__file__).with_name("intraday.py"),
    )]))


def _seal(bars, started, received, key):
    payload = dict(schema=1, scope="kis-server-collection",
                   collector_digest=_collector_digest(), bars_digest=digest(encode(bars)),
                   started_at=iso(started), received_at=iso(received))
    return dict(payload=payload,
                signature=hmac.new(key, encode(payload), hashlib.sha256).hexdigest())


async def collect_attested_kis(env, start, end, cache_path):
    """Collect, then attest only the returned complete symbol groups."""
    key = _read_key()
    started = datetime.now(UTC)
    async with asyncio.timeout(60):
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            batch = await collect_kis(ReadTransport(client), env, start, end, started, cache_path)
    received = datetime.now(UTC)
    if not 0 <= (received - started).total_seconds() <= 60:
        raise DataError("COLLECTION_CLOCK_INVALID")
    grouped = {}
    for bar in batch["bars"]:
        grouped.setdefault(bar["timestamp_utc"], {})[bar["symbol"]] = bar
    if not grouped or any(set(bars) != set(SYMBOLS) for bars in grouped.values()):
        raise DataError("COLLECTION_GROUP_INCOMPLETE")
    batch["collection_proofs"] = {
        stamp: _seal(bars, started, received, key) for stamp, bars in grouped.items()
    }
    return batch


def verify_collection(proof, bars, observed):
    """Verify a recorded normalized group under the current trusted server key."""
    try:
        if (not isinstance(proof, dict) or set(proof) != {"payload", "signature"}
                or len(encode(proof)) > 4096):
            raise ValueError
        payload = proof["payload"]
        if (not isinstance(payload, dict) or set(payload) != {
                "schema", "scope", "collector_digest", "bars_digest", "started_at", "received_at"}
                or type(payload["schema"]) is not int or payload["schema"] != 1
                or payload["scope"] != "kis-server-collection"
                or payload["collector_digest"] != _collector_digest()
                or payload["bars_digest"] != digest(encode(bars))
                or not isinstance(proof["signature"], str)):
            raise ValueError
        expected = hmac.new(_read_key(), encode(payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, proof["signature"]):
            raise ValueError
        started, received = utc(payload["started_at"]), utc(payload["received_at"])
        if not started <= received <= observed or (received - started).total_seconds() > 60:
            raise ValueError
        return True
    except (ValueError, TypeError, KeyError, OSError):
        raise DataError("COLLECTION_ATTESTATION_INVALID") from None
