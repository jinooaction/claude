# Tasks — Spec 006 Deploy Automation

> ✅ **SHIPPED — 전부 완료, main 에 머지됨.** `src/auto_invest/deploy/`
> (runner·steps·guards·supervisor·kernel_guard·audit_query) 구현 완료, `auto-invest
> deploy` CLI + 배포 테스트 8종(`test_deploy_*`) 통과. K4 추가 이벤트 5종
> (`DEPLOY_STARTED`/`COMPLETED`/`FAILED`/`ROLLED_BACK`/`KERNEL_TOUCHED`)은 `audit.py`
> 에 존재. 이 체크박스들은 한동안 0% 로 표시된 **stale 상태**였음(2026-05-24 재조정).
> 실제 상태는 코드+테스트가 진실. 머지 즉시 자동 배포(VIII.B `deploy-on-merge.yml`)
> 와 함께 가동 중.

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) |
**Constitution**: v3.0.0 (IX.A forensic kernel; IX.B-1 repealed; IX.D operator autonomy supremacy)

Dependency-ordered task list. Each task is independently testable.
Phases respect MVP-first ordering: Phase 1-3 deliver a working
`auto-invest deploy --dry-run` end-to-end; Phase 4 adds the live
deploy path; Phase 5 adds operator install + idempotency; Phase 6
is polish.

## Phase 1 — Setup

- [x] **T001** Create `src/auto_invest/deploy/` skeleton: `runner.py`, `guards.py`, `steps.py`, `supervisor.py`, `audit_query.py` (empty modules with module docstring). `__init__.py` and `kernel_guard.py` already exist.
- [x] **T002** Verify zero new runtime deps (R-D12) by running `uv run python -c "import subprocess, tomllib, pydantic, typer, exchange_calendars"`. No `pyproject.toml` change.

## Phase 2 — Foundational (BLOCKS US1/US2/US3)

⚠ **K4 touch**: this phase modifies `src/auto_invest/persistence/audit.py`, which is K4 in the kernel manifest. Under constitution v3.0.0 this is permitted under the autonomous workflow; the K4 commit hash is called out in the PR description for forensic-attention per CLAUDE.md.

- [x] **T003** [K4 touch] Extend `audit.py` `EventType` union with five new literals: `DEPLOY_STARTED`, `DEPLOY_COMPLETED`, `DEPLOY_FAILED`, `DEPLOY_ROLLED_BACK`, `DEPLOY_KERNEL_TOUCHED`. Keep `DEPLOY_BLOCKED_KERNEL_TOUCH` for backward compatibility (deprecated, no longer emitted).
- [x] **T004** [K4 touch] Add five frozen pydantic payload classes in `audit.py`: `DeployStartedPayload`, `DeployCompletedPayload`, `DeployFailedPayload`, `DeployRolledBackPayload`, `DeployKernelTouchedPayload` — schema per `data-model.md`.
- [x] **T005** `tests/unit/test_deploy_audit.py` — payload roundtrip (model_validate + model_dump_json), frozen behaviour, `event_type` discriminator pinned, `extra="forbid"` rejection.

## Phase 3 — US1 dry-run path (P1, MVP)

**Goal**: `auto-invest deploy --dry-run` runs end-to-end against a fake repo + dryrun supervisor and emits `DEPLOY_STARTED` → `DEPLOY_COMPLETED(phase=dry_run)`.

