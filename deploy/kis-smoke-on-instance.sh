#!/usr/bin/env bash
# Run the KIS live-read smoke test on the operator instance through the
# fixed deploy gateway. This script is installed root-owned by
# repair-ssh-boundary.sh and is intentionally narrow: it reads KIS credentials
# from /opt/auto-invest/.env, checks out the target commit into /tmp, and runs
# the read-only integration smoke tests there.

set -uo pipefail

if [[ "${1:-}" == "--quote-handoff-once" ]]; then
    if [[ "$#" -ne 1 ]]; then
        printf '%s\n' '{"status":"BLOCKED","reason":"EXACTLY_ONE_MODE_ARGUMENT_REQUIRED","orders_submitted":0}'
        exit 2
    fi
    exec /usr/bin/timeout --signal=KILL 60s /usr/bin/python3 -I -S -c "$(cat <<'QUOTE_HANDOFF_PYTHON'
"""Embedded in the existing root-owned KIS helper; stdlib only, no auth reads."""

import base64
import hashlib
import json
import os
import pwd
import re
import select
import stat
import subprocess
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BASE = Path("/opt/auto-invest")
APP_USER = "auto-invest"
SYMBOLS = ("AAPL", "SCHX", "SPTI", "IAUM")
MARKETS = {"AAPL": "NAS", "SCHX": "AMS", "SPTI": "AMS", "IAUM": "AMS"}
HASHES = {
    "kis_quotes.py": "e0ea3f45e0e4a8c76c634de3a9f7292422e404d7153a50057e8d8a56b430f12f",
    "quote_handoff.py": "c4c8b2473e3c5bdccd6df32bd415ecbf2be2cef7210a7b49a7cd8c03967dfb2d",
    "paper-quote-config.json": "faa70ff94f86fec83cdffd2a23af05c485c7ab7745e3668cfc9e0e195dfe32f2",
}
LIMIT = 50_000
GET_LIMIT = 12
SECONDS = 60
UTC = timezone.utc
CREATED_FILES = []
OUTPUT_PUBLISHED = False


class Refusal(Exception):
    pass


def require(condition, code):
    if not condition:
        raise Refusal(code)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def decode_payload(raw):
    require(len(raw) <= LIMIT, "PAYLOAD_TOO_LARGE")
    try:
        decoded = base64.b64decode(raw.strip(), validate=True)
        data = json.loads(decoded, object_pairs_hook=unique_object)
        require(set(data) == {"schema_version", "files"}, "PAYLOAD_SCHEMA_INVALID")
        require(type(data["schema_version"]) is int and data["schema_version"] == 1,
                "PAYLOAD_SCHEMA_INVALID")
        require(set(data["files"]) == set(HASHES), "ONLY_THREE_APPROVED_FILES")
        files = {}
        for name, expected in HASHES.items():
            row = data["files"][name]
            require(set(row) == {"content_b64"}, "FILE_SCHEMA_INVALID")
            content = base64.b64decode(row["content_b64"], validate=True)
            require(hashlib.sha256(content).hexdigest() == expected, "APPROVED_FILE_HASH_MISMATCH")
            files[name] = content
        return files
    except Refusal:
        raise
    except (ValueError, TypeError, KeyError):
        raise Refusal("PAYLOAD_INVALID") from None


def read_input(fd, deadline):
    result = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        require(remaining > 2, "INPUT_DEADLINE_EXCEEDED")
        readable, _, _ = select.select([fd], [], [], remaining - 2)
        require(bool(readable), "INPUT_DEADLINE_EXCEEDED")
        chunk = os.read(fd, 8192)
        if not chunk:
            return bytes(result)
        result.extend(chunk)
        require(len(result) <= LIMIT, "PAYLOAD_TOO_LARGE")


def secure_parent(path):
    require(path.is_absolute() and path.resolve() == path and path.is_dir(), "PARENT_PATH_UNSAFE")
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def drop_identity(identity):
    os.setgroups([])
    os.setgid(identity.pw_gid)
    os.setuid(identity.pw_uid)


