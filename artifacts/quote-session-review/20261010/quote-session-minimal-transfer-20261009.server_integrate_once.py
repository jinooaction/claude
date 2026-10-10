"""Stdlib root supervisor: explicit once approval -> isolated install -> token-only GET+paper -> seal."""

import argparse
import fcntl
import hashlib
import json
import os
import pwd
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

BASE = Path("/opt/auto-invest")
INSTALL = Path("/usr/local/lib/auto-invest-quote-session-review")
CONTROL = Path("/var/lib/auto-invest-quote-session-review")
PREFIX = "stock-quote-session-live-ready-candidate"
KIND = "KIS_EXISTING_TOKEN_ONE_SHOT_V2"
PROFILE = dict(
    max_attempts=3,
    max_HTTP_per_capture=10,
    max_HTTP=30,
    max_seconds=180,
    capture_spacing=60,
    HTTP_spacing=1,
)
MAX_ARCHIVE = 20 * 1024 * 1024
ROOT_PYTHON = Path("/usr/bin/python3")
SYMBOLS = {"AAPL", "SCHX", "SPTI", "IAUM"}


def assert_public_strings(data, secrets=()):
    """Decode to stability, checking every result; exhaustible work fails closed."""
    remaining = 262144

    def string(value, *, key=False):
        nonlocal remaining
        while True:
            remaining -= len(value.encode("utf-8")) + 1
            require(remaining >= 0, "KIS_SESSION_NORMALIZATION_LIMIT")
            require(
                not any(secret and secret in value for secret in secrets)
                and not re.search(r"bearer\s+", value, re.I)
                and (
                    not key
                    or not re.search(
                        r"authorization|app.?key|app.?secret|access.?token|refresh.?token|password|credential",
                        value,
                        re.I,
                    )
                ),
                "KIS_SESSION_SECRET_BODY",
            )
            try:
                decoded = unicodedata.normalize("NFKC", unquote(value, errors="strict"))
            except (UnicodeError, ValueError):
                raise Refusal("KIS_SESSION_NORMALIZATION_INVALID") from None
            if decoded == value:
                return
            value = decoded  # The final decoded value is checked on the next iteration.

    def walk(value, depth=0):
        require(depth <= 64, "KIS_SESSION_STRUCTURE_LIMIT")
        if isinstance(value, dict):
            for key, child in value.items():
                string(key, key=True)
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1)
        elif isinstance(value, str):
            string(value)

    walk(data)


def quote_body(raw, secrets=(), *, mock):
    """Preserve original bytes only for a deliberately narrow quote response schema."""
    require(len(raw) <= 65536, "KIS_SESSION_BODY_LIMIT")
    try:
        body = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_constant=lambda _: require(False, "KIS_SESSION_NONFINITE"),
        )
    except Exception:
        raise Refusal("KIS_SESSION_INVALID_JSON") from None
    assert_public_strings(body, secrets)
    require(isinstance(body, dict), "KIS_SESSION_RESPONSE_OBJECT_REQUIRED")
    require(
        body.get("mock_payload") is True if mock else "mock_payload" not in body,
        "KIS_SESSION_EXECUTION_KIND_MISMATCH",
    )
    require(
        body.get("rt_cd") == "0" and isinstance(body.get("output"), dict),
        "KIS_SESSION_BROKER_RESPONSE_FAILED",
    )
    require(
        set(body) <= {"rt_cd", "msg_cd", "msg1", "output", "mock_payload"},
        "KIS_SESSION_RESPONSE_SCHEMA_DENIED",
    )
    if "msg_cd" in body:
        require(
            isinstance(body["msg_cd"], str)
            and re.fullmatch(r"[A-Z][A-Z0-9]{0,11}", body["msg_cd"]),
            "KIS_SESSION_RESPONSE_SCHEMA_DENIED",
        )
    if "msg1" in body:
        require(
            isinstance(body["msg1"], str)
            and body["msg1"]
            in {
                "",
                "정상처리 되었습니다.",
                "정상처리되었습니다.",
                "정상 처리 되었습니다.",
            },
            "KIS_SESSION_RESPONSE_SCHEMA_DENIED",
        )
    numeric = {
        "zdiv",
        "base",
        "pvol",
        "last",
        "sign",
        "diff",
        "rate",
        "tvol",
        "tamt",
        "ordy",
        "bidp",
        "askp",
    }
    output = body["output"]
    require(set(output) <= numeric | {"rsym"}, "KIS_SESSION_RESPONSE_SCHEMA_DENIED")
    for key, value in output.items():
        if key == "rsym":
            allowed = {""} | {
                f"{prefix}{market}{symbol}"
                for prefix in ("", "D")
                for market in ("NAS", "NYS", "AMS")
                for symbol in SYMBOLS
            }
            require(
                isinstance(value, str) and value in allowed,
                "KIS_SESSION_RESPONSE_SCHEMA_DENIED",
            )
        else:
            require(
                value is None
                or isinstance(value, str)
                and (
                    value == ""
                    or re.fullmatch(
                        r"[+-]?\d{1,18}(?:\.\d{1,8})?", value, flags=re.ASCII
                    )
                ),
                "KIS_SESSION_RESPONSE_SCHEMA_DENIED",
            )
    return body