- [x] **T006** `deploy/guards.py` — `market_hours_guard(now=None) -> MarketHoursDecision` using `exchange_calendars` (same XNYS calendar as the worker). Returns next-allowed deploy window UTC on refuse.
- [x] **T007** `deploy/guards.py` — `dirty_tree_check(repo: Path) -> DirtyTreeDecision` using `git status --porcelain`. Honours `allow_dirty=True` override.
- [x] **T008** `deploy/guards.py` — `secrets_present(env_path: Path) -> SecretsDecision` reusing `auto_invest.config.loader` checks; returns missing keys.
- [x] **T009** `deploy/guards.py` — `acquire_lock(pid_path: Path) -> LockHandle` with stale-detection per R-D3 (POSIX `/proc/<pid>` + cmdline match). Releases on `__exit__`.
- [x] **T010** `deploy/guards.py` — `idempotency_check(repo, branch) -> bool` per R-D4 (returns True if HEAD == origin/<branch> after fetch).
- [x] **T011** `tests/unit/test_deploy_guards.py` — market hours decisions (open/closed/early-close), dirty/clean trees, secrets present/missing, lock acquire/contention/stale-recovery, idempotency true/false.
- [x] **T012** `deploy/supervisor.py` — `Supervisor` protocol with `stop_worker()` / `start_worker()` / `is_running()` returning structured results.
- [x] **T013** `deploy/supervisor.py` — `DryRunSupervisor` capturing intents in-memory; never calls subprocess. `SystemdSupervisor` calling `systemctl restart <unit>` via `subprocess.run`.
- [x] **T014** `tests/unit/test_deploy_supervisor.py` — dryrun captures intents; systemd is exercised only via mocked `subprocess.run` (no real systemctl).
- [x] **T015** `deploy/steps.py` — `pull(repo, branch) -> PullResult` (`sha_before`, `sha_after`); `sync(repo) -> SyncResult` calling `uv sync --frozen`; both subprocess-based, structured failure surfaces.
- [x] **T016** `deploy/steps.py` — `kernel_check(repo, sha_before, sha_after) -> KernelTouchReport` thin wrapper over `kernel_guard.kernel_diff_check`. Returns same report; runner decides to emit `DEPLOY_KERNEL_TOUCHED` informationally.
- [x] **T017** `deploy/steps.py` — `migrate_live(db_path)` calling `auto_invest.persistence.db.migrate` against the live DB; `dry_run_config(config_path)` reusing `config.loader.load_config(..., dry_run=True)`.
- [x] **T018** `deploy/audit_query.py` — helpers `wait_for_worker_started(db, after_ts, timeout_s)` and `errors_since(db, after_ts)` polling the audit log. Used by health-check.
- [x] **T019** `deploy/runner.py` — `DeployRunner` class. Constructor takes config (paths, supervisor, branch, dry_run, allow_dirty, health_window_s, triggered_by, ruleset_sha256). Method `run() -> DeployResult` orchestrates phases 1-14 from `contracts/deploy-cli.md`. Emits `DEPLOY_STARTED` + `DEPLOY_COMPLETED(phase=dry_run)` for dry-run path. Correlation id per R-D5.
- [x] **T020** `tests/unit/test_deploy_runner.py` — dry-run success; precondition failures (market open, dirty tree, missing secrets, lock held); idempotent no-op exit-0-no-audit; kernel-touch emits `DEPLOY_KERNEL_TOUCHED` and continues.

## Phase 4 — US1 live deploy + rollback (P1)

**Goal**: `auto-invest deploy` runs the full live path: stop_worker → start_worker → health_check, with rollback on failure.

- [x] **T021** `deploy/steps.py` — `health_check(db, deploy_started_ts, window_s)` polling per R-D2 / R-D9: requires `WORKER_STARTED` newer than `deploy_started_ts`, zero `ERROR`, zero `DATA_QUALITY_ISSUE` referencing telemetry. 1 s poll cadence.
- [x] **T022** `deploy/steps.py` — `rollback(repo, sha_before, supervisor, health_window_s) -> RollbackResult` per R-D6: checkout sha_before, uv sync, start_worker, health_check. Pure step; runner decides when to invoke.
- [x] **T023** `deploy/runner.py` — wire live path: stop_worker (waiting up to 10 s for `WORKER_STOPPED` per R-D8), start_worker, health_check, emit `DEPLOY_COMPLETED(phase=live)`. On failure path: emit `DEPLOY_FAILED(phase=<failing>)` → call rollback → on success emit `DEPLOY_ROLLED_BACK` and exit 1; on rollback failure emit `DEPLOY_FAILED(phase=rollback)` and exit 1.
- [x] **T024** `tests/unit/test_deploy_runner.py` — extend with live success, migrate failure → rollback success, health-check timeout → rollback success, rollback-of-rollback fails → no infinite loop.

