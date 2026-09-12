"""Private, append-only observations from the start of account monitoring.

Local sequence numbers prove journal order only. They are not broker event
identifiers, a complete cash-flow stream, or permission to submit orders.
"""

import hashlib
import json
import os
import re
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path


class AccountHistoryError(ValueError):
    pass


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def ledger_checkpoint(database):
    """Read existing ledger watermarks; do not assume old fills belong to this account."""
    if database is None:
        return None
    connection = None
    try:
        path = Path(database).resolve(strict=True)
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        result = {}
        for table in ("orders", "fills", "audit_log"):
            count, sequence = connection.execute(
                f"SELECT COUNT(*), COALESCE(MAX(seq),0) FROM {table}"
            ).fetchone()
            result[table] = dict(count=count, last_sequence=sequence)
        result["account_binding_verified"] = False
        return result
    except (OSError, sqlite3.Error):
        raise AccountHistoryError("HISTORY_EXECUTION_LEDGER_UNAVAILABLE") from None
    finally:
        if connection is not None:
            connection.close()


class AccountHistory:
    """One private observation batch, persisted on either success or failure."""

    def __init__(self, database, account, *, execution_db=None):
        if not isinstance(account, str) or not re.fullmatch(r"[0-9]{10}", account):
            raise AccountHistoryError("HISTORY_ACCOUNT_INVALID")
        self.path = Path(database)
        if execution_db is not None and self.path.resolve() == Path(execution_db).resolve():
            raise AccountHistoryError("HISTORY_REQUIRES_SEPARATE_DATABASE")
        self.account = account
        self.account_digest = hashlib.sha256(account.encode()).hexdigest()
        self.execution_db = execution_db
        self.started = datetime.now(UTC).isoformat()
        self.before = ledger_checkpoint(execution_db)
        self.responses = []
        self.size = 0
        self.finished = False
        self._validate_file()

    def _validate_file(self):
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_nlink != 1):
            raise AccountHistoryError("HISTORY_PRIVATE_FILE_REQUIRED")
        if info.st_size:
            connection = None
            try:
                connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro",
                                             uri=True, timeout=5)
                tables = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
                if tables != {"account_observations"}:
                    raise AccountHistoryError("HISTORY_DATABASE_TYPE_MISMATCH")
            except sqlite3.Error:
                raise AccountHistoryError("HISTORY_DATABASE_TYPE_MISMATCH") from None
            finally:
                if connection is not None:
                    connection.close()

    def client(self, client):
        owner = self

        class RecordingClient:
            async def request(self, method, url, **kwargs):
                params = kwargs.get("params", {})
                if (method != "GET" or not isinstance(url, str)
                        or url not in {
                            "/uapi/overseas-stock/v1/trading/inquire-present-balance",
                            "/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance",
                            "/uapi/domestic-stock/v1/trading/inquire-account-balance",
                            "/uapi/domestic-stock/v1/trading/inquire-balance",
                            "/uapi/overseas-stock/v1/trading/inquire-period-trans",
                            "/uapi/overseas-stock/v1/trading/inquire-ccnl",
                            "/uapi/overseas-stock/v1/trading/inquire-balance",
                            "/uapi/overseas-stock/v1/trading/inquire-nccs",
                            "/uapi/overseas-stock/v1/trading/inquire-psamount",
                            "/uapi/overseas-stock/v1/trading/foreign-margin",
                        }
                        or params.get("CANO") != owner.account[:8]
                        or params.get("ACNT_PRDT_CD") != owner.account[8:]):
                    raise AccountHistoryError("HISTORY_READ_SCOPE_INVALID")
                started = datetime.now(UTC).isoformat()
                response = await client.request(method, url, **kwargs)
                # Never store authentication headers, request objects, broker
                # free-form messages or response cookies. Retain data outputs.
                try:
                    body = response.json()
                except ValueError:
                    body = None
                record = dict(
                    endpoint=url, started_at=started,
                    received_at=datetime.now(UTC).isoformat(),
                    http_status=response.status_code,
                    continuation=response.headers.get("tr_cont"),
                    request_continuation=kwargs.get("headers", {}).get("tr_cont"),
                    params={k: v for k, v in params.items()
                            if k not in {"CANO", "ACNT_PRDT_CD"}},
                    data={k: v for k, v in body.items()
                          if k in {"rt_cd", "output", "output1", "output2", "output3",
                                   "ctx_area_fk100", "ctx_area_nk100", "ctx_area_fk200",
                                   "ctx_area_nk200"}} if isinstance(body, dict) else None,
                )
                owner.size += len(_encode(record).encode())
                if len(owner.responses) >= 200 or owner.size > 8 * 1024 * 1024:
                    raise AccountHistoryError("HISTORY_BATCH_LIMIT")
                owner.responses.append(record)
                return response

        return RecordingClient()

    def finish(self, status):
        if self.finished or status not in {"COMPLETE", "FAILED"}:
            raise AccountHistoryError("HISTORY_BATCH_STATE_INVALID")
        payload = _encode(dict(
            schema=1, started_at=self.started, completed_at=datetime.now(UTC).isoformat(),
            status=status, ledger_before=self.before,
            ledger_after=ledger_checkpoint(self.execution_db), responses=self.responses,
        ))
        connection = None
        try:
            # O_EXCL and mode 0600 prevent a new sensitive file being briefly
            # world-readable. Existing files are never chmod'ed or replaced.
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
            self._validate_file()
            connection = sqlite3.connect(self.path, timeout=5)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""CREATE TABLE IF NOT EXISTS account_observations (
                seq INTEGER PRIMARY KEY, account_digest TEXT NOT NULL,
                payload TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL)""")
            for action in ("UPDATE", "DELETE"):
                connection.execute(f"""CREATE TRIGGER IF NOT EXISTS history_no_{action.lower()}
                    BEFORE {action} ON account_observations BEGIN
                    SELECT RAISE(ABORT, 'account history is append-only'); END""")
            previous, sequence = "0" * 64, 0
            for row in connection.execute("SELECT * FROM account_observations ORDER BY seq"):
                sequence += 1
                expected = hashlib.sha256(
                    _encode([sequence, self.account_digest, row[2], previous]).encode()
                ).hexdigest()
                if row != (sequence, self.account_digest, row[2], previous, expected):
                    raise AccountHistoryError("HISTORY_CHAIN_OR_ACCOUNT_MISMATCH")
                previous = expected
            sequence += 1
            digest = hashlib.sha256(
                _encode([sequence, self.account_digest, payload, previous]).encode()
            ).hexdigest()
            connection.execute("INSERT INTO account_observations VALUES (?,?,?,?,?)",
                               (sequence, self.account_digest, payload, previous, digest))
            connection.commit()
            self.finished = True
            return dict(status=status, observation_sequence=sequence,
                        response_count=len(self.responses), live_eligible=False)
        except (OSError, sqlite3.Error):
            raise AccountHistoryError("HISTORY_STORAGE_UNAVAILABLE") from None
        finally:
            if connection is not None:
                connection.close()