def app_identity(identity=None):
    identity = identity or pwd.getpwnam("auto-invest")
    require(
        identity.pw_name == "auto-invest"
        and type(identity.pw_uid) is int
        and type(identity.pw_gid) is int
        and identity.pw_uid > 0
        and identity.pw_gid > 0,
        "NONROOT_APP_IDENTITY_REQUIRED",
    )
    return identity


def app_privileges(identity):
    identity = app_identity(identity)
    return dict(user=identity.pw_uid, group=identity.pw_gid, extra_groups=())


def run_app_json(command, release, deadline, *, identity, pass_fds=()):
    """All app-writable Python executes after native POSIX privilege drop, never root."""
    privileges = app_privileges(identity)
    process = subprocess.Popen(
        command,
        cwd=release,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        pass_fds=pass_fds,
        start_new_session=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        **privileges,
    )
    raw = bytearray()
    try:
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                left = deadline - time.monotonic()
                require(left > 0, "APP_OUTPUT_DEADLINE")
                for key, _ in selector.select(min(1, left)):
                    block = os.read(key.fd, 65537 - len(raw))
                    if not block:
                        selector.unregister(key.fileobj)
                    else:
                        raw.extend(block)
                        require(len(raw) <= 65536, "APP_OUTPUT_LIMIT")
        process.wait(timeout=max(0.1, deadline - time.monotonic()))
        try:
            data = json.loads(
                raw,
                object_pairs_hook=unique,
                parse_constant=lambda _: require(False, "APP_OUTPUT_NONFINITE"),
            )
        except Exception:
            raise Refusal("APP_OUTPUT_INVALID") from None
        # Raw stdout is transient memory only. No raw app stdout or stderr log is written.
        return process.returncode, data
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=1)
        process.stdout.close()


def public_wallet(value):
    require(isinstance(value, dict), "APP_WALLET_INVALID")
    base = {
        "cash_USD",
        "positions",
        "simulated_fills",
        "commissions_USD",
        "processed_captures",
        "holding_deadlines",
        "policy_id",
        "strategy_validated",
        "orders_submitted",
    }
    optional = {
        "ever_bought",
        "last_decision_at_utc",
        "last_event_sha256",
        "reconciliation",
    }
    require(base <= set(value) <= base | optional, "APP_WALLET_INVALID")
    for key in ("cash_USD", "commissions_USD"):
        require(
            isinstance(value[key], str)
            and re.fullmatch(
                r"[+-]?\d{1,18}(?:\.\d{1,8})?", value[key], flags=re.ASCII
            ),
            "APP_WALLET_INVALID",
        )
    for key in ("simulated_fills", "processed_captures", "orders_submitted"):
        require(
            type(value[key]) is int
            and 0
            <= value[key]
            <= (
                4
                if key == "simulated_fills"
                else 3
                if key == "processed_captures"
                else 0
            ),
            "APP_WALLET_INVALID",
        )
    require(
        value["policy_id"] == "quote-basket-plumbing-v1"
        and value["strategy_validated"] is False,
        "APP_WALLET_INVALID",
    )
    positions, deadlines = value["positions"], value["holding_deadlines"]
    require(
        isinstance(positions, dict)
        and set(positions) <= SYMBOLS
        and all(type(q) is int and 0 <= q < 2**63 for q in positions.values()),
        "APP_WALLET_INVALID",
    )
    require(
        isinstance(deadlines, dict) and set(deadlines) <= SYMBOLS, "APP_WALLET_INVALID"
    )
    for row in deadlines.values():
        require(
            isinstance(row, dict) and set(row) == {"deadline_utc", "planned_exit_utc"},
            "APP_WALLET_INVALID",
        )
        for stamp in row.values():
            public_utc(stamp)
    if "ever_bought" in value:
        require(
            isinstance(value["ever_bought"], list)
            and all(s in SYMBOLS for s in value["ever_bought"]),
            "APP_WALLET_INVALID",
        )
    if value.get("last_decision_at_utc") is not None:
        public_utc(value["last_decision_at_utc"])
    if "last_event_sha256" in value:
        public_hash(value["last_event_sha256"], 64)
    if "reconciliation" in value:
        require(
            value["reconciliation"] == "MATCHED_EXISTING_PAPER_AUDIT",
            "APP_WALLET_INVALID",
        )
    return value


def public_hash(value, size):
    require(
        isinstance(value, str) and re.fullmatch(r"[a-f0-9]{" + str(size) + "}", value),
        "APP_HASH_INVALID",
    )


def public_utc(value):
    require(isinstance(value, str) and len(value) <= 32, "APP_TIME_INVALID")
    parsed = datetime.fromisoformat(value)
    require(
        parsed.utcoffset() == timedelta(0) and parsed.isoformat() == value,
        "APP_TIME_INVALID",
    )
    return parsed