## Phase 5 — US2 audit lineage (P1)

**Goal**: every deploy reconstructible from the audit log alone via `correlation_id` join.

- [x] **T025** `tests/integration/test_deploy_end_to_end.py` — full flow with a real temp git repo (init + commit + remote) and `DryRunSupervisor`. Asserts:
  - no-op: zero audit rows, exit 0, < 2 s wall clock.
  - dry-run: STARTED + COMPLETED(phase=dry_run), one correlation_id joins them.
  - live success: STARTED + COMPLETED(phase=live), worker started/stopped/started visible via correlation_id and timestamps.
  - migrate failure: STARTED + FAILED(phase=migrate) + ROLLED_BACK, all sharing one correlation_id.
  - kernel touch: STARTED + KERNEL_TOUCHED + COMPLETED, touched_paths populated.
- [x] **T026** `deploy/runner.py` — add canary-gate phase per R-D10 / FR-D14 when `triggered_by="auto-tuner"`. Read most-recent `CANARY_PASSED` row; assert age ≤ 24 h AND `ruleset_sha256` matches CLI flag AND `code_sha256` matches `sha_after`. Failure: `DEPLOY_FAILED(phase=canary_gate)` exit 2. Manual deploys bypass per IX.D.
- [x] **T027** `tests/integration/test_deploy_end_to_end.py` — extend with auto-tuner scenarios: missing `CANARY_PASSED` → exit 2; stale (> 24 h) → exit 2; mismatched ruleset_sha256 → exit 2; matching → deploy continues.

## Phase 6 — US3 scheduler-friendly + operator install (P2)

**Goal**: timer-safe idempotent invocation + systemd templates the operator can copy-paste.

- [x] **T028** `src/auto_invest/cli.py` — register `deploy` subcommand with the flag surface from `contracts/deploy-cli.md`. Pre-condition check enforces `--health-window-s >= 90`. Stdout first line is `deploy correlation_id: <hex>` for non-noop paths.
- [x] **T029** `tests/unit/test_deploy_cli.py` — flag parsing, exit codes, stdout contract (correlation id first line, no-op message), `--health-window-s 60` rejected at parse time.
- [x] **T030** `deploy/auto-invest.service` — systemd unit template for the worker (User=auto-invest, WorkingDirectory=/opt/auto-invest, ExecStart=`uv run auto-invest run --capital ${AUTO_INVEST_CAPITAL}`, Restart=on-failure, StandardOutput=journal).
- [x] **T031** `deploy/auto-invest-deploy.service` — systemd one-shot for the deploy script (Type=oneshot, ExecStart=`uv run auto-invest deploy`).
- [x] **T032** `deploy/auto-invest-deploy.timer` — systemd timer with OnCalendar excluding US regular hours (UTC), Persistent=true.
- [x] **T033** `deploy/README.md` — operator copy-paste install steps mirroring `quickstart.md` § 2.

## Phase 7 — Polish

- [x] **T034** `README.md` — add `auto-invest deploy` section under CLI cheatsheet + link to `specs/006-deploy-automation/quickstart.md`.
- [x] **T035** `uv run ruff check src tests` clean.
- [x] **T036** `uv run pytest -q` — all green; expected count is `577 (main baseline) + new tests from this spec`.
- [x] **T037** Import smoke: `uv run python -c "from auto_invest.deploy import runner, guards, steps, supervisor, audit_query"` succeeds.
- [x] **T038** Quickstart smoke (manual): `uv run auto-invest deploy --dry-run` against `data/auto_invest.db` — records correlation id, completes with exit 0.

## Tasks count

38 tasks across 7 phases. Estimate: one session to deliver Phases 1-3 (dry-run MVP, ~20 tasks); a second session if needed for Phases 4-7 (live deploy + rollback + systemd + polish, ~18 tasks).

## Out of scope (deferred)

- Multi-host deploys / blue-green / containers.
- Push notifications.
- Rollback to arbitrary historical sha (only one commit back).
- Spec 005 autonomous tuner caller (the `--triggered-by=auto-tuner` channel is wired but has no producer yet).
