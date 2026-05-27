# Tasks: Automated US-Equity Trading MVP

**Input**: Design documents from `specs/001-automated-trading-mvp/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Generated for every module covered by the constitution's "test gate" — risk gates, order validation, reconciliation, audit log, secret handling, configuration validation, broker resilience, and trigger evaluation. Pure plumbing (CLI ergonomics, README, etc.) is shipped without dedicated tests.

**Organization**: Tasks are grouped by user story so each phase ends at an independently-demonstrable checkpoint.

## Format

`- [ ] T### [P?] [Story?] Description with file path`

- `[P]` — task touches a different file than its phase peers and has no incomplete dependencies; eligible for parallel execution.
- `[US1] / [US2] / [US3]` — user-story phase tasks only. Setup, Foundational, and Polish phases carry no story label.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton, dev dependencies, repo hygiene. Most of this is already done from the original scaffolding — these tasks fill the remaining gaps so user-story work can begin without churn.

- [ ] T001 Create source-tree skeleton with empty `__init__.py` files: `src/auto_invest/{config,broker,market_data,strategy,risk,execution,persistence,reconciliation,reports,worker}/__init__.py` plus `tests/{unit,integration,fixtures/{kis_responses,rules}}/` and top-level `data/` and `config/` directories.
- [ ] T002 Add runtime dependencies via `uv add httpx tenacity pandas ta exchange_calendars pydantic python-dotenv apscheduler typer` and verify `pyproject.toml` reflects them. (Note: `ta` substituted for `pandas-ta` per the R-2 implementation-time amendment in `research.md`.)
- [ ] T003 Add dev dependencies via `uv add --dev pytest-asyncio freezegun respx` and verify `pyproject.toml`.
- [ ] T004 [P] Create `.env.example` documenting required secrets (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`) with inline comments and a header noting that `.env` is gitignored.
- [ ] T005 [P] Extend `.gitignore` to add `data/`, `config/rules.toml` (operator-specific), `*.db-wal`, `*.db-shm`, and `.pid`.
- [ ] T006 [P] Add sample TOML fixture at `tests/fixtures/rules/sample-canary.toml` matching the schema in `contracts/rules-config.md` and a `tests/fixtures/kis_responses/.gitkeep` placeholder.
- [ ] T007 [P] Update `README.md` to point operators to `specs/001-automated-trading-mvp/quickstart.md` as the primary entrypoint.

**Checkpoint**: Repo lays out exactly as `plan.md` declares; `uv sync` and `uv run pytest` still succeed (only the existing smoke test runs).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting infrastructure every user story depends on — logging with secret redaction, SQLite + audit log, configuration loader, halt mechanism, market calendar, and the resilient broker client.

**⚠️ CRITICAL**: No user-story phase begins until this phase is complete.

### Logging & secrets (constitution V)

- [ ] T008 Implement JSON structured logging + `RedactionFilter` + `register_secret()` in `src/auto_invest/logging_config.py` so every handler runs through redaction.
- [ ] T009 [P] Add `tests/unit/test_secret_masking.py` covering: `register_secret` registers, log records are redacted, exception args/tracebacks are redacted, idempotent registration.

### Persistence + audit log (constitution IV)

- [ ] T010 Implement SQLite connection factory + WAL pragma + migration runner in `src/auto_invest/persistence/db.py`.
- [ ] T011 Author migration `0001_initial.sql` defining `audit_log`, `orders`, `order_state_history`, `fills`, `price_bars`, `current_positions`, `reconciliation_runs`, `strategy_stage_history` exactly as `data-model.md` specifies, at `src/auto_invest/persistence/migrations/0001_initial.sql`.
- [ ] T012 [US1 prereq] Implement append-only audit writer + per-event-type pydantic payload models in `src/auto_invest/persistence/audit.py` (depends on T010, T011).
- [ ] T013 [P] Add `tests/unit/test_audit.py` covering: monotonic seq, payload validation per event type, refusal of UPDATE/DELETE on audit tables, correlation_id linkage across rows.

### Configuration (FR-001, FR-011, FR-015)

- [ ] T014 [P] Implement `SizingCaps` pydantic model with cross-field invariants (`per_trade_pct ≤ per_symbol_pct ≤ global_exposure_pct`, `canary_capital_pct ≤ per_symbol_pct`) in `src/auto_invest/config/caps.py`.
- [ ] T015 [P] Implement `Whitelist` model (frozen sets for symbols/accounts/order_types/sessions) in `src/auto_invest/config/whitelist.py`.
- [ ] T016 [P] Implement `Trigger` discriminated union (`TimeTrigger`/`PriceTrigger`/`IndicatorTrigger`) + `Action` + `TradingRule` models in `src/auto_invest/config/rules.py`.
- [ ] T017 Implement `config/loader.py`: read TOML via `tomllib`, expand `${ENV_VAR}` against `.env`, validate via pydantic, refuse-on-missing-secret, refuse-on-unknown-symbol, freeze the result, in `src/auto_invest/config/loader.py` (depends on T014, T015, T016).
- [ ] T018 [P] Add `tests/unit/test_caps.py` covering all cross-field invariants and bounds.
- [ ] T019 [P] Add `tests/unit/test_whitelist.py` covering frozen invariant + uppercase normalization + duplicate rejection.
- [ ] T020 [P] Add `tests/unit/test_rules_loader.py` covering every "refuse to start" rule from `contracts/rules-config.md` (one test per validation rule) (depends on T017).

### Halt mechanism (FR-013)

- [ ] T021 [P] Implement halt-flag detection + write/clear helpers + JSON payload schema in `src/auto_invest/worker/halt.py`.
- [ ] T022 [P] Add `tests/unit/test_halt.py` covering: write creates payload with timestamp+reason, presence-detection across restarts (simulated), `resume` removes the file.

### Market calendar (FR-003)

- [ ] T023 [P] Implement `worker/schedule.py` wrapping `exchange_calendars` with helpers `is_session_open(now)`, `next_session_open(now)`, `next_session_close(now)`, `is_us_holiday(date)`.
- [ ] T024 [P] Add `tests/unit/test_schedule.py` using `freezegun` to assert correct boundaries on regular days, half-days, holidays, and DST transition days.

### Broker auth + client (FR-008, constitution VII)

- [ ] T025 [P] Implement KIS access-token issuance + cached refresh in `src/auto_invest/broker/auth.py`; persist token state to a small file under `data/` so refresh survives restarts.
- [ ] T026 Implement `broker/client.py`: httpx `AsyncClient` wrapper with per-host `AsyncTokenBucket` rate limiter, `CircuitBreaker` (closed/open/half-open), and `tenacity` retry with exponential backoff + jitter, in `src/auto_invest/broker/client.py` (depends on T025).
- [ ] T027 [P] Implement `broker/models.py`: `OrderRequest`, `OrderResult`, `Quote`, `PositionSnapshot`, `BalanceSnapshot` pydantic models in `src/auto_invest/broker/models.py`.
- [ ] T028 Implement `broker/overseas.py`: thin functions for the v1 endpoints — `get_quote`, `place_order`, `cancel_order`, `get_positions`, `get_balance` — using the wrapped client, in `src/auto_invest/broker/overseas.py` (depends on T026, T027).
- [ ] T029 Add `tests/integration/test_broker_client.py` with `respx`-recorded fixtures: retry on 5xx, no-retry on 4xx, breaker opens after N failures, breaker half-open after cooldown, rate limiter delays without dropping (depends on T026).

**Checkpoint**: All user stories now have a stable foundation: every persistence write is auditable, every external call is resilient, every secret is redacted, every config error fails-closed before the loop starts.

---

## Phase 3: User Story 1 — Sleep through US market open and wake up to executed trades (Priority: P1) 🎯 MVP

**Goal**: A configured rule fires during US regular hours, passes deny-by-default + sizing gates, reaches the broker, and every step is captured in the audit log. The operator can run the worker overnight and audit results in the morning by reading the SQLite audit log.

**Independent Test**: With a single canary rule against a mocked broker that accepts orders, start the worker; verify the audit log contains `WORKER_STARTED`, `ORDER_INTENT`, `ORDER_SUBMITTED`, `FILL`, and `WORKER_STOPPED` rows in the expected order, and that an order placed against a non-whitelisted symbol is rejected with `ORDER_REJECTED_BY_GATE`.

### Risk gates (constitution I, II)

- [ ] T030 [P] [US1] Add `tests/unit/test_risk_gates.py` covering each gate: `whitelist_gate`, `halt_gate`, `per_trade_cap_gate`, `per_symbol_cap_gate`, `global_exposure_gate`, `stage_uniqueness_gate` — including the boundary just-at-cap and just-over-cap.
- [ ] T031 [US1] Implement `risk/gates.py` with all six gates returning `GateDecision(allow: bool, gate: str, reason: str | None, metadata: dict)`, in `src/auto_invest/risk/gates.py`.

### Position cache + market data (FR-016, FR-017)

- [ ] T032 [P] [US1] Implement `persistence/positions.py` with `current_positions` cache + `rebuild_from_fills()` deterministic procedure, in `src/auto_invest/persistence/positions.py` (depends on T012).
- [ ] T033 [P] [US1] Implement `market_data/store.py` PriceBar persistence (insert-or-skip, no UPSERT) in `src/auto_invest/market_data/store.py`.
- [ ] T034 [P] [US1] Implement `market_data/quality.py` with gap detection + staleness threshold + per-symbol "armed/not-armed" decision, in `src/auto_invest/market_data/quality.py`.
- [ ] T035 [US1] Implement `market_data/feed.py` polling/subscription glue — pulls bars via `broker/overseas.py`, writes through `store.py`, marks quality via `quality.py`, in `src/auto_invest/market_data/feed.py` (depends on T028, T033, T034).

### Strategy: indicators + triggers + canary (FR-001, FR-014, FR-016)

- [ ] T036 [P] [US1] Implement `strategy/indicators.py`: pandas-ta facade with strict input validation (sufficient bars, monotonic ts, no NaNs) in `src/auto_invest/strategy/indicators.py`.
- [ ] T037 [P] [US1] Add `tests/unit/test_indicators.py` covering: insufficient bars raises, NaN raises, non-monotonic raises, EMA/SMA/RSI sanity values match a known reference.
- [ ] T038 [US1] Implement `strategy/triggers.py` evaluators for `TimeTrigger`/`PriceTrigger`/`IndicatorTrigger` with cooldown enforcement and warm-up tracking, in `src/auto_invest/strategy/triggers.py` (depends on T036).
- [ ] T039 [P] [US1] Add `tests/unit/test_triggers.py` covering: each family fires only on its declared condition; cooldown suppresses re-fire; indicator trigger stays not-armed until N bars accumulate.
- [ ] T040 [P] [US1] Implement `strategy/canary.py` tracking rolling drawdown per rule and emitting `STRATEGY_PAUSED` events when below acceptance for the configured duration, in `src/auto_invest/strategy/canary.py`.
- [ ] T041 [P] [US1] Add `tests/unit/test_canary_autopause.py` covering: pause triggers exactly at the threshold breach, never on transient noise, persists pause across restarts.

### Execution + worker loop (FR-004 through FR-006, FR-013)

- [ ] T042 [US1] Implement `execution/order_router.py`: receives a fired trigger, builds `OrderRequest`, runs every gate from `risk/gates.py` (in declared order), submits via `broker/overseas.py`, writes audit rows for every step (`ORDER_INTENT` → `ORDER_SUBMITTED|ORDER_REJECTED_BY_GATE` → `FILL`/`CANCEL`), enforces stage-uniqueness on startup, in `src/auto_invest/execution/order_router.py` (depends on T031, T012, T028, T032).
- [ ] T043 [US1] Add `tests/integration/test_order_router.py` covering: happy-path submit+fill, gate rejection short-circuits before any broker call, broker 5xx triggers retry-then-success, breaker open results in `ERROR` audit row not `ORDER_REJECTED_BY_GATE`.
- [ ] T044 [US1] Implement `worker/loop.py`: asyncio main loop, lifecycle (start, run, stop), one task per active rule, signal handlers for graceful shutdown, halt-flag check at startup + every tick, in `src/auto_invest/worker/loop.py` (depends on T038, T042, T021, T023).
- [ ] T045 [US1] Add `tests/integration/test_worker_loop.py`: dry-run end-to-end (no broker contact), normal run with `respx`-mocked broker covering one rule firing once and reaching `FILL`.

### Operator CLI (contract: `contracts/cli.md`)

- [ ] T046 [US1] Implement Typer app with `run` (incl. `--dry-run`, `--config`, `--db`) in `src/auto_invest/cli.py`, including the startup sequence steps from `contracts/cli.md`.
- [ ] T047 [US1] Wire `python -m auto_invest` to `cli.app` in `src/auto_invest/__main__.py`.

**Checkpoint**: User Story 1 fully functional. Operator can run the worker, see triggers fire, see orders gated correctly, see fills audited. The worker shuts down cleanly. Zero LLM calls happen anywhere.

---

## Phase 4: User Story 2 — Daily reconciliation prevents silent state drift (Priority: P2)

**Goal**: After each US session close, the worker reconciles its local positions and cash against KIS and halts new orders if any mismatch is found. Operator can clear the halt with a logged reason.

**Independent Test**: Inject a synthetic mismatch (e.g., add a fake row to `current_positions` that doesn't match the broker fixture); run reconciliation; verify `RECONCILIATION_MISMATCH` is recorded, halt-flag is set, and subsequent order intents are rejected by the halt gate.

- [X] T048 [P] [US2] Add `tests/integration/test_reconciliation.py` covering: positions match, qty mismatch, cash mismatch outside tolerance, broker error → `INCONCLUSIVE` result, mismatch sets halt and the halt message includes the diff.
- [X] T049 [US2] Implement `reconciliation/runner.py`: pull broker positions+balance, compare against `current_positions`, write `reconciliation_runs` row + matching audit event, set halt flag on mismatch with the diff payload, in `src/auto_invest/reconciliation/runner.py` (depends on T032, T028, T012, T021).
- [X] T050 [US2] Invoke reconciliation at session close from `worker/loop.py` and expose a manual `reconcile` command (depends on T044, T049). **NOTE**: implemented via tick-loop session-close *transition* detection (`Worker._session_was_open` flips open→closed → `_reconcile_at_close`), not APScheduler — the worker is an asyncio tick loop, not APScheduler-based. Manual path is the `auto-invest reconcile` CLI command. Live-only (paper has virtual positions); errors isolated so the tick never breaks.
- [X] T051 [US2] Extend `cli.py` with `halt --reason "<text>"` and `resume --confirm` subcommands per `contracts/cli.md`, ensuring both write the corresponding audit rows.
- [X] T052 [P] [US2] Extend worker-loop tests to assert: reconciliation runs at session close, mismatch halts within one tick. **NOTE**: covered by `tests/integration/test_worker_reconcile_at_close.py` (OK/mismatch-halts/paper-skip/fires-once/startup-closed-no-trigger).

**Checkpoint**: User Stories 1 + 2 work together. End-of-session reconciliation is automatic; operator-controlled halt/resume is covered.

---

## Phase 5: User Story 3 — Morning report makes daily activity auditable in minutes (Priority: P3)

**Goal**: After session close, a single Markdown + JSON daily report at `data/reports/{date}/` summarizes everything from the audit log. Operator can read the morning report and trust it as a complete summary.

**Independent Test**: After a recorded session containing fills, gate rejections, and one reconciliation mismatch (cleared with a reason), generate the report; verify all sections from `contracts/daily-report.md` are present, and that re-running with the same date produces byte-identical output unless audit-log content changed.

- [ ] T053 [P] [US3] Add `tests/unit/test_daily_report.py`: byte-stability across re-runs, all sections rendered, JSON ↔ Markdown numeric agreement, empty-day rendered as `(none)` rather than omitted.
- [ ] T054 [US3] Implement `reports/daily.py` reading the audit log + positions cache, rendering Markdown to `data/reports/{date}/daily-report.md` and a sibling JSON, exactly per `contracts/daily-report.md`, in `src/auto_invest/reports/daily.py` (depends on T012, T032).
- [ ] T055 [US3] Extend `cli.py` with `report [--date YYYY-MM-DD]` subcommand defaulting to the most recent completed session.
- [ ] T056 [US3] Extend `cli.py` with `status` subcommand printing one-screen JSON summary (worker pid, halt state, last reconciliation, today's order counts, current positions) — read-only, no DB writes.
- [ ] T057 [US3] Wire APScheduler in `worker/loop.py` to auto-generate the report after every successful end-of-session reconciliation (depends on T050, T054).

**Checkpoint**: All three user stories are independently functional. Operator gets the full overnight value: trades executed safely, positions reconciled, morning report ready.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final hardening, documentation, and validation that the whole system meets the success criteria from `spec.md`.

- [x] T058 [P] Implement `db migrate` CLI subcommand with PID-file safety check (refuses if a worker process is detected), in `src/auto_invest/cli.py`.
- [x] T059 [P] Add `--dry-run` end-to-end smoke test scripted in `tests/integration/test_quickstart_dry_run.py` that follows the quickstart steps against `tests/fixtures/rules/sample-canary.toml`.
- [x] T060 [P] Performance smoke test: assert trigger-eval p95 < 1 s with 20 active rules using stub triggers, in `tests/integration/test_performance.py`.
- [x] T061 [P] Run `uv run ruff format .` and `uv run ruff check --fix .` across `src/` and `tests/`; commit any formatting deltas in a separate commit.
- [x] T062 [P] Manually validate `quickstart.md` against a fresh checkout (operator's MacBook, 2026-05): clone via `gh repo clone`, install uv, `uv sync`, `uv run python scripts/live_smoke.py` → live AAPL quote `$279.4475` returned via real KIS account.
- [x] T063 Update `README.md` with a short "what this does / what it does not do (yet)" summary, CLI cheatsheet, and links to `quickstart.md` and the constitution.
- [x] T064 [P] Optional live KIS smoke test in `tests/integration/test_live_broker.py`, gated by `KIS_LIVE_TEST=1` (skipped otherwise). Verifies a single read-only call (`issue_token` + `get_quote("AAPL")`) against the operator's real KIS account. Run via `scripts/live_smoke.py` (interactive, hidden-input credentials). NEVER places a real order.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)** — no dependencies; can start immediately.
- **Phase 2 (Foundational)** — depends on Phase 1; **blocks all user stories**.
- **Phase 3 (US1, P1)** — depends on Phase 2; can run before Phase 4/5.
- **Phase 4 (US2, P2)** — depends on Phase 2; technically independent of Phase 3, but the recommended order is US1 → US2 because the reconciliation halt path becomes meaningful once orders flow.
- **Phase 5 (US3, P3)** — depends on Phase 2 and at least one prior story producing audit rows; trivially independent of US2 implementation, but the report's reconciliation section becomes meaningful only after US2 is in.
- **Phase 6 (Polish)** — depends on whichever user stories are in scope.

### Within each user story

- Risk-related modules: tests written **first** and observed failing before implementation (constitution VI's spirit; even though we ship without paper trading, we still TDD risk code).
- Models before services: pydantic config models (T014–T016) before loader (T017); `broker/models.py` (T027) before `broker/overseas.py` (T028); `risk/gates.py` (T031) before `execution/order_router.py` (T042).
- Services before glue: `order_router.py` (T042) before `worker/loop.py` (T044); `reconciliation/runner.py` (T049) before its scheduler wiring (T050); `reports/daily.py` (T054) before its scheduler wiring (T057).
- CLI subcommands extend `cli.py`; sequential within `cli.py` because they share a file (T046, T051, T055, T056, T058 all not [P] with each other).

### Parallel opportunities

- Phase 1: T004–T007 are all `[P]`.
- Phase 2: T009 with T013/T018/T019/T022/T024 in parallel (different test files); T014/T015/T016 in parallel (different config files); T021/T023/T025/T027 in parallel (different modules).
- Phase 3 (US1): T030/T032/T033/T034/T036/T040 in parallel (different files); T037/T039/T041 in parallel test files.
- Phase 4 (US2): T048 with T049 implementation in parallel (test first / impl second is a within-module sequence; the across-module split between test file and runner module is parallelizable).
- Phase 5 (US3): T053 in parallel with T054 (test file vs implementation).
- Phase 6: T058–T062 mostly `[P]`.

### Cross-story integration points

- The audit log writer (T012) is consumed by every later phase; it must remain backwards compatible.
- The configuration loader's frozen output (T017) is the boot-time contract for the worker; later phases should read it through a dependency injection seam, not by re-parsing.
- The halt mechanism (T021) is exercised by both US1 (gate) and US2 (reconciliation mismatch).

---

## Parallel Example: Phase 2 (Foundational)

```bash
# After T008 (logging) and T010+T011 (db schema) land, the next wave can run in parallel:

# Config models — three independent files
Task: "Implement SizingCaps in src/auto_invest/config/caps.py"
Task: "Implement Whitelist in src/auto_invest/config/whitelist.py"
Task: "Implement TradingRule + Trigger union in src/auto_invest/config/rules.py"

# Independent infrastructure modules
Task: "Implement halt-flag helpers in src/auto_invest/worker/halt.py"
Task: "Implement market calendar wrapper in src/auto_invest/worker/schedule.py"
Task: "Implement broker auth/token refresh in src/auto_invest/broker/auth.py"
Task: "Implement broker pydantic models in src/auto_invest/broker/models.py"

# And, in their own files, the matching test tasks:
Task: "tests/unit/test_secret_masking.py"
Task: "tests/unit/test_audit.py"
Task: "tests/unit/test_caps.py"
Task: "tests/unit/test_whitelist.py"
Task: "tests/unit/test_halt.py"
Task: "tests/unit/test_schedule.py"
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1: Setup → green `uv run pytest` (smoke only).
2. Phase 2: Foundational → all foundational tests pass; no broker contact has happened yet.
3. Phase 3: User Story 1 → end-to-end dry-run; with a mocked broker, full integration test passes; risk gates short-circuit non-whitelisted orders.
4. **Stop and validate**: walk through `quickstart.md` against this build. Demonstrate `auto-invest run --dry-run` and a single mocked rule firing.
5. Decide whether to ship MVP here or continue.

### Incremental delivery

- After **Phase 3**: demo "rule fires, gates protect, audit log captures".
- After **Phase 4**: demo "session close → reconciliation → halt-on-mismatch → operator clears halt".
- After **Phase 5**: demo "morning report ready in five minutes; operator audits in five minutes".
- After **Phase 6**: ship.

### When to revisit the constitution

If, during implementation, any task forces a constitution principle into a corner (e.g., a foundational test would require placing real orders), stop and amend the constitution by an explicit version bump rather than work around the principle silently. Constitution v1.0.0 is permissive enough that this should not happen, but the discipline matters more than the prediction.

---

## Notes

- Every task lists an exact file path; do not split a task across files unless an explicit dependency note says so.
- `[P]` markers reflect file-level independence. Tasks that share a file (e.g., the four CLI extensions) are not parallel even when they are otherwise independent.
- After each task — or each tightly-coupled task pair — commit. Big-bang commits across phases break the audit trail constitution-VIII calls for.
- Do not begin implementing a task whose dependencies are still incomplete; if you must, mark the dependency complete first by writing the placeholder it needs, and add the missing test in the same commit.
- Verify each "test" task observably fails before its paired implementation begins. The first commit of a test should run red.
