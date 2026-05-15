"""Side-effecting deploy phases — spec 006.

Each function is a pure step: it does its work and returns a structured
result. The runner decides ordering and audit emission.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

from auto_invest.deploy.kernel_guard import (
    KernelTouchReport,
    kernel_diff_check,
    load_kernel_manifest,
)
from auto_invest.deploy.supervisor import Supervisor


@dataclass(frozen=True)
class StepResult:
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class PullResult:
    ok: bool
    sha_before: str = ""
    sha_after: str = ""
    detail: str = ""


def pull(repo: Path, branch: str) -> PullResult:
    """git fetch + git reset --hard origin/<branch>. Returns shas."""
    try:
        sha_before = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(repo), "fetch", "--quiet", "origin", branch],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "reset", "--hard", f"origin/{branch}"],
            capture_output=True, text=True, check=True,
        )
        sha_after = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        return PullResult(ok=False, detail=f"git failed: {exc.stderr or exc}")
    return PullResult(ok=True, sha_before=sha_before, sha_after=sha_after)


def sync(repo: Path) -> StepResult:
    """uv sync --frozen. Restores deps to the lockfile."""
    if shutil.which("uv") is None:
        return StepResult(ok=False, detail="uv not found on PATH")
    try:
        proc = subprocess.run(
            ["uv", "sync", "--frozen"],
            cwd=str(repo),
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        return StepResult(ok=False, detail=f"uv sync OSError: {exc}")
    if proc.returncode != 0:
        return StepResult(ok=False, detail=proc.stderr.strip() or "uv sync failed")
    return StepResult(ok=True)


def kernel_check(repo: Path, sha_before: str, sha_after: str) -> KernelTouchReport:
    """Return the kernel-touch report between two shas. v3.0.0: informational.

    If the repo has no kernel manifest (e.g. a freshly-bootstrapped repo
    or a test fixture), return a clean report — there is nothing to check.
    """
    if not sha_before or not sha_after or sha_before == sha_after:
        return KernelTouchReport(touches=())
    manifest_path = repo / ".specify" / "memory" / "kernel.toml"
    if not manifest_path.exists():
        return KernelTouchReport(touches=())
    proc = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"{sha_before}..{sha_after}"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        return KernelTouchReport(touches=())
    changed = [line for line in proc.stdout.splitlines() if line.strip()]
    manifest = load_kernel_manifest(manifest_path)
    return kernel_diff_check(changed, manifest=manifest)


def migrate_live(db_path: Path) -> StepResult:
    """Apply pending SQLite migrations to the live DB."""
    from auto_invest.persistence import db as dbmod

    try:
        conn = dbmod.get_connection(db_path)
        try:
            dbmod.migrate(conn)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return StepResult(ok=False, detail=f"migrate failed: {exc}")
    return StepResult(ok=True)


def dry_run_config(config_path: Path) -> StepResult:
    """Parse the rules TOML the same way the worker does, but don't run."""
    from auto_invest.config.loader import ConfigError, load_config

    try:
        load_config(config_path)
    except ConfigError as exc:
        return StepResult(ok=False, detail=f"config invalid: {exc}")
    except FileNotFoundError as exc:
        return StepResult(ok=False, detail=f"config missing: {exc}")
    return StepResult(ok=True)


@dataclass(frozen=True)
class HealthCheckResult:
    ok: bool
    detail: str = ""
    elapsed_s: float = 0.0


def _read_audit_rows_since(
    conn: sqlite3.Connection,
    after_ts_utc: str,
    event_types: tuple[str, ...] | None = None,
) -> list[sqlite3.Row]:
    if event_types:
        placeholders = ",".join("?" for _ in event_types)
        return list(
            conn.execute(
                f"SELECT * FROM audit_log "
                f"WHERE ts_utc > ? AND event_type IN ({placeholders}) "
                f"ORDER BY seq",
                (after_ts_utc, *event_types),
            )
        )
    return list(
        conn.execute(
            "SELECT * FROM audit_log WHERE ts_utc > ? ORDER BY seq",
            (after_ts_utc,),
        )
    )


