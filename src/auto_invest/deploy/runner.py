"""DeployRunner — phase state machine + audit emission. Spec 006.

Phases (per contracts/deploy-cli.md):

    cli_parse → load_secrets → acquire_lock → idempotency_check →
    market_hours_guard → dirty_tree_check →
    [DEPLOY_STARTED] →
    pull → kernel_check (informational) → canary_gate (auto-tuner only) →
    sync → migrate → dry_run_check →
    if dry_run: [DEPLOY_COMPLETED(phase=dry_run)] return
    stop_worker → start_worker → health_check →
    [DEPLOY_COMPLETED(phase=live)]

On any failure after DEPLOY_STARTED, emit DEPLOY_FAILED then attempt
rollback per R-D6; emit DEPLOY_ROLLED_BACK on success.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from auto_invest.deploy import guards, steps
from auto_invest.deploy.supervisor import Supervisor
from auto_invest.persistence import (
    audit,
)
from auto_invest.persistence import (
    db as dbmod,
)


@dataclass(frozen=True)
class RunnerConfig:
    repo: Path
    db_path: Path
    branch: str = "main"
    dry_run: bool = False
    allow_dirty: bool = False
    health_window_s: int = 90
    triggered_by: Literal["manual", "auto-tuner"] = "manual"
    ruleset_sha256: str = ""
    config_path: Path = Path("config/rules.toml")
    env_path: Path = Path(".env")
    pid_path: Path | None = None  # None means use default
    worker_stop_timeout_s: int = 10


@dataclass(frozen=True)
class RunnerResult:
    exit_code: int
    correlation_id: str | None
    sha_before: str
    sha_after: str
    phase_terminal: str
    detail: str = ""
    rolled_back: bool = False


def _utcnow_ms() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _make_correlation_id(sha_before: str, started_ts: str) -> str:
    digest = hashlib.sha256(f"{sha_before}:{started_ts}".encode()).hexdigest()
    return digest[:32]


@dataclass
class DeployRunner:
    config: RunnerConfig
    supervisor: Supervisor
    _stdout: list[str] = field(default_factory=list)
    _stderr: list[str] = field(default_factory=list)

    # --- helpers ---

    def emit(self, line: str) -> None:
        self._stdout.append(line)

    def emit_err(self, line: str) -> None:
        self._stderr.append(line)

    def _append(self, payload: audit.AuditPayload, correlation_id: str | None = None) -> None:
        conn = dbmod.get_connection(self.config.db_path)
        try:
            audit.append(conn, payload, correlation_id=correlation_id)
            conn.commit()
        finally:
            conn.close()

    # --- main entry ---

    def run(self) -> RunnerResult:
        cfg = self.config
        # 1. acquire_lock
        try:
            lock = guards.acquire_lock(cfg.pid_path)
        except guards.LockContention as exc:
            self.emit_err(f"deploy refused: {exc}")
            return RunnerResult(
                exit_code=2,
                correlation_id=None,
                sha_before="",
                sha_after="",
                phase_terminal="precondition_lock",
                detail=str(exc),
            )
        try:
            return self._run_locked()
        finally:
            lock.release()

    def _run_locked(self) -> RunnerResult:
        cfg = self.config
        # 2. idempotency
        idem = guards.idempotency_check(cfg.repo, cfg.branch)
        if idem.is_noop:
            self.emit(
                f"no changes to deploy (HEAD == origin/{cfg.branch} @ {idem.sha_local})"
            )
            return RunnerResult(
                exit_code=0,
                correlation_id=None,
                sha_before=idem.sha_local,
                sha_after=idem.sha_local,
                phase_terminal="noop",
            )
        sha_before = idem.sha_local
        sha_after_target = idem.sha_remote

        # 3. market hours
        mh = guards.market_hours_guard()
        if not mh.allowed:
            return self._fail_precondition(
                sha_before, "market_hours_guard", mh.refusal_reason(), 2
            )

        # 4. dirty tree
        dt = guards.dirty_tree_check(cfg.repo)
        if dt.is_dirty and not cfg.allow_dirty:
            return self._fail_precondition(
                sha_before,
                "precondition_dirty_tree",
                f"working tree dirty:\n{dt.porcelain}",
                2,
            )

        # 5. secrets present
        sec = guards.secrets_present(cfg.env_path)
        if not sec.allowed:
            return self._fail_precondition(
                sha_before,
                "precondition_secrets",
                f"missing required secrets: {', '.join(sec.missing)}",
                2,
            )

        # 6. emit DEPLOY_STARTED
        started_ts = _utcnow_ms()
        correlation_id = _make_correlation_id(sha_before, started_ts)
        self.emit(f"deploy correlation_id: {correlation_id}")
        self._append(
            audit.DeployStartedPayload(
                sha_before=sha_before,
                sha_after=sha_after_target,
                branch=cfg.branch,
                triggered_by=cfg.triggered_by,
                dry_run=cfg.dry_run,
                allow_dirty=cfg.allow_dirty,
                health_window_s=cfg.health_window_s,
            ),
            correlation_id=correlation_id,
        )
        t_start = time.monotonic()

        # 7. pull
        pull_result = steps.pull(cfg.repo, cfg.branch)
        if not pull_result.ok:
            return self._fail_after_start(
                correlation_id, sha_before, sha_after_target, "pull",
                pull_result.detail, exit_code=1, rollback=False, started_ts=started_ts,
            )
        sha_after = pull_result.sha_after

        # 8. kernel_check (informational)
        kreport = steps.kernel_check(cfg.repo, sha_before, sha_after)
        if not kreport.is_clean:
            self._append(
                audit.DeployKernelTouchedPayload(
                    sha_before=sha_before,
                    sha_after=sha_after,
                    touched_paths=[t.path for t in kreport.touches],
                    touched_groups=list(kreport.touched_groups),
                    triggered_by=cfg.triggered_by,
                ),
                correlation_id=correlation_id,
            )

        # 9. canary_gate (auto-tuner only)
        if cfg.triggered_by == "auto-tuner":
            cg = steps.canary_gate(
                cfg.db_path, cfg.ruleset_sha256, sha_after,
            )
            if not cg.ok:
                return self._fail_after_start(
                    correlation_id, sha_before, sha_after, "canary_gate",
                    cg.detail, exit_code=2, rollback=False, started_ts=started_ts,
                )

        # 10. sync
        sync_result = steps.sync(cfg.repo)
        if not sync_result.ok:
            return self._fail_after_start(
                correlation_id, sha_before, sha_after, "sync",
                sync_result.detail, exit_code=1, rollback=True, started_ts=started_ts,
            )

        # 11. migrate
        mig_result = steps.migrate_live(cfg.db_path)
        if not mig_result.ok:
            return self._fail_after_start(
                correlation_id, sha_before, sha_after, "migrate",
                mig_result.detail, exit_code=1, rollback=True, started_ts=started_ts,
            )

        # 12. dry_run_check (config)
        dr_result = steps.dry_run_config(cfg.config_path)
        if not dr_result.ok:
            return self._fail_after_start(
                correlation_id, sha_before, sha_after, "dry_run",
                dr_result.detail, exit_code=1, rollback=True, started_ts=started_ts,
            )

        # 13. if dry_run, emit COMPLETED(dry_run) and return
        if cfg.dry_run:
            duration = time.monotonic() - t_start
            self._append(
                audit.DeployCompletedPayload(
                    sha_before=sha_before,
                    sha_after=sha_after,
                    phase="dry_run",
                    duration_s=duration,
                ),
                correlation_id=correlation_id,
            )
            return RunnerResult(
                exit_code=0,
                correlation_id=correlation_id,
                sha_before=sha_before,
                sha_after=sha_after,
                phase_terminal="dry_run",
            )

        # 14. stop_worker
        stop_result = self.supervisor.stop_worker()
        if not stop_result.ok:
            return self._fail_after_start(
                correlation_id, sha_before, sha_after, "stop_worker",
                stop_result.stderr or "supervisor.stop_worker failed",
                exit_code=1, rollback=False, started_ts=started_ts,
            )

        # 15. start_worker
        start_result = self.supervisor.start_worker()
        if not start_result.ok:
            return self._fail_after_start(
                correlation_id, sha_before, sha_after, "start_worker",
                start_result.stderr or "supervisor.start_worker failed",
                exit_code=1, rollback=True, started_ts=started_ts,
            )

        # 16. health_check
        hc = steps.health_check(
            cfg.db_path, started_ts, window_s=cfg.health_window_s,
        )
        if not hc.ok:
            return self._fail_after_start(
                correlation_id, sha_before, sha_after, "health_check",
                hc.detail, exit_code=1, rollback=True, started_ts=started_ts,
            )

        # 17. success
        duration = time.monotonic() - t_start
        self._append(
            audit.DeployCompletedPayload(
                sha_before=sha_before,
                sha_after=sha_after,
                phase="live",
                duration_s=duration,
            ),
            correlation_id=correlation_id,
        )
        return RunnerResult(
            exit_code=0,
            correlation_id=correlation_id,
            sha_before=sha_before,
            sha_after=sha_after,
            phase_terminal="live",
        )

    def _fail_precondition(
        self,
        sha_before: str,
        phase: str,
        reason: str,
        exit_code: int,
    ) -> RunnerResult:
        """Pre-DEPLOY_STARTED failure. Emit a DEPLOY_FAILED row for forensics."""
        self.emit_err(f"deploy refused: {reason}")
        # We still emit a DEPLOY_FAILED row for forensics on the precondition
        # failure (FR-D03 only mandates one of COMPLETED/FAILED *if* STARTED
        # was emitted; here we add the FAILED proactively so an audit query
        # `WHERE event_type LIKE 'DEPLOY_%'` finds the blocked attempt).
        self._append(
            audit.DeployFailedPayload(
                sha_before=sha_before,
                sha_after=None,
                phase=phase,  # type: ignore[arg-type]
                reason=reason,
                exit_code=exit_code,
            ),
            correlation_id=None,
        )
        return RunnerResult(
            exit_code=exit_code,
            correlation_id=None,
            sha_before=sha_before,
            sha_after="",
            phase_terminal=phase,
            detail=reason,
        )

    def _fail_after_start(
        self,
        correlation_id: str,
        sha_before: str,
        sha_after: str,
        phase: str,
        reason: str,
        exit_code: int,
        *,
        rollback: bool,
        started_ts: str,
    ) -> RunnerResult:
        """Post-DEPLOY_STARTED failure. Emit DEPLOY_FAILED + attempt rollback if requested."""
        self.emit_err(f"deploy failed at phase={phase}: {reason}")
        self._append(
            audit.DeployFailedPayload(
                sha_before=sha_before,
                sha_after=sha_after,
                phase=phase,  # type: ignore[arg-type]
                reason=reason,
                exit_code=exit_code,
            ),
            correlation_id=correlation_id,
        )
        rolled_back = False
        if rollback:
            rb = steps.rollback(
                self.config.repo,
                sha_before,
                self.supervisor,
                self.config.db_path,
                started_ts,
                health_window_s=self.config.health_window_s,
            )
            if rb.ok:
                self._append(
                    audit.DeployRolledBackPayload(
                        sha_before=sha_before,
                        sha_after_failed=sha_after,
                        rolled_back_phase=phase,
                    ),
                    correlation_id=correlation_id,
                )
                rolled_back = True
            else:
                # rollback failed → emit a second DEPLOY_FAILED with phase=rollback
                self._append(
                    audit.DeployFailedPayload(
                        sha_before=sha_before,
                        sha_after=sha_after,
                        phase="rollback",
                        reason=f"rollback failed: {rb.detail}",
                        exit_code=1,
                    ),
                    correlation_id=correlation_id,
                )
        return RunnerResult(
            exit_code=exit_code,
            correlation_id=correlation_id,
            sha_before=sha_before,
            sha_after=sha_after,
            phase_terminal=phase,
            detail=reason,
            rolled_back=rolled_back,
        )