def public_binding(value, grant, worker_out):
    if value is None:
        return None
    fields = {
        "session_id",
        "started_at",
        "deadline_at",
        "profile",
        "producer_sha256",
        "input_kind",
        "grant_sha256",
        "approval_id",
        "manifest",
        "consumer_sha256",
    }
    require(isinstance(value, dict) and set(value) == fields, "APP_BINDING_INVALID")
    require(
        value["session_id"] == grant["run_id"]
        and value["approval_id"] == grant["approval_id"]
        and value["grant_sha256"] == sha(encode(grant))
        and value["profile"] == PROFILE
        and value["input_kind"] == "REAL_KIS_HTTP_EXPLICIT_ONE_SHOT"
        and value["producer_sha256"]
        == grant["runtime_files_sha256"]["approved_session.py"]
        and value["consumer_sha256"]
        == grant["runtime_files_sha256"]["approved_session_program.py"]
        and value["manifest"] == str(worker_out / "captures/manifest.json"),
        "APP_BINDING_INVALID",
    )
    began, end = public_utc(value["started_at"]), public_utc(value["deadline_at"])
    require(end == began + timedelta(seconds=180), "APP_BINDING_INVALID")
    return value


def public_worker(value, grant, worker_out):
    assert_public_strings(value)
    require(isinstance(value, dict), "APP_WORKER_INVALID")
    fields = {
        "phase",
        "reason",
        "kind",
        "input_kind",
        "grant_sha256",
        "approval_id",
        "run_id",
        "clock_kind",
        "producer_sha256",
        "counters",
        "paper",
        "binding",
        "session_cursor",
        "actual_external_GET",
        "orders_submitted",
        "token_issuance_or_refresh",
        "account_queries",
        "live_eligible",
        "strategy_validated",
        "strategy_trials_added",
        "legacy_strategy_trial_lower_bound",
        "source_trade_time_verified",
        "real_time_verified",
        "production_readiness",
        "notice",
    }
    require(set(value) == fields, "APP_WORKER_INVALID")
    require(
        value["phase"] in {"GRANTED_SESSION_COMPLETE", "INPUT_BLOCKED"}
        and value["reason"]
        in {
            None,
            "QUOTE_INPUT_REJECTED",
            "GRANT_OR_TOKEN_REJECTED",
            "GRANTED_SESSION_FAILED",
        },
        "APP_WORKER_INVALID",
    )
    require(
        value["kind"] == KIND
        and value["input_kind"] == "REAL_KIS_HTTP_EXPLICIT_ONE_SHOT"
        and value["grant_sha256"] == sha(encode(grant))
        and value["approval_id"] == grant["approval_id"]
        and value["run_id"] == grant["run_id"]
        and value["clock_kind"] == "ACTUAL_UTC_AND_MONOTONIC"
        and value["producer_sha256"]
        == grant["runtime_files_sha256"]["approved_session.py"],
        "APP_WORKER_INVALID",
    )
    for key in (
        "token_issuance_or_refresh",
        "account_queries",
        "live_eligible",
        "strategy_validated",
        "source_trade_time_verified",
        "real_time_verified",
        "production_readiness",
    ):
        require(value[key] is False, "APP_WORKER_INVALID")
    require(
        type(value["orders_submitted"]) is int
        and value["orders_submitted"] == 0
        and type(value["strategy_trials_added"]) is int
        and value["strategy_trials_added"] == 0
        and type(value["legacy_strategy_trial_lower_bound"]) is int
        and value["legacy_strategy_trial_lower_bound"] == 63,
        "APP_WORKER_INVALID",
    )
    for key, limit in (("session_cursor", 3), ("actual_external_GET", 30)):
        require(
            type(value[key]) is int and 0 <= value[key] <= limit, "APP_WORKER_INVALID"
        )
    counts = value["counters"]
    fields = {
        "attempts_reserved",
        "HTTP_reserved",
        "HTTP_transport_entered",
        "HTTP_completed",
        "actual_external_GET",
        "complete_captures",
        "state",
        "unknown",
        "source_trade_time_verified",
        "real_time_verified",
        "token_issuance_or_refresh",
        "orders_submitted",
        "wire_outcome_unknown",
    }
    require(isinstance(counts, dict) and set(counts) == fields, "APP_COUNTERS_INVALID")
    for key, limit in (
        ("attempts_reserved", 3),
        ("complete_captures", 3),
        ("HTTP_reserved", 30),
        ("HTTP_transport_entered", 30),
        ("HTTP_completed", 30),
        ("actual_external_GET", 30),
        ("wire_outcome_unknown", 30),
        ("orders_submitted", 0),
    ):
        require(
            type(counts[key]) is int and 0 <= counts[key] <= limit,
            "APP_COUNTERS_INVALID",
        )
    require(
        counts["state"] in {"ACTIVE", "COMPLETED", "FAILED"}
        and isinstance(counts["unknown"], dict)
        and set(counts["unknown"]) <= SYMBOLS
        and all(v == "CAPTURE_ABORTED" for v in counts["unknown"].values()),
        "APP_COUNTERS_INVALID",
    )
    for key in (
        "source_trade_time_verified",
        "real_time_verified",
        "token_issuance_or_refresh",
    ):
        require(counts[key] is False, "APP_COUNTERS_INVALID")
    public_wallet(value["paper"])
    public_binding(value["binding"], grant, worker_out)
    require(
        value["notice"]
        == "한정된 기존 토큰 현재가·새 모의원장 검증 / source시간 미확인",
        "APP_WORKER_INVALID",
    )
    return value


