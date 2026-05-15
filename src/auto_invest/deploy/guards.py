"""Deploy preconditions — spec 006 Phase 3.

Each guard returns a frozen decision object the runner consumes. The
guards never write to the audit log — that responsibility belongs to
the runner so emission order is centralised.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import exchange_calendars

DEFAULT_PID_PATH = Path("data/auto_invest.deploy.pid")


@dataclass(frozen=True)
class MarketHoursDecision:
    is_open: bool
    next_close_utc: str | None
    next_open_utc: str | None

    @property
    def allowed(self) -> bool:
        return not self.is_open

    def refusal_reason(self) -> str:
        if self.allowed:
            return "market closed"
        return (
            f"US market is open (NYSE session in progress). "
            f"Next allowed deploy: {self.next_close_utc}."
        )


def market_hours_guard(now: datetime | None = None) -> MarketHoursDecision:
    """Refuse to deploy during US regular hours (constitution VIII.A).

    Uses the same XNYS calendar as the worker. `now` is for tests.
    """
    cal = exchange_calendars.get_calendar("XNYS")
    ts = now or datetime.now(UTC)
    is_open = cal.is_trading_minute(ts)
    if is_open:
        session = cal.minute_to_session(ts)
        close = cal.session_close(session)
        return MarketHoursDecision(
            is_open=True,
            next_close_utc=close.strftime("%Y-%m-%dT%H:%M:%SZ"),
            next_open_utc=None,
        )
    next_open = cal.next_open(ts)
    return MarketHoursDecision(
        is_open=False,
        next_close_utc=None,
        next_open_utc=next_open.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


@dataclass(frozen=True)
class DirtyTreeDecision:
    is_dirty: bool
    porcelain: str

    @property
    def allowed(self) -> bool:
        return not self.is_dirty


def dirty_tree_check(repo: Path) -> DirtyTreeDecision:
    """Return whether the working tree has uncommitted changes."""
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    porcelain = result.stdout.strip()
    return DirtyTreeDecision(is_dirty=bool(porcelain), porcelain=porcelain)


@dataclass(frozen=True)
class SecretsDecision:
    missing: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return not self.missing


REQUIRED_SECRETS = ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT_NO")


def secrets_present(env_path: Path | None = None) -> SecretsDecision:
    """Check that required secrets are loadable.

    The check honours environment variables first (production case where
    secrets are injected via systemd `EnvironmentFile=`); falls back to
    parsing the `.env` file at `env_path` if the env vars are absent.
    Never echoes secret values anywhere.
    """
    missing: list[str] = []
    env_values: dict[str, str] = {}
    if env_path is not None and env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            env_values[key.strip()] = value.strip().strip('"').strip("'")
    for key in REQUIRED_SECRETS:
        if os.environ.get(key):
            continue
        if env_values.get(key):
            continue
        missing.append(key)
    return SecretsDecision(missing=tuple(missing))


class LockContention(RuntimeError):
    """Raised when the deploy PID lock is held by another running process."""

    def __init__(self, pid: int, cmdline: str) -> None:
        self.pid = pid
        self.cmdline = cmdline
        super().__init__(f"deploy lock held by pid={pid} cmdline={cmdline!r}")


@dataclass
class LockHandle:
    """Context-manager-ish handle. Use via `acquire_lock(...)` + `release()`."""

    pid_path: Path
    pid: int

    def release(self) -> None:
        import contextlib

        with contextlib.suppress(FileNotFoundError):
            self.pid_path.unlink()

    def __enter__(self) -> LockHandle:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def _process_alive(pid: int) -> tuple[bool, str]:
    """Return (alive, cmdline). POSIX-only via /proc."""
    proc = Path("/proc") / str(pid) / "cmdline"
    if not proc.exists():
        return False, ""
    try:
        raw = proc.read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return False, ""
    return True, raw


def acquire_lock(pid_path: Path | None = None) -> LockHandle:
    """Acquire the deploy lock; raise `LockContention` if another deploy is live.

    Stale-pid detection per R-D3: if the recorded pid is dead or its
    cmdline does not include `auto-invest`, treat the lock as stale and
    overwrite.
    """
    path = pid_path or DEFAULT_PID_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            recorded = int(path.read_text().strip() or "0")
        except (ValueError, OSError):
            recorded = 0
        if recorded > 0:
            alive, cmdline = _process_alive(recorded)
            if alive and "auto-invest" in cmdline:
                raise LockContention(pid=recorded, cmdline=cmdline)
    my_pid = os.getpid()
    path.write_text(f"{my_pid}\n")
    return LockHandle(pid_path=path, pid=my_pid)


@dataclass(frozen=True)
class IdempotencyDecision:
    is_noop: bool
    sha_local: str
    sha_remote: str
    branch: str


def idempotency_check(repo: Path, branch: str) -> IdempotencyDecision:
    """Return whether HEAD already matches origin/<branch> after fetch (R-D4)."""
    subprocess.run(
        ["git", "-C", str(repo), "fetch", "--quiet", "origin", branch],
        check=True,
    )
    local = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    remote = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"origin/{branch}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return IdempotencyDecision(
        is_noop=(local == remote),
        sha_local=local,
        sha_remote=remote,
        branch=branch,
    )