def collector_command():
    addon = BASE / "quote-handoff-addon"
    return [str(BASE / ".venv/bin/python"), str(addon / "kis_quotes.py"), "once",
            "--environment", "production", "--env-file", str(BASE / ".env"),
            "--token-cache", str(BASE / "data/kis_token.json"), "--symbols", ",".join(SYMBOLS),
            "--output", str(addon / "capture/quote-handoff.json"), "--max-requests", "12"]


def launch_collector(identity, deadline):
    remaining = deadline - time.monotonic() - 2
    require(remaining > 0, "COLLECTION_DEADLINE_EXCEEDED")
    process = subprocess.Popen(
        collector_command(), shell=False, cwd=str(BASE),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(BASE / "src"),
             "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        preexec_fn=lambda: drop_identity(identity),
    )
    try:
        return process.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        process.kill()  # Only the new process owned by this invocation.
        process.wait(timeout=1)
        raise Refusal("COLLECTION_TIMEOUT_NEW_CHILD_KILLED") from None


def stamp(value):
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(value.utcoffset() is not None, "QUOTE_TIMEZONE_REQUIRED")
    return value.astimezone(UTC)


def positive(value, optional=False):
    if optional and value is None:
        return
    require(isinstance(value, str) and bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value)),
            "QUOTE_PRICE_INVALID")
    require(Decimal(value) > 0, "QUOTE_PRICE_INVALID")


def safe_projection(data, now):
    require(set(data) == {"schema_version", "source", "emitted_at_utc", "requested_symbols",
                          "quotes", "unknown", "quote_request_attempts", "execution_mode", "broker_orders_enabled"},
            "OUTPUT_SCHEMA_INVALID")
    require(type(data["schema_version"]) is int and data["schema_version"] == 2,
            "OUTPUT_SCHEMA_INVALID")
    require(type(data["quote_request_attempts"]) is int
            and 0 <= data["quote_request_attempts"] <= GET_LIMIT, "OUTPUT_REQUEST_BUDGET_INVALID")
    require(data["execution_mode"] == "PAPER_INPUT_ONLY" and data["broker_orders_enabled"] is False,
            "OUTPUT_EXECUTION_MODE_INVALID")
    require(data["source"] == {
        "kind": "KIS_REST_CURRENT_QUOTE", "environment": "production",
        "endpoint": "/uapi/overseas-price/v1/quotations/price", "tr_id": "HHDFS00000300",
    }, "OUTPUT_SOURCE_INVALID")
    require(data["requested_symbols"] == list(SYMBOLS), "OUTPUT_SYMBOLS_INVALID")
    require(set(data["quotes"]) | set(data["unknown"]) == set(SYMBOLS)
            and not set(data["quotes"]) & set(data["unknown"]), "OUTPUT_COVERAGE_INVALID")
    require(data["quote_request_attempts"] >= len(data["quotes"]), "OUTPUT_RECEIPT_COUNT_INVALID")
    emitted = stamp(data["emitted_at_utc"])
    require(0 <= (now - emitted).total_seconds() <= 120, "OUTPUT_STALE_OR_FUTURE")
    rows = []
    for symbol in SYMBOLS:
        if symbol not in data["quotes"]:
            continue
        row = data["quotes"][symbol]
        require(set(row) == {"last_USD", "bid_USD", "ask_USD", "exchange", "observed_at_utc",
                             "source_trade_time", "source_latency_verified", "source_response_sha256"},
                "QUOTE_SCHEMA_INVALID")
        require(row["exchange"] == MARKETS[symbol], "QUOTE_MARKET_MISMATCH")
        require(row["source_trade_time"] is None and row["source_latency_verified"] is False,
                "QUOTE_SOURCE_TIME_CLAIM_INVALID")
        require(isinstance(row["source_response_sha256"], str)
                and bool(re.fullmatch(r"[0-9a-f]{64}", row["source_response_sha256"])),
                "QUOTE_RESPONSE_PROVENANCE_INVALID")
        observed = stamp(row["observed_at_utc"])
        require(observed <= emitted and 0 <= (now - observed).total_seconds() <= 120,
                "QUOTE_RESPONSE_STALE_OR_FUTURE")
        positive(row["last_USD"])
        positive(row["bid_USD"], optional=True)
        positive(row["ask_USD"], optional=True)
        if row["bid_USD"] is not None and row["ask_USD"] is not None:
            require(Decimal(row["bid_USD"]) <= Decimal(row["ask_USD"]), "QUOTE_CROSSED_BID_ASK")
        rows.append(dict(symbol=symbol, currency="USD", **row))
    return {"quotes": rows,
            "quote_request_attempts": data["quote_request_attempts"],
            "unknown": {s: "QUOTE_UNAVAILABLE" for s in SYMBOLS if s not in data["quotes"]},
            "source_trade_time_verified": False, "real_time_verified": False}