def health_check(
    db_path: Path,
    deploy_started_ts_utc: str,
    window_s: int = 90,
    poll_interval_s: float = 1.0,
    *,
    now_fn=None,
    sleep_fn=None,
) -> HealthCheckResult:
    """Poll the audit log until WORKER_STARTED arrives or window elapses.

    Fails fast on ERROR or DATA_QUALITY_ISSUE rows during the window.
    """
    import time

    if window_s < 1:
        return HealthCheckResult(ok=False, detail="window must be >= 1")
    now_fn = now_fn or time.monotonic
    sleep_fn = sleep_fn or time.sleep
    deadline = now_fn() + window_s
    from auto_invest.persistence import db as dbmod

    conn = dbmod.get_connection(db_path)
    try:
        started_seen = False
        while True:
            errors = _read_audit_rows_since(conn, deploy_started_ts_utc, ("ERROR",))
            if errors:
                first = errors[0]
                return HealthCheckResult(
                    ok=False,
                    detail=f"ERROR row during health window: {first['event_type']}",
                    elapsed_s=window_s - max(deadline - now_fn(), 0),
                )
            dq = _read_audit_rows_since(
                conn, deploy_started_ts_utc, ("DATA_QUALITY_ISSUE",)
            )
            if dq:
                return HealthCheckResult(
                    ok=False,
                    detail="DATA_QUALITY_ISSUE row during health window",
                    elapsed_s=window_s - max(deadline - now_fn(), 0),
                )
            started = _read_audit_rows_since(
                conn, deploy_started_ts_utc, ("WORKER_STARTED",)
            )
            if started:
                started_seen = True
                return HealthCheckResult(ok=True, elapsed_s=0.0)
            if now_fn() >= deadline:
                return HealthCheckResult(
                    ok=False,
                    detail="timed out waiting for WORKER_STARTED",
                    elapsed_s=float(window_s),
                )
            sleep_fn(poll_interval_s)
        # unreachable
        return HealthCheckResult(ok=started_seen)
    finally:
        conn.close()


@dataclass(frozen=True)
class RollbackResult:
    ok: bool
    detail: str = ""
    rolled_back_to: str = ""


def rollback(
    repo: Path,
    sha_before: str,
    supervisor: Supervisor,
    db_path: Path,
    deploy_started_ts_utc: str,
    health_window_s: int = 90,
    *,
    now_fn=None,
    sleep_fn=None,
) -> RollbackResult:
    """Restore the previous worker version per R-D6."""
    try:
        subprocess.run(
            ["git", "-C", str(repo), "checkout", sha_before],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        return RollbackResult(ok=False, detail=f"git checkout failed: {exc.stderr}")
    sync_result = sync(repo)
    if not sync_result.ok:
        return RollbackResult(ok=False, detail=f"rollback sync failed: {sync_result.detail}")
    start_result = supervisor.start_worker()
    if not start_result.ok:
        return RollbackResult(
            ok=False, detail=f"rollback start_worker failed: {start_result.stderr}"
        )
    hc = health_check(
        db_path,
        deploy_started_ts_utc,
        window_s=health_window_s,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
    )
    if not hc.ok:
        return RollbackResult(
            ok=False, detail=f"rollback health_check failed: {hc.detail}"
        )
    return RollbackResult(ok=True, rolled_back_to=sha_before)


@dataclass(frozen=True)
class CanaryGateResult:
    ok: bool
    detail: str = ""
    matched_row_seq: int | None = None


def canary_gate(
    db_path: Path,
    ruleset_sha256: str,
    code_sha256: str,
    *,
    max_age_seconds: int = 86_400,
    now_fn=None,
) -> CanaryGateResult:
    """Verify a recent CANARY_PASSED row matches the candidate.

    Per R-D10 / FR-D14: required when --triggered-by=auto-tuner.
    """
    import json
    from datetime import UTC, datetime

    from auto_invest.persistence import db as dbmod

    if not ruleset_sha256:
        return CanaryGateResult(ok=False, detail="ruleset_sha256 missing")
    now_fn = now_fn or (lambda: datetime.now(UTC))
    conn = dbmod.get_connection(db_path)
    try:
        rows = list(
            conn.execute(
                "SELECT seq, ts_utc, payload_json FROM audit_log "
                "WHERE event_type = 'CANARY_PASSED' ORDER BY seq DESC LIMIT 1"
            )
        )
        if not rows:
            return CanaryGateResult(ok=False, detail="no CANARY_PASSED row found")
        row = rows[0]
        payload = json.loads(row["payload_json"])
        # spec 007 CanaryPassedPayload doesn't carry ruleset/code shas in v1;
        # we look for an extension field if present, otherwise we accept the
        # row if its candidate_rev matches code_sha256.
        candidate_rev = payload.get("candidate_rev", "")
        row_ruleset = payload.get("ruleset_sha256") or payload.get("ruleset_hash") or ""
        if candidate_rev and candidate_rev != code_sha256:
            return CanaryGateResult(
                ok=False,
                detail=(
                    f"CANARY_PASSED candidate_rev={candidate_rev!r} != "
                    f"deploy code sha={code_sha256!r}"
                ),
            )
        if row_ruleset and row_ruleset != ruleset_sha256:
            return CanaryGateResult(
                ok=False,
                detail=(
                    f"CANARY_PASSED ruleset={row_ruleset!r} != "
                    f"--ruleset-sha256={ruleset_sha256!r}"
                ),
            )
        ts = datetime.fromisoformat(row["ts_utc"].replace("Z", "+00:00"))
        age = (now_fn() - ts).total_seconds()
        if age > max_age_seconds:
            return CanaryGateResult(
                ok=False,
                detail=f"CANARY_PASSED is {int(age)}s old (>{max_age_seconds}s)",
            )
        return CanaryGateResult(ok=True, matched_row_seq=int(row["seq"]))
    finally:
        conn.close()