def public_audit(value, grant, worker_out):
    assert_public_strings(value)
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "paper",
            "binding",
            "session_cursor",
            "orders_submitted",
            "actual_external_GET",
            "auth_reads",
        },
        "APP_AUDIT_INVALID",
    )
    for key in ("orders_submitted", "actual_external_GET", "auth_reads"):
        require(type(value[key]) is int and value[key] == 0, "APP_AUDIT_INVALID")
    require(
        type(value["session_cursor"]) is int and 0 <= value["session_cursor"] <= 3,
        "APP_AUDIT_INVALID",
    )
    public_wallet(value["paper"])
    public_binding(value["binding"], grant, worker_out)
    return value


class Refusal(ValueError):
    pass


def require(value, code):
    if not value:
        raise Refusal(code)


def encode(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_FIELD")
        result[key] = value
    return result


def read_regular(path, limit, *, root_owned=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        require(
            stat.S_ISREG(info.st_mode) and info.st_size <= limit,
            "REGULAR_FILE_REQUIRED",
        )
        if root_owned:
            require(
                info.st_uid == 0
                and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1,
                "ROOT_PRIVATE_FILE_REQUIRED",
            )
        raw = f.read(limit + 1)
        require(len(raw) <= limit, "FILE_LIMIT")
        return raw


def immutable(path, raw, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def owned_directory(path, mode):
    path.mkdir(mode=mode, exist_ok=True)
    info = path.stat(follow_symlinks=False)
    require(
        path.resolve() == path
        and stat.S_ISDIR(info.st_mode)
        and info.st_uid == 0
        and not info.st_mode & 0o022,
        "ROOT_INSTALL_DIRECTORY_REQUIRED",
    )
    path.chmod(mode)


def atomic(path, raw):
    require(not path.is_symlink(), "POINTER_SYMLINK")
    fd, name = tempfile.mkstemp(prefix=".active-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_approval(data, now):
    fields = {
        "schema_version",
        "kind",
        "status",
        "approval_id",
        "run_id",
        "archive_sha256",
        "runtime_files_sha256",
        "profile",
        "whole_seconds",
        "created_at",
        "expires_at",
        "target_base",
    }
    require(
        set(data) == fields
        and type(data["schema_version"]) is int
        and data["schema_version"] == 1,
        "APPROVAL_SCHEMA",
    )
    require(
        data["kind"] == KIND and data["status"] == "EXPLICITLY_APPROVED_ONCE",
        "EXPLICIT_APPROVAL_REQUIRED",
    )
    require(
        encode(data["profile"]) == encode(PROFILE)
        and type(data["whole_seconds"]) is int
        and data["whole_seconds"] == 300,
        "APPROVAL_BUDGET",
    )
    require(data["target_base"] == str(BASE), "APPROVAL_HOST_SCOPE")
    require(
        all(re.fullmatch("[a-f0-9]{32}", data[k]) for k in ("approval_id", "run_id")),
        "APPROVAL_ID",
    )
    require(
        re.fullmatch("[a-f0-9]{64}", data["archive_sha256"]), "APPROVAL_ARCHIVE_PIN"
    )
    created = datetime.fromisoformat(data["created_at"])
    expires = datetime.fromisoformat(data["expires_at"])
    require(
        created.utcoffset() == expires.utcoffset() == timedelta(0)
        and created <= now < expires
        and 300 <= (expires - created).total_seconds() <= 1800,
        "APPROVAL_TIME",
    )
    require(
        isinstance(data["runtime_files_sha256"], dict) and data["runtime_files_sha256"],
        "APPROVAL_RUNTIME_PINS",
    )


def install_archive(raw, release, expected, check_time):
    import io

    require(len(raw) <= MAX_ARCHIVE, "ARCHIVE_LIMIT")
    release.mkdir(mode=0o755, parents=False, exist_ok=False)
    release.chmod(0o755)
    total = 0
    seen = set()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for info in z.infolist():
            check_time()
            path = Path(info.filename)
            require(
                path.parts[0] == PREFIX
                and len(path.parts) > 1
                and ".." not in path.parts
                and not path.is_absolute()
                and not info.is_dir(),
                "ARCHIVE_MEMBER_PATH",
            )
            rel = str(path.relative_to(PREFIX))
            require(
                rel not in seen
                and not stat.S_ISLNK(info.external_attr >> 16)
                and ".venv" not in path.parts
                and "__pycache__" not in path.parts,
                "ARCHIVE_MEMBER_DENIED",
            )
            seen.add(rel)
            total += info.file_size
            require(total <= MAX_ARCHIVE, "ARCHIVE_EXPANSION_LIMIT")
            contents = z.read(info)
            if rel in expected:
                require(sha(contents) == expected[rel], "RUNTIME_HASH_MISMATCH")
            target = release / rel
            for parent in reversed(target.parent.parents):
                if parent.is_relative_to(release) and parent != release:
                    parent.mkdir(exist_ok=True, mode=0o755)
                    parent.chmod(0o755)
            target.parent.mkdir(exist_ok=True, mode=0o755)
            target.parent.chmod(0o755)
            immutable(target, contents, mode=0o444)
            target.chmod(0o444)
    require(set(expected) <= seen, "MISSING_RUNTIME_FILE")


def check_environment(python, release, deadline, *, identity):
    script = "import importlib.metadata,json;print(json.dumps({d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions()}))"
    code, actual = run_app_json(
        [str(python), "-I", "-B", "-c", script],
        release,
        deadline,
        identity=identity,
    )
    require(code == 0 and isinstance(actual, dict), "EXISTING_ENVIRONMENT_UNAVAILABLE")
    for line in (release / "requirements.lock").read_text().splitlines():
        name, version = line.split("==")
        require(
            actual.get(name.lower().replace("_", "-")) == version,
            "EXISTING_ENVIRONMENT_VERSION_MISMATCH",
        )


def public_metadata(value, root):
    """Closed evidence vocabulary: no arbitrary text or opaque response extensions."""
    assert_public_strings(value)
    keys = set(
        "AAPL SCHX SPTI IAUM HTTP_completed HTTP_reserved HTTP_spacing HTTP_status HTTP_transport_entered account_queries actual_external_GET approval_id ask_USD attempt attempt_started_at attempts_reserved bid_USD binding broker_orders_enabled capture_spacing captures cash_USD clock_kind commissions_USD complete_captures consumer_sha256 contract counters deadline_at deadline_utc emitted_at emitted_at_utc endpoint environment ever_bought exchange execution_mode grant_sha256 holding_deadlines input_kind kind last last_USD last_decision_at_utc last_event_sha256 legacy_strategy_trial_lower_bound live_eligible manifest market max_HTTP max_HTTP_per_capture max_attempts max_seconds method notice observed_at_utc orders_submitted outcome paper phase planned_exit_utc policy_id positions previous_receipt_sha256 processed_captures producer_sha256 production_readiness profile published_at quote_request_attempts quotes real_time_verified reason receipt receipt_sha256 reconciliation requested_symbols requests reservation reserved_at response_completed_at response_file response_sha256 run_id schema_version sequence session_cursor session_id simulated_fills snapshot snapshot_sha256 source source_latency_verified source_response_sha256 source_trade_time source_trade_time_verified started_at state status strategy_trials_added strategy_validated symbol token_issuance_or_refresh tr_id transport_entered_at unknown wire_outcome_unknown".split()
    )
    keys.add("auth_reads")
    words = set(
        "AAPL SCHX SPTI IAUM NAS NYS AMS ATTEMPT_RESERVED_ONLY COMPLETED EMPTY_MARKET_PROBE GET GRANTED_SESSION_COMPLETE INPUT_BLOCKED FAILED ACTIVE CAPTURE_ABORTED QUOTE_INPUT_REJECTED GRANT_OR_TOKEN_REJECTED GRANTED_SESSION_FAILED HHDFS00000300 INVENTED_TEST_CLOCK KIS_EXISTING_TOKEN_ONE_SHOT_V2 KIS_QUOTE_SESSION_V2_EXISTING_TOKEN_APPROVED KIS_REST_CURRENT_QUOTE MATCHED_EXISTING_PAPER_AUDIT MOCK_OF_REAL_KIS_ONE_SHOT PAPER_INPUT_ONLY QUOTE RESERVED_ONLY SUCCESS production quote-basket-plumbing-v1 REAL_KIS_HTTP_EXPLICIT_ONE_SHOT ACTUAL_UTC_AND_MONOTONIC ACTUAL_UTC_AND_MONOTONIC_WITH_MOCK_HTTP".split()
    )
    words |= {
        "",
        "/uapi/overseas-price/v1/quotations/price",
        "한정된 기존 토큰 현재가·새 모의원장 검증 / source시간 미확인",
    }

    def walk(item, key=""):
        if isinstance(item, dict):
            require(set(item) <= keys, "EVIDENCE_SCHEMA_DENIED")
            for name, child in item.items():
                walk(child, name)
        elif isinstance(item, list):
            for child in item:
                walk(child, key)
        elif item is None or type(item) is bool:
            return
        elif type(item) is int:
            require(0 <= item < 2**63, "EVIDENCE_SCHEMA_DENIED")
        elif isinstance(item, str):
            if key.endswith("sha256"):
                public_hash(item, 64)
            elif key in {"approval_id", "run_id", "session_id"}:
                public_hash(item, 32)
            elif key.endswith("_utc") or key.endswith("_at"):
                public_utc(item)
            elif key in {"snapshot", "receipt", "response_file"}:
                require(
                    re.fullmatch(
                        r"(?:capture|receipt|http-response)-\d{3}\.json", item
                    ),
                    "EVIDENCE_SCHEMA_DENIED",
                )
            elif key == "manifest":
                require(
                    item == str(root / "captures/manifest.json"),
                    "EVIDENCE_SCHEMA_DENIED",
                )
            elif key.endswith("_USD") or key == "last":
                require(
                    item == ""
                    or re.fullmatch(r"[+-]?\d{1,18}(?:\.\d{1,8})?", item, re.ASCII),
                    "EVIDENCE_SCHEMA_DENIED",
                )
            else:
                require(item in words, "EVIDENCE_SCHEMA_DENIED")
        else:
            require(False, "EVIDENCE_SCHEMA_DENIED")

    walk(value)


def seal_json(root, sealed, check_time, *, grant=None):
    files = {}
    total = 0
    for path in sorted(root.rglob("*.json")):
        check_time()
        require(
            not any(p.is_symlink() for p in (path, *path.parents)), "EVIDENCE_SYMLINK"
        )
        raw = read_regular(path, 131072)
        total += len(raw)
        require(total <= 4 * 1024 * 1024, "SEALED_EVIDENCE_LIMIT")
        relative = str(path.relative_to(root))
        require(
            relative in {"worker-result.json", "ledger-export.json"}
            or re.fullmatch(
                r"captures/(?:manifest|terminal|(?:attempt|http-reserved|http-completed|http-response|capture|receipt)-\d{3})\.json",
                relative,
            ),
            "EVIDENCE_FILENAME_DENIED",
        )
        if re.fullmatch(r"captures/http-response-\d{3}\.json", relative):
            quote_body(raw, mock=grant is None)
        else:
            value = json.loads(
                raw,
                object_pairs_hook=unique,
                parse_constant=lambda _: require(False, "EVIDENCE_NONFINITE"),
            )
            public_metadata(value, root)
            if grant is not None and relative == "worker-result.json":
                public_worker(value, grant, root)
            if grant is not None and relative == "ledger-export.json":
                public_audit(value, grant, root)
        files[relative] = dict(sha256=sha(raw), bytes=len(raw))
    with zipfile.ZipFile(sealed, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for relative, record in files.items():
            raw = read_regular(root / relative, 131072)
            require(sha(raw) == record["sha256"], "EVIDENCE_CHANGED_DURING_SEAL")
            z.writestr(relative, raw)
    sealed.chmod(0o400)
    return dict(
        path=str(sealed),
        sha256=sha(sealed.read_bytes()),
        bytes=sealed.stat().st_size,
        files=files,
    )


def run_once(approval_path, archive_path):
    require(os.geteuid() == 0, "ROOT_CONSOLE_AND_EXPLICIT_APPROVAL_REQUIRED")
    os.umask(0o077)
    for directory in (CONTROL, CONTROL / "approvals", CONTROL / "incoming"):
        info = directory.stat(follow_symlinks=False)
        require(
            directory.resolve() == directory
            and stat.S_ISDIR(info.st_mode)
            and info.st_uid == 0
            and not info.st_mode & 0o022,
            "ROOT_CONTROL_DIRECTORY_REQUIRED",
        )
    lock_fd = os.open(
        CONTROL / "execution.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise Refusal("ANOTHER_REVIEW_RUNNING") from None
    began = time.monotonic()
    started = datetime.now(UTC)
    approval_raw = read_regular(approval_path, 65536, root_owned=True)
    data = json.loads(approval_raw, object_pairs_hook=unique)
    validate_approval(data, started)
    require(
        approval_path == CONTROL / "approvals" / (data["approval_id"] + ".json")
        and archive_path == CONTROL / "incoming" / (data["archive_sha256"] + ".zip"),
        "EXACT_APPROVED_PATH_REQUIRED",
    )
    raw = read_regular(archive_path, MAX_ARCHIVE, root_owned=True)
    require(sha(raw) == data["archive_sha256"], "ARCHIVE_HASH_MISMATCH")
    require(
        data["runtime_files_sha256"].get("server_integrate_once.py")
        == sha(Path(__file__).read_bytes()),
        "SUPERVISOR_PIN_MISMATCH",
    )

    def remaining(limit=300):
        require(0 <= time.monotonic() - began < limit, "WHOLE_OR_INSTALL_DEADLINE")

    for name in ("consumed", "runs", "backups"):
        (CONTROL / name).mkdir(mode=0o700, parents=False, exist_ok=True)
    immutable(
        CONTROL / "consumed" / (data["approval_id"] + ".json"),
        encode(
            dict(
                approval_sha256=sha(approval_raw),
                run_id=data["run_id"],
                started_at=started.isoformat(),
                status="SPENT_ONCE",
            )
        ),
    )
    campaign = CONTROL / "runs" / data["run_id"]
    campaign.mkdir(mode=0o700, exist_ok=False)
    owned_directory(INSTALL, 0o755)
    owned_directory(INSTALL / "releases", 0o755)
    pointer = INSTALL / "active.json"
    prior = read_regular(pointer, 65536, root_owned=True) if pointer.exists() else None
    backup = CONTROL / "backups" / (data["run_id"] + ".json")
    immutable(
        backup,
        encode(
            dict(
                previous_active_sha256=sha(prior) if prior else None,
                previous_active_hex=prior.hex() if prior else None,
            )
        ),
    )
    release = INSTALL / "releases" / data["archive_sha256"]
    process = None
    grant_fd = None
    activated = False
    identity = None
    worker_out = None
    result = None
    failure = None
    try:
        identity = app_identity()  # Before ANY app interpreter/startup code is run.
        install_archive(
            raw, release, data["runtime_files_sha256"], lambda: remaining(60)
        )
        check_environment(
            BASE / ".venv/bin/python", release, began + 60, identity=identity
        )
        remaining(60)
        parent = BASE / "data/quote-session-review"
        owned_directory(parent, 0o711)
        output = parent / data["run_id"]
        output.mkdir(mode=0o700, exist_ok=False)
        os.chown(output, identity.pw_uid, identity.pw_gid)
        worker_out = output / "worker"
        grant = dict(
            kind=KIND,
            status="EXPLICITLY_APPROVED_ONCE",
            profile=PROFILE,
            approval_id=data["approval_id"],
            run_id=data["run_id"],
            archive_sha256=data["archive_sha256"],
            started_at=started.isoformat(),
            whole_deadline_at=(started + timedelta(seconds=300)).isoformat(),
            runtime_files_sha256=data["runtime_files_sha256"],
            source_kind="ROOT_SUPERVISOR_GRANT",
        )
        grant_path = campaign / "grant.json"
        immutable(grant_path, encode(grant))
        grant_fd = os.open(grant_path, os.O_RDONLY | os.O_NOFOLLOW)
        atomic(
            pointer,
            encode(
                dict(
                    release=data["archive_sha256"],
                    run_id=data["run_id"],
                    scope="ONE_SHOT_REVIEW_ONLY",
                )
            ),
        )
        activated = True

        worker_code, worker_data = run_app_json(
            [
                str(BASE / ".venv/bin/python"),
                "-I",
                "-B",
                str(release / "real_session_worker.py"),
                "--grant-fd",
                str(grant_fd),
                "--output",
                str(worker_out),
            ],
            release,
            min(time.monotonic() + 185, began + 295),
            identity=identity,
            pass_fds=(grant_fd,),
        )
        remaining()
        result = public_worker(worker_data, grant, worker_out)
        immutable(campaign / "worker-result-public.json", encode(result), mode=0o400)
        require(
            worker_code == 0 and result.get("phase") == "GRANTED_SESSION_COMPLETE",
            "WORKER_FAILED_FIRST_STOP",
        )
        require(
            result["input_kind"] == "REAL_KIS_HTTP_EXPLICIT_ONE_SHOT"
            and result["orders_submitted"] == 0
            and result["session_cursor"] == 3
            and result["counters"]["HTTP_reserved"] == 30
            and result["counters"]["HTTP_transport_entered"] == 30
            and result["counters"]["HTTP_completed"] == 30
            and result["actual_external_GET"] == 30
            and result["grant_sha256"] == sha(encode(grant))
            and result["approval_id"] == data["approval_id"]
            and result["run_id"] == data["run_id"]
            and result["token_issuance_or_refresh"] is False
            and result["source_trade_time_verified"] is False
            and result["real_time_verified"] is False,
            "WORKER_FINAL_CONTRACT",
        )
    except Exception:
        failure = "ONE_SHOT_FAILED_NO_RETRY"
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if grant_fd is not None:
            os.close(grant_fd)
        if failure and activated:
            atomic(
                pointer,
                prior
                if prior is not None
                else encode(
                    dict(status="INACTIVE_AFTER_FAILED_REVIEW", run_id=data["run_id"])
                ),
            )
        restore_ok = (
            not activated
            or not failure
            or (
                pointer.read_bytes() == prior
                if prior is not None
                else json.loads(pointer.read_bytes()).get("status")
                == "INACTIVE_AFTER_FAILED_REVIEW"
            )
        )
    sealed = None
    if worker_out is not None and worker_out.exists():
        try:
            audit_code, audit_data = run_app_json(
                [
                    str(BASE / ".venv/bin/python"),
                    "-I",
                    "-B",
                    str(release / "real_session_worker.py"),
                    "--audit-only",
                    str(worker_out),
                ],
                release,
                began + 295,
                identity=identity,
            )
            require(audit_code == 0, "LEDGER_AUDIT_FAILED")
            audit = public_audit(audit_data, grant, worker_out)
            if result is not None:
                require(
                    all(
                        audit[key] == result[key]
                        for key in ("paper", "binding", "session_cursor")
                    ),
                    "LEDGER_AUDIT_MISMATCH",
                )
            immutable(worker_out / "ledger-export.json", encode(audit), mode=0o400)
            sealed = seal_json(
                worker_out, campaign / "sealed-evidence.zip", remaining, grant=grant
            )
        except Exception:
            failure = failure or "SEAL_OR_LEDGER_AUDIT_FAILED"
            if activated:
                atomic(
                    pointer,
                    prior
                    if prior is not None
                    else encode(
                        dict(
                            status="INACTIVE_AFTER_FAILED_REVIEW", run_id=data["run_id"]
                        )
                    ),
                )
            restore_ok = (
                pointer.read_bytes() == prior
                if prior is not None
                else json.loads(pointer.read_bytes()).get("status")
                == "INACTIVE_AFTER_FAILED_REVIEW"
            )
    outcome = dict(
        status="SUCCESS" if failure is None else "FAILED_NO_RETRY",
        reason=failure,
        approval_id=data["approval_id"],
        run_id=data["run_id"],
        archive_sha256=data["archive_sha256"],
        worker_result=result,
        evidence=sealed,
        restore_verified=restore_ok,
        elapsed_seconds=time.monotonic() - began,
        orders_submitted=0,
        token_issuance_or_refresh=False,
        account_queries=False,
        strategy_trials_added=0,
        actual_external_GET_confirmed=result["actual_external_GET"] if result else None,
        HTTP_execution_unknown=result is None,
        source_trade_time_verified=False,
        real_time_verified=False,
    )
    immutable(campaign / "root-receipt.json", encode(outcome), mode=0o400)
    os.close(lock_fd)
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run"), nargs="?", default="plan")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.command == "plan":
        print(
            json.dumps(
                dict(
                    status="DEFAULT_BLOCKED",
                    profile=PROFILE,
                    whole_seconds=300,
                    existing_token_only=True,
                    orders_submitted=0,
                    actual_external_GET=0,
                    install=str(INSTALL),
                    control=str(CONTROL),
                    production_readiness=False,
                ),
                indent=2,
            )
        )
        return 0
    if not args.child:
        try:
            require(
                args.approval is not None and args.archive is not None,
                "EXPLICIT_APPROVAL_AND_ARCHIVE_REQUIRED",
            )
            code, result = supervise(
                [
                    str(ROOT_PYTHON),
                    "-I",
                    "-S",
                    str(Path(__file__).resolve()),
                    *sys.argv[1:],
                    "--child",
                ],
                approval_path=args.approval,
            )
        except Exception as exc:
            code, result = (
                2,
                dict(
                    status="BLOCKED",
                    reason="EXPLICIT_APPROVAL_AND_ARCHIVE_REQUIRED"
                    if isinstance(exc, Refusal)
                    and str(exc) == "EXPLICIT_APPROVAL_AND_ARCHIVE_REQUIRED"
                    else "SUPERVISOR_FAILED",
                    actual_external_GET=0,
                    orders_submitted=0,
                ),
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return code
    try:
        require(
            args.approval is not None and args.archive is not None,
            "EXPLICIT_APPROVAL_AND_ARCHIVE_REQUIRED",
        )
        result = run_once(args.approval, args.archive)
    except Exception as exc:
        result = dict(
            status="BLOCKED",
            reason="ROOT_CONSOLE_AND_EXPLICIT_APPROVAL_REQUIRED"
            if isinstance(exc, Refusal)
            and str(exc) == "ROOT_CONSOLE_AND_EXPLICIT_APPROVAL_REQUIRED"
            else "SUPERVISOR_PREFLIGHT_FAILED",
            actual_external_GET_confirmed=None,
            HTTP_execution_unknown=True,
            orders_submitted=0,
            token_issuance_or_refresh=False,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "SUCCESS" else 2


def recover_owned_pointer(approval_path):
    data = json.loads(
        read_regular(approval_path, 65536, root_owned=True), object_pairs_hook=unique
    )
    require(re.fullmatch("[a-f0-9]{32}", data["run_id"]), "RECOVERY_RUN_ID")
    require(
        approval_path == CONTROL / "approvals" / (data["approval_id"] + ".json"),
        "RECOVERY_APPROVAL_PATH",
    )
    validate_approval(data, datetime.fromisoformat(data["created_at"]))
    pointer = INSTALL / "active.json"
    if not pointer.exists():
        return True
    current = json.loads(read_regular(pointer, 65536, root_owned=True))
    if current.get("run_id") != data["run_id"]:
        return current.get("scope") != "ONE_SHOT_REVIEW_ONLY"
    backup = json.loads(
        read_regular(
            CONTROL / "backups" / (data["run_id"] + ".json"), 65536, root_owned=True
        )
    )
    if backup["previous_active_hex"] is None:
        atomic(
            pointer,
            encode(dict(status="INACTIVE_AFTER_FAILED_REVIEW", run_id=data["run_id"])),
        )
    else:
        raw = bytes.fromhex(backup["previous_active_hex"])
        require(sha(raw) == backup["previous_active_sha256"], "RECOVERY_BACKUP_HASH")
        atomic(pointer, raw)
        require(pointer.read_bytes() == raw, "RECOVERY_VERIFY_FAILED")
    return True


def supervise(command, *, seconds=295, approval_path=None):
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        raw, _ = process.communicate(timeout=seconds)
        require(len(raw) <= 1048576, "ROOT_RESULT_LIMIT")
        result = json.loads(raw)
        require(result.get("orders_submitted") == 0, "ROOT_RESULT_CONTRACT")
        return process.returncode, result
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=1)
        restored = None
        if approval_path is not None:
            try:
                restored = bounded_recovery(approval_path)
            except Exception:
                restored = False
        return 2, dict(
            status="ABORTED_NO_RETRY",
            reason="ROOT_GROUP_HARD_STOP",
            HTTP_execution_unknown=True,
            actual_external_GET_confirmed=None,
            restore_verified=restored,
            orders_submitted=0,
        )


def bounded_recovery(approval_path):
    """Recovery I/O cannot extend the 295+1+3 second supervisor budget."""
    script = (
        "import json,os,sys;from pathlib import Path;"
        "sys.path.insert(0,sys.argv[1]);import server_integrate_once as s;"
        "s.require(os.geteuid()==0,'ROOT_RECOVERY_REQUIRED');"
        "print(json.dumps({'restored':s.recover_owned_pointer(Path(sys.argv[2]))}))"
    )
    process = subprocess.Popen(
        [
            str(ROOT_PYTHON),
            "-I",
            "-S",
            "-c",
            script,
            str(Path(__file__).resolve().parent),
            str(approval_path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    try:
        raw, _ = process.communicate(timeout=3)
        require(len(raw) <= 1024 and process.returncode == 0, "RECOVERY_FAILED")
        return json.loads(raw)["restored"] is True
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=0.5)


if __name__ == "__main__":
    raise SystemExit(main())
