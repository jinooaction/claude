---

description: "Task list for spec 008 Backtest Engine implementation"
---

# Tasks: Backtest Engine

**Input**: Design documents from `specs/008-backtest-engine/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all committed at 8785298)
**Tests**: INCLUDED. Spec's safety contracts (FR-B02, FR-B06, FR-B08, FR-B12, FR-B15) are non-negotiable and require test enforcement.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with adjacent tasks (different files, no incomplete-task dependency)
- **[Story]**: Maps to user story from spec.md (US1, US2, US3)
- All paths in tasks are repo-relative
- Tests for a story MUST be written before/alongside that story's implementation

## Path Conventions

Single-package layout under `src/auto_invest/`. Tests under `tests/unit/` and `tests/integration/`. Per the plan, all new engine code lives under `src/auto_invest/backtest/`; only `audit.py` (K4) and `cli.py`, `reports/daily.py` are edited outside that package.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Skeleton directories + dependency confirmation. Nothing risky here.

- [X] T001 Create `src/auto_invest/backtest/` with empty `__init__.py`; create `tests/unit/` and `tests/integration/` placeholders confirmed
- [X] T002 Verify `pyproject.toml` already pins `pandas`, `pydantic`, `numpy` (transitive via pandas), `tomllib` (stdlib); add NO new third-party dependencies (per plan Technical Context). Confirm `uv lock` is clean.
- [X] T003 [P] Create empty `config/synthetic_shocks.toml` with placeholder structure documenting the four canonical dates (real content goes in via T029)

**Checkpoint**: directory skeleton ready; no behavior shipped.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: K4 audit-event extension + Clock primitives + kernel-guard wiring. EVERY user story consumes these.

**⚠️ CRITICAL**: No user story work may begin until Phase 2 is complete.

**⚠️ K4 NOTE**: T004 + T005 form the ONLY Kernel touch in this entire spec. They MUST be committed together as a single commit with subject `feat(008): K4 — append BACKTEST_* + LLM_CALL_STUBBED event types to audit.py` so the operator review per constitution IX.B-1 has a single, atomic, additive change to inspect. No other task may modify any file listed under `.specify/memory/kernel.toml`.

- [ ] T004 Append `BACKTEST_STARTED`, `BACKTEST_COMPLETED`, `LLM_CALL_STUBBED` to the `EventType` Union in `src/auto_invest/persistence/audit.py` (K4 — same commit as T005)
- [ ] T005 Add `BacktestStartedPayload`, `BacktestCompletedPayload`, `LLMCallStubbedPayload` pydantic models in `src/auto_invest/persistence/audit.py` per `data-model.md § Audit-log payloads` (K4 — same commit as T004)
- [ ] T006 [P] Implement `src/auto_invest/backtest/data_model.py` — `BacktestRun`, `RuleBacktestResult`, `BacktestSummary`, `OHLCVBar`, `DataQualityWarning`, `SyntheticShockDay` pydantic v2 models per `data-model.md § In-memory entities`, with Decimal canonicalisation via `quantize(Decimal("0.000001"))`
- [ ] T007 Implement `src/auto_invest/backtest/clock.py` — `Clock` Protocol, `ReplayClock`, `WallClockLeakError`, and `WallClockGuard` context manager that monkey-patches `datetime.datetime` and `time.time` in `auto_invest.*` module namespaces during the guarded scope (R-B2)
- [ ] T008 [P] Unit test `tests/unit/test_backtest_clock_guard.py` — `WallClockGuard` raises `WallClockLeakError` on any `datetime.now()` / `time.time()` call from within `auto_invest.*` inside the scope; live-worker call sites outside the scope are unaffected
- [ ] T009 [P] Unit test `tests/unit/test_backtest_data_model.py` — Decimal canonicalisation produces byte-stable strings; `BacktestRun.fill_model` and `judgment_mode` reject non-literal values (Pydantic strict literal)
- [ ] T010 Implement `src/auto_invest/backtest/kernel_pre_flight.py` — parses `git status --porcelain`, consults `auto_invest.deploy.kernel_guard.kernel_diff_check`, returns a `(touched: bool, paths: list[str])` result. Reuses the deploy module shipped by spec 006; does NOT modify any kernel-listed file.
- [ ] T011 [P] Unit test `tests/unit/test_backtest_kernel_guard.py` — given a stubbed `git status` output that includes a K-listed path, `kernel_pre_flight` returns `touched=True`; given a clean tree, returns `touched=False`; `--allow-kernel-edits` bypass call writes an `ERROR` audit row with `reason="BACKTEST_KERNEL_OVERRIDE"`

**Checkpoint**: K4 commit lands (single operator review), clock primitives + kernel guard ready. Phase 3 may begin.

---

## Phase 3: User Story 1 — Operator validates a candidate rule change (Priority: P1) 🎯 MVP

**Goal**: Operator runs `auto-invest backtest --rules ... --from ... --to ...` against ingested CSV data and gets per-rule return/drawdown/Sharpe + gate-rejection breakdown + immutable artefacts under `data/backtest/<run_id>/`.

**Independent Test**: Take an existing `config/rules.toml`, ingest a tiny one-year fixture CSV for the rule's symbol, run the CLI, verify `backtest-run.json` and `metrics.csv` exist with non-zero `order_count` for the rule. Re-run with the same inputs; verify `metrics.csv` and per-rule JSON files hash identically to the first run.

### Implementation for User Story 1

- [ ] T012 [P] [US1] Implement `src/auto_invest/backtest/data_source.py` — `HistoricalDataSource` Protocol per `contracts/historical-data-source.md`, plus `CSVDataSource` adapter that reads `data/history/<dataset_version>/<SYMBOL>.parquet` and a `manifest.json`; computes `dataset_version` from the sorted `(symbol, file_size, file_sha256)` manifest (R-B12)
- [ ] T013 [US1] Implement `src/auto_invest/backtest/ingest.py` — CSV → parquet ingest per `contracts/ohlcv-csv.md`; validation rules 1–7 produce fatal errors; quality warnings emit `DATA_QUALITY_ISSUE` audit rows; writes `manifest.json` with content-hash `dataset_version`
- [ ] T014 [P] [US1] Unit test `tests/unit/test_backtest_csv_ingest.py` — each of `HEADER_MISMATCH`, `UNPARSEABLE_ROW`, `BAD_PRICE_RANGE`, `BAD_VOLUME`, `UNKNOWN_SCHEDULE_TAG`, `DUPLICATE_DATE`, `NON_MONOTONIC_DATE` produces a fatal error; `ZERO_VOLUME_REGULAR`, `GAP_OVER_7_DAYS`, `SCHEDULE_TAG_MISMATCH` produce warnings; two identical source dirs produce identical `dataset_version`
- [ ] T015 [P] [US1] Unit test `tests/unit/test_backtest_data_source.py` — `coverage_holes` returns missing (symbol, date) pairs only for exchange-open dates per `worker/schedule.py`; `read_bars` is sorted ascending and pre-validated; `dataset_version` matches manifest hash
- [ ] T016 [US1] Implement `src/auto_invest/backtest/broker_mock.py` — `BacktestBroker(adapter_id="backtest-mock-v1")` implementing `submit_order` / `cancel_order` / `list_open_orders` with pessimistic zero-slippage fills per R-B3 (BUY fills at `min(limit, bar.open)` iff `bar.low ≤ limit AND bar.volume ≥ order.qty`; SELL symmetric); no partial fills in v1; `DAY` and `GTC` time-in-force supported
- [ ] T017 [P] [US1] Unit test `tests/unit/test_backtest_fill_model.py` — exhaustive coverage of R-B3: limit-touched-volume-ok-BUY → fill; limit-untouched-BUY → no fill; volume-shortfall-BUY → no fill; limit-touched-volume-ok-SELL → fill; tie-break behaviour for limit exactly equal to bar.open
- [ ] T018 [P] [US1] Unit test `tests/unit/test_backtest_broker_mock.py` — every `ORDER_SUBMITTED` audit row produced through `BacktestBroker` carries `adapter_id == "backtest-mock-v1"`; a router fed a non-mock adapter during backtest raises `BacktestLiveBrokerLeakError`
- [ ] T019 [US1] Implement `src/auto_invest/backtest/judgment_stub.py` — `JudgmentStub.decide(decision_class, inputs)` emits `LLM_CALL_STUBBED` audit row (input hashed via canonical-JSON SHA-256) and returns rule's documented safe-default branch; raises `BacktestJudgmentLeakError` if instantiated when `BACKTEST_MODE!=1` AND a real `AnthropicClient` is on the call stack (handshake per R-B9; spec 004 plugs in when it ships)
- [ ] T020 [P] [US1] Unit test `tests/unit/test_backtest_judgment_stub.py` — stub emits one `LLM_CALL_STUBBED` per call with stable `input_sha256`; attempting to construct an `AnthropicClient` while `BACKTEST_MODE=1` raises `BacktestJudgmentLeakError`
- [ ] T021 [P] [US1] Implement `src/auto_invest/backtest/metrics.py` — `total_return_pct`, `max_drawdown_pct`, `sharpe_ratio` (annualised √252, RFR 0) per R-B4; pure numpy/pandas, no `empyrical`/`quantstats` (R-B11); inputs and outputs are `Decimal` for byte-stability
- [ ] T022 [P] [US1] Unit test `tests/unit/test_backtest_metrics.py` — fixture: known monotonically increasing series → 0% drawdown, positive Sharpe; canned drawdown series → expected DD %; canned PnL series matches hand-computed Sharpe to 6 dp
- [ ] T023 [US1] Implement `src/auto_invest/backtest/replay.py` — drives bar-level sequential per-(session_date, rule) replay (R-B7, R-B10); for each tick, advances `ReplayClock`, queries `CSVDataSource.read_bars` for the day, constructs `Worker.tick(now=clock.now())` injection, captures order events from the in-memory router. Reuses `risk/gates.py`, `config/whitelist.py`, `config/caps.py`, `worker/schedule.py` UNMODIFIED.
- [ ] T024 [US1] Implement `src/auto_invest/backtest/report.py` — writes `backtest-run.json` per `contracts/backtest-run-json.md`, `metrics.csv` (one row per rule + `_aggregate`), `per-rule/<rule_id>/orders.json`, `fills.json`, `gate-rejections.json` per `data-model.md § On-disk per-run layout`; stable sort (ts asc, insertion order ties); chmods directory read-only at completion (POSIX)
- [ ] T025 [US1] Implement `src/auto_invest/backtest/run.py` — top-level orchestration: invoke `kernel_pre_flight` → if touched and not `--allow-kernel-edits`, emit `ERROR`/`BACKTEST_BLOCKED_KERNEL_TOUCH`, exit 78 → enter `WallClockGuard` scope → emit `BACKTEST_STARTED` → run replay → write report → emit `BACKTEST_COMPLETED` → chmod-readonly → exit 0; all error branches set the correct exit code (77/78/79/80/81) and still attempt to write `backtest-run.json` so forensics survive failures
- [ ] T026 [US1] Wire `auto-invest backtest` and `auto-invest ingest-history` Typer subcommands in `src/auto_invest/cli.py` per `contracts/backtest-cli.md`; stdout layout (first + last line = `backtest run_id: ...`); the CLI imports from `auto_invest.backtest` and ONLY adds entry-point glue (no business logic in cli.py)
- [ ] T027 [US1] Filter backtest event types out of live observability paths: in `src/auto_invest/reports/daily.py` and the `status` subcommand in `src/auto_invest/cli.py`, exclude `event_type IN ('BACKTEST_STARTED', 'BACKTEST_COMPLETED', 'LLM_CALL_STUBBED')` from PnL and position queries (one-line WHERE addition each); add a comment pointing back to FR-B17
- [ ] T028 [P] [US1] Integration test `tests/integration/test_backtest_end_to_end.py` — fixture: one-rule TOML + one-symbol one-year CSV under `tests/integration/fixtures/backtest/`; run `auto_invest.backtest.run.run_backtest(...)`; assert `backtest-run.json` exists, `metrics.csv` has one rule row + aggregate row, `per-rule/<rule>/orders.json` non-empty, `BACKTEST_STARTED`/`BACKTEST_COMPLETED` rows in `audit_log` with matching `run_id`; no `ORDER_SUBMITTED` payload has any adapter_id other than `backtest-mock-v1`

**Checkpoint**: User Story 1 is fully functional. Operator can validate a rule change end-to-end. MVP shippable here.

---

## Phase 4: User Story 2 — Synthetic-shock replay (Priority: P1, second slice)

**Goal**: `auto-invest backtest --synthetic-shock` replays the four canonical shock dates (2020-03-12, 2020-04-20, 2024-08-05, most recent quarterly OPEX) and produces deterministic per-day per-rule artefacts that spec 007's canary harness will consume.

**Independent Test**: With a deliberately loose ruleset (per-trade cap raised arbitrarily high), run `--synthetic-shock` against a fixture covering 2020-03-12; verify the per-day report contains ≥1 `ORDER_REJECTED_BY_GATE` event (SC-B04 sanity). Then run twice with identical inputs; verify byte-identical `metrics.csv` and per-rule JSON outputs.

### Implementation for User Story 2

- [ ] T029 [P] [US2] Implement `src/auto_invest/backtest/synthetic_shocks.py` — load `config/synthetic_shocks.toml`; resolve "most recent quarterly OPEX day" at engine-startup time using `exchange_calendars` via existing `worker/schedule.py` helpers (third Friday of Mar/Jun/Sep/Dec on/before today, adjusted for early-close)
- [ ] T030 [P] [US2] Populate `config/synthetic_shocks.toml` with the four canonical dates per FR-B09 (name, session_date, expected_gate_trip optional)
- [ ] T031 [P] [US2] Unit test `tests/unit/test_backtest_synthetic_shocks.py` — `resolve_synthetic_shock_dates(today=date(2026,5,13))` returns the four expected dates; "most recent quarterly OPEX" walks back from today to a third Friday in {3,6,9,12}
- [ ] T032 [US2] Extend `src/auto_invest/backtest/run.py` and `cli.py` for `--synthetic-shock` mode — per-day per-rule artefacts under `per-rule/<rule_id>/by-date/<date>/{orders,fills,gate-rejections}.json`; one combined `run_id` covering all shock days; `summary.md` lists per-day outcome
- [ ] T033 [P] [US2] Integration test `tests/integration/test_backtest_synthetic_shock_2020_03_12.py` — fixture: deliberately loose ruleset + tiny shock-day CSV; assert ≥1 `ORDER_REJECTED_BY_GATE` event surfaces for 2020-03-12 (SC-B04)
- [ ] T034 [P] [US2] Integration test `tests/integration/test_backtest_determinism.py` — run the same fixture-driven backtest twice; assert `metrics.csv` and every `per-rule/**/*.json` file are byte-identical between runs; `backtest-run.json` differs only in `run_id`, `start_ts`, `end_ts` (FR-B15 / SC-B02)

**Checkpoint**: User Story 2 is fully functional. Spec 007 prerequisite unlocked.

---

## Phase 5: User Story 3 — Operator reads a one-page summary (Priority: P2)

**Goal**: Every backtest emits `summary.md` (and identical content to stdout) that the operator scans in under 2 minutes to make a keep/discard decision.

**Independent Test**: Run a backtest with 5 rules, 2 of which are intentionally bad (one violates per-trade cap, one references a delisted symbol). Verify `summary.md` surfaces both failures with a one-line reason each, and the headline metrics are within 2 minutes' visual scan.

### Implementation for User Story 3

- [ ] T035 [US3] Extend `src/auto_invest/backtest/report.py` (extends T024) to render `summary.md` with: header (date range, ruleset hash, dataset version, fill model, slippage assumption), aggregate metrics block, per-rule headline metrics table, data-quality warnings block, gate-rejection breakdown block; identical content goes to stdout
- [ ] T036 [P] [US3] Unit test `tests/unit/test_backtest_summary_render.py` — given a canned `BacktestSummary`, the rendered `summary.md` contains headline metrics for each rule, surfaces every `DataQualityWarning`, and includes the slippage-assumption disclaimer line

**Checkpoint**: All three user stories functional.

---

## Phase 6: Polish & Cross-Cutting

- [ ] T037 Update `README.md` with one paragraph + link to `specs/008-backtest-engine/quickstart.md`
- [ ] T038 [P] Run `uv run ruff check src tests`; clean any new findings introduced by this spec
- [ ] T039 [P] Run `uv run pytest` and confirm new test count (expected: 319 prior + new backtest tests; `1 skipped` for the live KIS gate remains unchanged)
- [ ] T040 [P] Run `uv run python -c "from auto_invest.backtest import run_backtest; print('importable')"` to confirm public surface compiles
- [ ] T041 Execute the `quickstart.md` walkthrough end-to-end on a tiny operator-style fixture (single rule, single symbol, 30 trading days); record the `run_id`; verify the artefact tree matches `data-model.md § On-disk per-run layout`; add the run_id to a HANDOFF section in `HANDOFF-002-003.md`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)** → no dependencies; can start immediately.
- **Foundational (Phase 2)** → depends on Phase 1. **K4 commit (T004+T005) is the single Kernel touch** and MUST land before any of T006..T011. Operator reviews this commit per constitution IX.B-1.
- **User Story 1 (Phase 3)** → depends on Phase 2.
- **User Story 2 (Phase 4)** → depends on Phase 3 (consumes the same engine; `--synthetic-shock` is an additive CLI mode).
- **User Story 3 (Phase 5)** → depends on Phase 3 (extends `report.py`).
- **Polish (Phase 6)** → depends on all user stories.

### Critical commit-boundary rule

T004 + T005 form ONE commit. Subject line MUST start with `feat(008): K4 —`. Every other task ships as its own commit (or grouped logically with adjacent same-file tasks), with subject prefix `feat(008):` or `test(008):` per existing repo style. No other commit may touch any `.specify/memory/kernel.toml` path.

### Within each user story

- Models (data shapes) before services (engine logic) before orchestration (run.py) before CLI wiring.
- Tests for safety contracts (`WallClockGuard`, broker-mock isolation, judgment-stub leak, kernel-pre-flight, determinism) are NOT optional — they enforce the spec's non-negotiable invariants.

### Parallel opportunities

- T003 in Phase 1.
- T006, T008, T009, T011 in Phase 2 (different files).
- Within US1: T014, T015, T017, T018, T020, T022 (unit tests of disjoint modules).
- T028 in US1 (one integration test file).
- Within US2: T029, T030, T031, T033, T034 (all disjoint files).
- T036 in US3.
- T038, T039, T040 in Phase 6 (read-only).

### Sequential bottlenecks (no [P])

- T004+T005 must commit together; T006..T011 cannot start until that commit lands.
- T013 (ingest) blocks T015 because the test fixture under `tests/integration/fixtures/backtest/` depends on the ingest format.
- T016 (broker_mock) blocks T023 (replay needs the mock).
- T023 (replay) blocks T024 (report consumes replay output).
- T024 (report) blocks T025 (run.py orchestrates report writing).
- T025 (run.py) blocks T026 (CLI imports run.py).
- T026 (CLI) blocks T028 (E2E test invokes CLI).
- T032 extends T025 + T026, so must come after both.
- T035 extends T024.

---

## Parallel Example: Phase 2 Foundational

```bash
# After T004+T005 (the K4 commit) lands, the following can run in parallel:
Task: "Implement src/auto_invest/backtest/data_model.py (T006)"
Task: "Unit test tests/unit/test_backtest_clock_guard.py (T008)"
Task: "Unit test tests/unit/test_backtest_data_model.py (T009)"
Task: "Unit test tests/unit/test_backtest_kernel_guard.py (T011)"
```

## Parallel Example: User Story 1 unit tests

```bash
Task: "Unit test tests/unit/test_backtest_csv_ingest.py (T014)"
Task: "Unit test tests/unit/test_backtest_data_source.py (T015)"
Task: "Unit test tests/unit/test_backtest_fill_model.py (T017)"
Task: "Unit test tests/unit/test_backtest_broker_mock.py (T018)"
Task: "Unit test tests/unit/test_backtest_judgment_stub.py (T020)"
Task: "Unit test tests/unit/test_backtest_metrics.py (T022)"
```

---

## Implementation Strategy

### MVP scope (recommended first cut)

1. Phase 1 (Setup) — half-day.
2. Phase 2 (Foundational, K4 commit included) — operator reviews + approves K4 commit before Phase 3.
3. Phase 3 (User Story 1) — operator can validate any rule change against a CSV-ingested historical window.
4. STOP and validate against a real operator ruleset on a one-year window. If artefacts and metrics look right, ship the MVP.

### Spec-007 unlock cut

5. Phase 4 (User Story 2) — `--synthetic-shock` mode produces the deterministic per-day artefacts spec 007's canary harness consumes. This unlocks spec 007's implementation (which itself unlocks spec 005).

### Full v1

6. Phase 5 (User Story 3) — `summary.md` polish for daily operator use.
7. Phase 6 (Polish) — lint + tests + README + manual quickstart walkthrough.

### Why not parallelise everything

Spec 007's hardened canary depends on FR-B15 (byte-identical determinism). Determinism bugs are easy to introduce, hard to detect, and corrosive to spec 007's safety guarantee. Phase 3 → Phase 4 must be sequential so the determinism integration test (T034) runs against a fully-wired engine BEFORE we declare spec 007 unblocked.

---

## Safety-contract test coverage map

| Safety FR | Test task | What it asserts |
|-----------|-----------|----------------|
| FR-B02 (wall-clock leak) | T008 | `WallClockGuard` raises on `datetime.now()` / `time.time()` inside scope |
| FR-B06 (no live broker) | T018, T028 | every `ORDER_SUBMITTED` carries `adapter_id == "backtest-mock-v1"`; non-mock adapter raises |
| FR-B07 (pessimistic fill) | T017 | open-anchored fill iff limit ∈ [low, high] AND volume ≥ qty |
| FR-B08 (no real LLM) | T020 | `LLM_CALL_STUBBED` emitted per call; `BACKTEST_MODE=1` + AnthropicClient raises `BacktestJudgmentLeakError` |
| FR-B10 (refuse incomplete coverage) | T015 | `coverage_holes` returns missing pairs; CLI exits 66 on non-empty |
| FR-B12 (kernel-guard pre-flight) | T011 | `kernel_pre_flight` returns `touched=True` for K-listed dirty path; bypass writes audit override |
| FR-B13 (data quality at ingest) | T014 | all seven fatal rules and three warnings fire as specified |
| FR-B15 (byte-identical determinism) | T034 | two runs with identical inputs produce byte-identical `metrics.csv` and `per-rule/**/*.json` |
| FR-B17 (live observability filter) | T028 | `auto-invest report` query excludes backtest event types |
| SC-B04 (synthetic-shock gate trip) | T033 | loose ruleset on 2020-03-12 produces ≥1 `ORDER_REJECTED_BY_GATE` |

If any of these tests goes red during `/speckit-implement`, the corresponding safety guarantee is broken and must be fixed BEFORE marking the related task complete.

---

## Notes

- 41 tasks total. Per-story counts: Setup 3 + Foundational 8 + US1 17 + US2 6 + US3 2 + Polish 5.
- [P] flag applied to 21 tasks where adjacent tasks operate on disjoint files.
- Single K4 commit (T004 + T005) is the operator-reviewed approval point per constitution IX.B-1.
- Every task name maps to an exact file path under `src/auto_invest/backtest/`, `tests/unit/`, `tests/integration/`, or one of the four edited files outside the engine package (`audit.py`, `cli.py`, `reports/daily.py`, `pyproject.toml`).
- Independent test for each user story is documented at the top of each phase.
- Verify tests fail before implementing where TDD applies (safety-contract tests in particular).
- Commit after each task or logically-grouped same-file pair. Stop at any checkpoint to validate.