def read_output(data_fd, now):
    fd = os.open("quote-handoff.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=data_fd)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 16_384, "OUTPUT_NOT_SMALL_REGULAR")
        raw = handle.read(16_385)
    require(len(raw) <= 16_384, "OUTPUT_TOO_LARGE")
    data = json.loads(raw, object_pairs_hook=unique_object)
    return safe_projection(data, now), hashlib.sha256(raw).hexdigest(), raw


def publish_output(addon_fd, data_fd, raw, identity, deadline):
    """Link a verified root-owned inode into an absent destination; never replace."""
    global OUTPUT_PUBLISHED
    require(time.monotonic() < deadline - 1, "PUBLICATION_DEADLINE_EXCEEDED")
    fd = os.open("sealed-output.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o640, dir_fd=addon_fd)
    with os.fdopen(fd, "wb") as handle:
        CREATED_FILES.append("sealed-output.json")
        os.fchown(handle.fileno(), 0, identity.pw_gid)
        os.fchmod(handle.fileno(), 0o640)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        written = os.fstat(handle.fileno())
        require(time.monotonic() < deadline, "PUBLICATION_DEADLINE_EXCEEDED")
        try:
            os.link("sealed-output.json", "quote-handoff.json", src_dir_fd=addon_fd,
                    dst_dir_fd=data_fd, follow_symlinks=False)
        except FileExistsError:
            raise Refusal("OUTPUT_ALREADY_EXISTS_AT_PUBLICATION") from None
        except OSError:
            # Includes separate filesystems/unsupported hard links. No replace fallback.
            raise Refusal("OUTPUT_NONREPLACING_PUBLICATION_UNAVAILABLE") from None
        OUTPUT_PUBLISHED = True
        published = os.stat("quote-handoff.json", dir_fd=data_fd, follow_symlinks=False)
        require((published.st_dev, published.st_ino) == (written.st_dev, written.st_ino),
                "OUTPUT_CHANGED_AFTER_PUBLICATION")
    # Only our private new root-owned link is removed after successful publication.
    # The complete verified inode remains at the final destination.
    os.unlink("sealed-output.json", dir_fd=addon_fd)


def execute(raw, deadline):
    global OUTPUT_PUBLISHED
    require(os.geteuid() == 0, "ROOT_HELPER_REQUIRED")
    files = decode_payload(raw)
    identity = pwd.getpwnam(APP_USER)
    require(identity.pw_uid != 0, "NONROOT_APP_IDENTITY_REQUIRED")
    base_fd, data_fd, addon_fd, capture_fd = secure_parent(BASE), None, None, None
    try:
        data_fd = secure_parent(BASE / "data")
        # Lexical checks include dangling symlinks. No existing target is read or replaced.
        require(not os.path.lexists(BASE / "quote-handoff-addon"), "ADDON_ALREADY_EXISTS")
        require(not os.path.lexists(BASE / "data/quote-handoff.json"), "OUTPUT_ALREADY_EXISTS")
        require(time.monotonic() < deadline - 2, "INSTALL_DEADLINE_EXCEEDED")
        os.mkdir("quote-handoff-addon", 0o750, dir_fd=base_fd)
        addon_fd = os.open("quote-handoff-addon", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                           dir_fd=base_fd)
        os.fchown(addon_fd, 0, identity.pw_gid)
        os.fchmod(addon_fd, 0o750)
        for name, content in files.items():
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640,
                         dir_fd=addon_fd)
            with os.fdopen(fd, "wb") as handle:
                CREATED_FILES.append(name)
                os.fchown(handle.fileno(), 0, identity.pw_gid)
                os.fchmod(handle.fileno(), 0o640)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        os.mkdir("capture", 0o700, dir_fd=addon_fd)
        capture_fd = os.open("capture", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                             dir_fd=addon_fd)
        os.fchown(capture_fd, identity.pw_uid, identity.pw_gid)
        os.fchmod(capture_fd, 0o700)
        try:
            os.stat("quote-handoff.json", dir_fd=data_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise Refusal("OUTPUT_ALREADY_EXISTS_BEFORE_COLLECTION")
        exit_code = launch_collector(identity, deadline)
        projection, output_sha, output_raw = read_output(capture_fd, datetime.now(UTC))
        publish_output(addon_fd, data_fd, output_raw, identity, deadline)
        require(time.monotonic() <= deadline, "TOTAL_DEADLINE_EXCEEDED")
        return {
            "contract": "KIS_QUOTE_HANDOFF_ONCE_V2",
            "status": "SUCCESS" if exit_code == 0 and not projection["unknown"] else "PARTIAL_OR_BLOCKED",
            "collector_exit_code": exit_code, "installed_files_sha256": HASHES,
            "output_sha256": output_sha, "maximum_GET_requests": GET_LIMIT,
            "maximum_requests_per_second": 1, "maximum_total_seconds": SECONDS,
            "orders_submitted": 0, "token_issuance_or_refresh": False, **projection,
        }
    finally:
        os.close(base_fd)
        if data_fd is not None:
            os.close(data_fd)
        if addon_fd is not None:
            os.close(addon_fd)
        if capture_fd is not None:
            os.close(capture_fd)


def main():
    global OUTPUT_PUBLISHED
    CREATED_FILES.clear()
    OUTPUT_PUBLISHED = False
    deadline = time.monotonic() + SECONDS
    try:
        result = execute(read_input(0, deadline), deadline)
        code = 0 if result["status"] == "SUCCESS" else 2
    except Refusal as error:
        result, code = {"status": "BLOCKED", "reason": str(error), "orders_submitted": 0,
                        "created_file_names": CREATED_FILES, "new_output_published": OUTPUT_PUBLISHED}, 2
    except Exception:
        # Never echo payload, paths supplied by callers, child stderr, or exception text.
        result, code = {"status": "BLOCKED", "reason": "SEALED_HELPER_FAILED", "orders_submitted": 0,
                        "created_file_names": CREATED_FILES, "new_output_published": OUTPUT_PUBLISHED}, 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
QUOTE_HANDOFF_PYTHON
)"
fi

LIVE_REPO="${LIVE_REPO:-/opt/auto-invest}"
TARGET_SHA="${1:-${TARGET_SHA:-origin/main}}"
FALLBACK_REMOTE_URL="${FALLBACK_REMOTE_URL:-https://github.com/jinooaction/claude.git}"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "::warning::kis-smoke helper must run as root via the deploy gateway (setup pending)."
    exit 100
fi
if [[ "${TARGET_SHA}" != "origin/main" && ! "${TARGET_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
    echo "::warning::unsafe TARGET_SHA '${TARGET_SHA}' — expected origin/main or a 40-char commit SHA."
    exit 100
fi
if [[ ! -d "${LIVE_REPO}" ]]; then
    echo "::warning::${LIVE_REPO} 가 인스턴스에 없습니다 — provision-vultr.yml 미실행 (셋업 보류)."
    exit 100
fi

echo "--- smoke 전용 checkout 준비 ---"
echo "운영 repo: ${LIVE_REPO} (읽기 전용: .env/remote URL 확인만)"
echo "대상 commit: ${TARGET_SHA}"

# smoke 는 운영 워커가 쓰는 /opt/auto-invest 작업트리를 절대 checkout/reset 하지 않는다.
# 배포 상태기계만 운영 repo 를 갱신해야 deploy no-op/worker 미재시작 경쟁이 사라진다.
git config --global --add safe.directory "${LIVE_REPO}" 2>/dev/null || true
sudo -u auto-invest git config --global --add safe.directory "${LIVE_REPO}" 2>/dev/null || true
remote_url="$(git -C "${LIVE_REPO}" config --get remote.origin.url 2>/dev/null || true)"
remote_url="${remote_url:-${FALLBACK_REMOTE_URL}}"

smoke_parent=/tmp/auto-invest-kis-smoke
mkdir -p "${smoke_parent}"
chmod 1777 "${smoke_parent}" 2>/dev/null || true
SMOKE_REPO="$(sudo -u auto-invest mktemp -d "${smoke_parent}/repo.XXXXXX" 2>/dev/null || mktemp -d "${smoke_parent}/repo.XXXXXX")"
trap 'sudo rm -rf "${SMOKE_REPO:-}" 2>/dev/null || rm -rf "${SMOKE_REPO:-}"' EXIT

if ! sudo -u auto-invest git clone --quiet --no-checkout "${remote_url}" "${SMOKE_REPO}" 2>/dev/null; then
    rm -rf "${SMOKE_REPO:?}/"* "${SMOKE_REPO}/".[^.]* 2>/dev/null || true
    clone_url="${FALLBACK_REMOTE_URL}"
    sudo -u auto-invest git clone --quiet --no-checkout "${clone_url}" "${SMOKE_REPO}" 2>/dev/null || git clone --quiet --no-checkout "${clone_url}" "${SMOKE_REPO}"
    chown -R auto-invest:auto-invest "${SMOKE_REPO}" 2>/dev/null || true
fi
git config --global --add safe.directory "${SMOKE_REPO}" 2>/dev/null || true
sudo -u auto-invest git config --global --add safe.directory "${SMOKE_REPO}" 2>/dev/null || true
sudo -u auto-invest git -C "${SMOKE_REPO}" fetch --quiet origin main
if [[ "${TARGET_SHA}" != "origin/main" ]]; then
    if ! sudo -u auto-invest git -C "${SMOKE_REPO}" merge-base --is-ancestor "${TARGET_SHA}" origin/main; then
        echo "::warning::target commit ${TARGET_SHA} is not reachable from origin/main (setup pending)."
        exit 100
    fi
fi
sudo -u auto-invest git -C "${SMOKE_REPO}" checkout --quiet --detach "${TARGET_SHA}"
echo "smoke HEAD: $(git -C "${SMOKE_REPO}" rev-parse --short HEAD) ($(git -C "${SMOKE_REPO}" log -1 --pretty=%s))"
echo
echo "--- .env 확인 (KIS 키만 ✓ 표시, 값 노출 안 함) ---"
if [[ ! -f "${LIVE_REPO}/.env" ]]; then
    echo "::warning::${LIVE_REPO}/.env 파일이 없습니다 — scripts/set_secrets.sh 미실행 (셋업 보류)."
    exit 100
fi
missing_env=()
for k in KIS_APP_KEY KIS_APP_SECRET KIS_ACCOUNT_NO; do
    if grep -qE "^${k}=[^[:space:]]" "${LIVE_REPO}/.env"; then
        echo "  ${k}: ✓ 설정됨"
    else
        missing_env+=("${k}")
    fi
done
if [[ ${#missing_env[@]} -gt 0 ]]; then
    echo "::warning::.env 에 다음 KIS 키 누락: ${missing_env[*]} (셋업 보류)."
    exit 100
fi
echo
echo "--- KIS_LIVE_TEST=1 라이브 smoke 실행 ---"
read_env_value() {
    local key="$1"
    local line value
    line="$(grep -E "^${key}=" "${LIVE_REPO}/.env" | tail -1 || true)"
    value="${line#*=}"
    value="${value%$'\r'}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "${value}" == \"*\" && "${value}" == *\" ]]; then
        value="${value:1:${#value}-2}"
    elif [[ "${value}" == \'*\' && "${value}" == *\' ]]; then
        value="${value:1:${#value}-2}"
    fi
    printf '%s' "$value"
}
KIS_APP_KEY="$(read_env_value KIS_APP_KEY)"
KIS_APP_SECRET="$(read_env_value KIS_APP_SECRET)"
KIS_ACCOUNT_NO="$(read_env_value KIS_ACCOUNT_NO)"

# sudo -E 가 root 의 HOME=/root 로 남으면서 auto-invest 가 root 의
# ~/.cache/uv 에 접근 시도 → permission denied. UV_CACHE_DIR / HOME 을 명시
# 전달한다. Pytest cache는 서버의 이전 root-owned 흔적을 피하려고 끈다.
AUTO_INVEST_HOME=$(getent passwd auto-invest 2>/dev/null | cut -d: -f6 || echo /tmp)
cd "${SMOKE_REPO}"
KIS_LIVE_TEST=1 sudo -E -u auto-invest \
    env "PATH=$PATH" \
        "HOME=${AUTO_INVEST_HOME}" \
        "UV_CACHE_DIR=${AUTO_INVEST_HOME}/.cache/uv" \
        "KIS_LIVE_TEST=1" \
        "KIS_APP_KEY=$KIS_APP_KEY" \
        "KIS_APP_SECRET=$KIS_APP_SECRET" \
        "KIS_ACCOUNT_NO=$KIS_ACCOUNT_NO" \
        "KIS_TOKEN_CACHE_PATH=${LIVE_REPO}/data/kis_token.json" \
    /usr/local/bin/uv run --project "${SMOKE_REPO}" pytest \
        tests/integration/test_live_broker.py -v -s \
        -p no:cacheprovider 2>&1
pytest_exit=$?
if [[ "${pytest_exit}" -ne 0 ]]; then
    echo "::warning::KIS smoke failed after one token issue; not retrying full live tests to avoid KIS OAuth throttle and duplicate live-read noise."
fi

# Account source capture uses the same approved checkout and credentials. The
# private journal persists outside the temporary checkout; stdout is counts only.
# Older approved commits without the recorder remain valid smoke targets.
if [[ "${pytest_exit}" -eq 0 && -f "${SMOKE_REPO}/src/auto_invest/execution/intraday_account_history.py" ]]; then
    sudo -u auto-invest env \
        "KIS_APP_KEY=$KIS_APP_KEY" \
        "KIS_APP_SECRET=$KIS_APP_SECRET" \
        "KIS_ACCOUNT_NO=$KIS_ACCOUNT_NO" \
        "KIS_TOKEN_CACHE_PATH=${LIVE_REPO}/data/kis_token.json" \
        /usr/local/bin/uv run --project "${SMOKE_REPO}" python \
        "${SMOKE_REPO}/scripts/intraday_balance_check.py" \
        --history-db "${LIVE_REPO}/data/account-source.db"
    capture_exit=$?
    if [[ "${capture_exit}" -ne 0 ]]; then
        echo "::warning::Private account source capture failed; no retry or account verification promotion."
        exit 2
    fi
fi
exit "${pytest_exit}"
