"""Server-signed research freeze. No broker access or execution permission."""

import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from auto_invest.execution.intraday_forward import assess_forward
from auto_invest.execution.intraday_selection import ResearchSelection, select_research
from auto_invest.execution.intraday_signals import execution_fingerprint
from auto_invest.market_data.intraday import DataError, digest, iso, utc

KEY_PATH = Path("/etc/auto-invest/intraday-forward.key")


def _read_key():
    try:
        fd = os.open(KEY_PATH, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                    or stat.S_IMODE(info.st_mode) & 0o137 or info.st_size != 32):
                raise DataError("REGISTRATION_KEY_INVALID")
            key = os.read(fd, 33)
            if len(key) != 32:
                raise DataError("REGISTRATION_KEY_INVALID")
            return key
        finally:
            os.close(fd)
    except OSError:
        raise DataError("REGISTRATION_KEY_UNAVAILABLE") from None


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _identity(selection, preregistration):
    if (not isinstance(selection, ResearchSelection) or selection.candidate is None
            or selection.verdict != "PAPER_CHALLENGER"
            or selection.provider != "kis-nasdaq-partial-unadjusted"
            or selection.execution_identity != execution_fingerprint(
                selection.candidate, selection.provider)):
        raise DataError("REGISTRATION_RESEARCH_INVALID")
    return dict(candidate_id=selection.candidate.candidate_id,
                execution_identity=selection.execution_identity,
                dataset_fingerprint=selection.dataset_fingerprint,
                research_digest=selection.research_digest,
                code_commit=selection.code_commit, provider=selection.provider,
                preregistration_digest=digest(preregistration))


def register(archives: Path, preregistration: Path) -> bytes:
    """Only the server key holder can issue; callers cannot supply the freeze time."""
    key = _read_key()
    code_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[3], text=True,
    ).strip()
    with TemporaryDirectory(prefix="intraday-register-") as directory:
        frozen = Path(directory) / "preregistration.json"
        frozen.write_bytes(preregistration.read_bytes())
        selected = select_research(archives, frozen, code_commit)
        identity = _identity(selected, frozen.read_bytes())
    payload = dict(schema=1, scope="intraday-research-freeze", **identity,
                   frozen_at=iso(datetime.now(UTC)))
    signature = hmac.new(key, _encode(payload), hashlib.sha256).hexdigest()
    return _encode(dict(payload=payload, signature=signature))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DataError("REGISTRATION_FORMAT_INVALID")
        result[key] = value
    return result


def verify_registration(record: bytes, selection: ResearchSelection, preregistration: Path):
    """Authenticate a freeze against the current server key, code and selected research."""
    try:
        if not isinstance(record, bytes) or len(record) > 16384:
            raise ValueError
        envelope = json.loads(record, object_pairs_hook=_unique)
        if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
            raise ValueError
        payload, signature = envelope["payload"], envelope["signature"]
        if not isinstance(signature, str) or not re.fullmatch("[0-9a-f]{64}", signature):
            raise ValueError
        expected = hmac.new(_read_key(), _encode(payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise DataError("REGISTRATION_SIGNATURE_INVALID")
        identity = _identity(selection, preregistration.read_bytes())
        if (not isinstance(payload, dict)
                or set(payload) != set(identity) | {"schema", "scope", "frozen_at"}
                or type(payload["schema"]) is not int or payload["schema"] != 1
                or payload["scope"] != "intraday-research-freeze"
                or any(payload[k] != v for k, v in identity.items())):
            raise DataError("REGISTRATION_IDENTITY_CHANGED")
        frozen = utc(payload["frozen_at"])
        if frozen > datetime.now(UTC):
            raise DataError("REGISTRATION_TIME_INVALID")
        return frozen
    except DataError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, OSError):
        raise DataError("REGISTRATION_FORMAT_INVALID") from None


def assess_registered_forward(database, record, selection, preregistration):
    with TemporaryDirectory(prefix="intraday-registered-check-") as directory:
        source = Path(directory) / "preregistration.json"
        source.write_bytes(preregistration.read_bytes())
        frozen = verify_registration(record, selection, source)
        result = assess_forward(database, selection, source,
                                frozen_at=frozen, now=datetime.now(UTC))
    return dict(result, freeze_authentication_verified=True)
