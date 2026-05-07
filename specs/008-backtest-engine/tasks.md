---

description: "Tasks for spec 008 — backtest engine implementation"
---

# Tasks: Backtest Engine

**Input**: Design documents from `/specs/008-backtest-engine/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/ (all present), quickstart.md

**Tests**: this feature requires tests. Spec 008 SC-B02 (gate-coverage diff vs live), SC-B03 (≥100 deterministic reruns), SC-B04 (injected-fault rejection coverage), and SC-B07 (≥10 000 property-fuzz iterations) all bottom out at automated tests; the implementation cannot ship without them. Tests are written first inside each user-story phase and MUST fail before the matching implementation lands.

**Organization**: tasks are grouped by user story so each story can be implemented and tested independently. Spec 008 has two P1 stories (US1 = synthetic-shock for spec 007; US2 = operator ad-hoc backtest) and two P2 stories (US3 = audit-log integration; US4 = on-disk artifact). The implementation strategy below explains the realistic ordering — US3 and US4 cross-cut both P1 stories and ship alongside them rather than as separate increments.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- File paths are absolute under repo root: `src/auto_invest/...`, `tests/backtest/...`

## Path Conventions

Single Python package (spec 001 layout extended). Code under `src/auto_invest/backtest/`; tests under `tests/backtest/`; on-disk artifacts under `data/backtests/`; named-dataset manifests under `data/ohlcv/datasets/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: scaffold the new subpackage and test tree; pin new dependencies.

- [ ] T001 Create the `auto_invest.backtest` subpackage skeleton: `src/auto_invest/backtest/__init__.py`, `src/auto_invest/backtest/ohlcv/__init__.py` (empty stubs; public surface comes later)
- [ ] T002 [P] Create `tests/backtest/__init__.py` and `tests/backtest/fixtures/` directory; empty `tests/backtest/fixtures/.gitkeep`
- [ ] T003 [P] Add `yfinance ~= 0.2` and `hypothesis ~= 6` to `pyproject.toml` `[project.dependencies]` (or the equivalent `dependencies` list) and run `uv lock` to refresh `uv.lock`
- [ ] T004 [P] Verify ruff/pytest are unchanged in `pyproject.toml`; add a `[tool.pytest.ini_options]` marker definition `nightly: marks slow property-fuzz runs (deselect with -m "not nightly")` if not already present

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the one-time K-meta human-merge change set. Until this phase is complete, no user story can land — the audit-event types, the migration, the kernel-manifest update, and the worker DI seam all live here. **Everything in Phase 2 must be reviewed together as the documented one-time Kernel touch (constitution IX.C).**

⚠️ **CRITICAL**: this phase intentionally touches K4 (`audit.py`, new migration) and K-meta (`kernel.toml`). The deploy guard's kernel-touch check (spec 006 FR-D13) WILL flag this change set; that is expected and is the whole point of IX.C.

- [ ] T005 Write SQLite migration `src/auto_invest/persistence/migrations/0003_backtest_events.sql` — adds the partial index `idx_audit_log_backtest_events ON audit_log (event_type, ts_utc) WHERE event_type IN ('BACKTEST_STARTED','BACKTEST_COMPLETED','BACKTEST_FAILED')`. NO column additions. SQL idempotent (`CREATE INDEX IF NOT EXISTS`).
- [ ] T006 Update `.specify/memory/kernel.toml` in two coordinated edits (still one K-meta touch — single review event): (a) add `"src/auto_invest/persistence/migrations/0003_backtest_events.sql"` to `[K4_append_only_audit].files`; (b) **add a new group `[K7_named_datasets]`** with description "Curated synthetic-shock named datasets used by spec 007's hardened canary (constitution IX.B-2). Without K7, autonomous tuner could silently mutate the safety surface that spec 007's FR-C03 synthetic-shock replay rests on. Spec 005 separately classifies these as L4; K7 is the runtime-enforcement counterpart." and `files = ["data/ohlcv/datasets/synthetic_shock_v1.json"]`. The K7 group makes FR-B20 enforceable by spec 006's deploy guard immediately, not contingent on spec 005's tuner shipping.
- [ ] T007 Modify `src/auto_invest/persistence/audit.py` (K4): extend `EventType` Literal with `"BACKTEST_STARTED"`, `"BACKTEST_COMPLETED"`, `"BACKTEST_FAILED"`; add three pydantic payload classes `BacktestStartedPayload`, `BacktestCompletedPayload`, `BacktestFailedPayload` per `contracts/audit-events.md` schemas. NO change to write semantics or to existing payload classes.
- [ ] T008 [P] Create exception types `src/auto_invest/backtest/errors.py`: `OhlcvDataQualityError`, `OhlcvVendorError`, `OhlcvWindowError`, `BacktestKernelTouchError`, `BacktestDirtyTreeError`, `BacktestReproducibilityError` — all subclasses of a base `BacktestError(Exception)`
- [ ] T009 [P] Create canonical OHLCV row at `src/auto_invest/backtest/ohlcv/canonical.py`: frozen pydantic `OhlcvBar` per data-model.md §1; `canonical_dump(bars: Sequence[OhlcvBar]) -> str` for content-hash input; `content_hash(bars: Sequence[OhlcvBar]) -> str` returning sha256 hex
- [ ] T010 [P] Create `src/auto_invest/backtest/clock.py` with `SyntheticClock` — holds a single `datetime` and exposes `now()` returning it; `advance_to(dt)` mutator. Frozen-time across a single `Worker.tick`.
- [ ] T011 [P] Create `src/auto_invest/backtest/verdict.py` with `VerdictThresholds` (frozen pydantic; v1 baseline as class-level defaults per FR-B21) and `Verdict` (promote_eligible, reasons list)
- [ ] T012 [P] Create `src/auto_invest/backtest/config.py` with `BacktestWindow` discriminated union (`Window` / `NamedDataset`), `BacktestConfig` per data-model.md §1, including all defaults from FR-B07/B10/B21/R-7/R-8
- [ ] T013 Modify `src/auto_invest/worker/loop.py` (NON-Kernel): add two optional kwargs to `Worker.__init__` — `quote_provider: QuoteProvider | None = None` and `clock: ClockCallable | None = None`. In `_evaluate_and_route`, branch on `self.quote_provider`: if `None`, call live `get_quote` as today; otherwise `await self.quote_provider(rule.symbol, now)`. Default `clock` is `lambda: datetime.now(UTC)`. Type-hints in a new `src/auto_invest/worker/types.py` if needed. **Live behaviour MUST be byte-identical when both kwargs are `None`.**
- [ ] T014 [P] Create `src/auto_invest/backtest/hashing.py`: `code_sha(allow_dirty: bool) -> str`, `rules_hash(toml_path: Path) -> str` (canonicalises TOML before hashing), `caps_hash() -> str` (over `config/caps.py` constants), `whitelist_hash() -> str` (over `config/whitelist.py` symbols)
- [ ] T015 Foundational integration test `tests/backtest/test_foundational.py`: round-trip a `BacktestStartedPayload` through `audit.append` and read it back; assert no live-pipeline regression by running an existing `Worker.tick` test (from `tests/test_worker_loop.py` or equivalent) with both new kwargs absent.

**Checkpoint — Phase 2**: foundation ready; the one-time human-merge change set boundary ends here. From Phase 3 onwards, every change set is non-Kernel and (post spec 007) autonomous-merge-eligible.

---

## Phase 3: User Story 1 (P1) 🎯 — Spec 007 Synthetic-Shock Replay

**Goal**: the spec 007 canary harness can drive the candidate code through `auto_invest.backtest` against `synthetic_shock_v1` and observe per-day outcomes (orders proposed, gate rejections, simulated fills, audit-integrity anomalies). This is the gate constitution IX.B-2 conditions autonomous merge on.

**Independent Test**: feed a known-good rule (comment-only edit of a previously-promoted rule) through synthetic-shock mode → expect zero risk-gate violations and a stable PnL series. Feed a deliberately-broken rule (per-trade cap raised 100×) → expect the engine to surface the violation without ever submitting a fill.

### Tests for User Story 1 (write FIRST, expect FAIL until implementation lands) ⚠️

- [ ] T016 [P] [US1] Test `tests/backtest/test_named_dataset.py`: load `data/ohlcv/datasets/synthetic_shock_v1.json` and assert membership = {2020-03-12, 2020-04-20, 2024-08-05, 2026-03-20}; assert schema_version=1, constitutional_tier="L4"; mutate a date and assert the loader rejects with `OhlcvDataQualityError` when the manifest's content hash drifts mid-run
- [ ] T017 [P] [US1] Test `tests/backtest/test_kernel_safety.py`: invoke the engine's pre-flight `kernel_touch_check` against a synthetic diff that includes `kernel.toml` and assert it raises `BacktestKernelTouchError`; against an empty diff assert it returns cleanly. **Also**: parametrise over each Kernel group (K1..K7 + K_meta) — synthesize a diff that touches one file per group and assert the check rejects each; specifically include `data/ohlcv/datasets/synthetic_shock_v1.json` (K7) so FR-B20's runtime enforcement is regression-tested.
- [ ] T018 [US1] Test `tests/backtest/test_synthetic_shock_mode.py`: end-to-end — given a known-good rule and a fixture OHLCV file for the four shock dates plus warmup, drive the engine in named-dataset mode and assert per-day fills/rejections match a frozen golden under `tests/backtest/fixtures/synthetic_shock_v1/golden.json`. Then mutate the rule's per-trade cap to 100× and assert zero fills land (gate rejection rate = 100%)

### Implementation for User Story 1

- [ ] T019 [P] [US1] Create `src/auto_invest/backtest/named_dataset.py`: `load(name: str) -> NamedDataset` reading `data/ohlcv/datasets/<name>.json`, validating schema per `contracts/named-dataset.md`, returning a frozen pydantic model with `frozen_at_utc`, `dates`, `rationale`, `constitutional_tier`. Computes content hash for FR-B19.
- [ ] T020 [P] [US1] Create `data/ohlcv/datasets/synthetic_shock_v1.json` per `contracts/named-dataset.md` v1 frozen content (exact 4-date membership + rationale + L4 mutation_policy); commit alongside spec 008's first landing
- [ ] T021 [US1] Implement engine pre-flight check at `src/auto_invest/backtest/engine.py::_kernel_touch_check`: read `.specify/memory/kernel.toml`, compute the working-tree diff (vs `git rev-parse HEAD`) using a subprocess `git diff --name-only`, raise `BacktestKernelTouchError` if any path under any `[K*].files` is in the diff. Defense-in-depth (CLI exit `7`).
- [ ] T022 [US1] Implement synthetic-shock branch in `engine.py::run_backtest`: when `config.window` is a `NamedDataset`, for each date in the dataset, compute `(date - warmup_bars * 1.5_calendar)`, request bars from the chosen adapter, prime indicator state silently, then drive `Worker.tick(now=close_of_shock_day)` exactly once per shock date. Emit per-date sub-reports into the headline `report.json`.
- [ ] T023 [US1] Wire `BACKTEST_STARTED` payload's `named_dataset` field correctly when running in synthetic-shock mode (mutually exclusive with `window_start`/`window_end` per FR-B17 invariant)

**Checkpoint — US1**: synthetic-shock mode is callable from python and produces a deterministic per-date report. Spec 007's harness can integrate against this entry point.

---

## Phase 4: User Story 2 (P1) — Operator Ad-Hoc Backtest

**Goal**: the operator runs `auto-invest backtest --rules X.toml --window 2024-01-02:2024-12-31 --symbols AAPL` and reads a returns/drawdown/Sharpe report.

**Independent Test**: load a synthetic OHLCV fixture (sine-wave price series over 252 trading days), run a single SMA-cross rule, verify the engine reports the closed-form expected number of fills and the closed-form PnL within numerical tolerance (`<= 1e-6`).

### Tests for User Story 2 ⚠️

- [ ] T024 [P] [US2] Test `tests/backtest/test_ohlcv_adapter_protocol.py`: assert that both `yfinance_adapter` and `kis_historical_adapter` implement the `OhlcvAdapter` Protocol (structural typing check via `runtime_checkable`); assert canonical `OhlcvBar` shape returned for a stub fixture
- [ ] T025 [P] [US2] Test `tests/backtest/test_yfinance_adapter.py` using `respx` to mock Yahoo's HTTP surface: assert tenacity retry on 429, circuit-breaker open after N consecutive failures, adjusted-flag detection, NaN/zero-volume rejection
- [ ] T026 [P] [US2] Test `tests/backtest/test_kis_historical_adapter.py` using `respx`: assert reuse of existing `ResilientClient`; assert that no order-submission endpoint is hit in any code path; assert auth-token-redaction filter active
- [ ] T027 [P] [US2] Test `tests/backtest/test_fills_model.py`: enumerate the FR-B07 hybrid branches — limit BUY where bar straddles + bar opens below limit (fill at open); limit BUY where bar straddles + bar opens above limit (fill at limit); limit BUY where bar doesn't straddle (no fill); symmetric SELL cases; market BUY/SELL with default 5 bps slippage; market with operator-overridden slippage
- [ ] T028 [P] [US2] Test `tests/backtest/test_report_math.py`: deterministic sine-wave OHLCV fixture (252 days, period 30, amplitude 5%); run a 20/50 SMA-cross rule; assert fill count and total PnL match closed-form expectations (within float tolerance for the Sharpe denominator only)
- [ ] T029 [P] [US2] Test `tests/backtest/test_verdict.py`: matrix of (return, drawdown, sharpe) triples × v1 thresholds → assert promote_eligible boolean and the three reason strings are byte-identical and in canonical order; assert sharpe=None ⇒ promote_eligible=False with bankruptcy reason
- [ ] T030 [P] [US2] Test `tests/backtest/test_engine_determinism.py`: run the same `BacktestConfig` 100 times in-process; assert `report.json`, `daily.csv`, `fills.csv` are byte-identical (excluding `run_id`/`*_ts_utc`/`dirty`); same for `manifest.json` minus those fields
- [ ] T031 [US2] Test `tests/backtest/test_engine_pipeline_reuse.py`: instrument `coverage.py` over `auto_invest.risk.gates` while running once live (with mocked broker) and once in backtest; assert the line/branch coverage sets are equal — SC-B02
- [ ] T032 [P] [US2] Test `tests/backtest/test_dirty_tree_refusal.py`: when the working tree is dirty and `allow_dirty=False`, the engine raises `BacktestDirtyTreeError` before any audit row is written; with `allow_dirty=True`, `code_sha` ends with `+dirty` and `manifest.dirty=True`

### Implementation for User Story 2

- [ ] T033 [P] [US2] Create `OhlcvAdapter` Protocol at `src/auto_invest/backtest/ohlcv/adapter.py` (per `contracts/ohlcv-adapter.md`); declare runtime-checkable
- [ ] T034 [P] [US2] Create `src/auto_invest/backtest/ohlcv/cache.py`: read/write per-symbol bars under `data/ohlcv/<vendor_id>/<symbol>.parquet` (or `.csv` if pyarrow absent); content-hash sidecar `.json` carrying `vendor_id`, `fetched_at_utc`, `adjusted_flag`. Cache-miss detection used by ingestion.
- [ ] T035 [US2] Create `src/auto_invest/backtest/ohlcv/yfinance_adapter.py`: implements `fetch_bars`; tenacity retry + token-bucket rate limiter + circuit breaker (mirrors `broker/client.py` pattern); normalises pandas DataFrame → `OhlcvBar` rows with 4-decimal precision; sets `adjusted=True` always (uses `auto_adjust=True`)
- [ ] T036 [US2] Create `src/auto_invest/backtest/ohlcv/kis_historical_adapter.py`: reuses existing `ResilientClient`; uses KIS overseas-equity historical endpoint; raises `OhlcvDataQualityError` on any unadjusted-bar marker. Verifies no order-endpoint URL ever appears in the call surface (asserted in T026).
- [ ] T037 [US2] Wire adapter registry in `src/auto_invest/backtest/ohlcv/__init__.py`: `ADAPTERS: dict[str, type[OhlcvAdapter]]` mapping vendor_id strings to classes
- [ ] T038 [P] [US2] Create `src/auto_invest/backtest/fills.py`: `simulate_fill(rule, bar, next_bar, slippage_bps_market) -> SimulatedFill` per FR-B07 + R-4 semantics. Pure function; stateless.
- [ ] T039 [P] [US2] Create `src/auto_invest/backtest/portfolio.py`: cash + per-symbol position ledger; `apply_fill(fill) -> None` mutates in place; emits `DailyState` snapshot at end-of-bar
- [ ] T040 [US2] Create `src/auto_invest/backtest/broker.py::BacktestBroker`: implements the same call surface the live order-router calls on `ResilientClient` for order submission, but persists `SimulatedFill` rows to the in-memory ledger. NO network. Constructor takes the `Portfolio` object from T039.
- [ ] T041 [US2] Implement main replay loop in `src/auto_invest/backtest/engine.py::run_backtest` (depends on T013, T019, T021, T033, T035, T036, T038, T039, T040): validate inputs, kernel-touch check, hash inputs, ingest OHLCV (cache-first), emit `BACKTEST_STARTED`, prime indicators, drive `Worker.tick` over each bar's close timestamp, accumulate `DailyState`, build the report, emit `BACKTEST_COMPLETED`, write artifact dir
- [ ] T042 [P] [US2] Create `src/auto_invest/backtest/report.py`: compute total return %, max drawdown %, annualised Sharpe (per R-7), per-rule PnL/fill counts; bankruptcy detection sets `sharpe=None` and `bankruptcy_at`
- [ ] T043 [US2] Wire `verdict.compute(report, thresholds) -> Verdict` in `verdict.py` (T011 stub gets its real implementation); deterministic reason-string ordering per `contracts/run-artifact.md`
- [ ] T044 [US2] Create `src/auto_invest/backtest/manifest.py`: `Manifest.from_run(run, bars_consumed) -> Manifest`; `Manifest.write(path) -> None` produces the on-disk `manifest.json` per `contracts/run-artifact.md`. Sorted-keys, indent=2, trailing-newline JSON.
- [ ] T045 [US2] Create `src/auto_invest/backtest/cli.py` and integrate into `src/auto_invest/cli.py` (top-level `auto-invest` click group): `auto-invest backtest` subcommand per `contracts/cli.md`; flag parsing produces a `BacktestConfig`; calls `run_backtest`; prints artifact path on stdout, progress on stderr; maps exceptions to exit codes 0/2/3/4/5/6/7

**Checkpoint — US2**: operators can run `auto-invest backtest --rules X.toml --window ... --symbols ...` and read a deterministic report. Spec 008 SC-B01, B02, B03, B04, B05 are all covered by tests T024..T032.

---

## Phase 5: User Story 3 (P2) — Audit-Log Integration

**Goal**: every backtest run is recorded in the existing `audit_log` table with `BACKTEST_STARTED` / `BACKTEST_COMPLETED` / `BACKTEST_FAILED` rows; the operator can answer "show me every backtest in the last 30 days" with a single SQL query (SC-B06). The engine NEVER exits without a matching `COMPLETED` or `FAILED` row for any `STARTED` row (FR-B16).

Note: payload classes already exist (T007). This phase wires emission and proves the FR-B16 invariant.

**Independent Test**: run two distinct backtests, then run the SC-B06 SQL — verify exactly two `BACKTEST_STARTED` rows and two corresponding `BACKTEST_COMPLETED` rows, each with monotonic `seq_id`s, payloads carrying the expected `run_id`s.

### Tests for User Story 3 ⚠️

- [ ] T046 [P] [US3] Test `tests/backtest/test_audit_lifecycle.py`: parametrised over (success path, ingest_ohlcv failure, replay failure, report failure) — assert that for every path that crossed `BACKTEST_STARTED`, exactly one of `BACKTEST_COMPLETED` or `BACKTEST_FAILED` exists; for paths that fail before `STARTED` (validate_inputs, dirty-tree, kernel-touch), assert ZERO `BACKTEST_*` rows exist
- [ ] T047 [P] [US3] Test `tests/backtest/test_audit_payload_schema.py`: validate every emitted `BACKTEST_*` payload against `contracts/audit-events.md` schemas (hash regex, exclusive null fields, no-secrets in reason); assert truncation at 256 chars
- [ ] T048 [P] [US3] Test `tests/backtest/test_audit_no_mutation.py`: monkeypatch `sqlite3.Connection.execute` to raise on any SQL containing `UPDATE` or `DELETE`; run the full engine; assert no monkeypatch trip — the engine never mutates `audit_log`
- [ ] T049 [P] [US3] Test `tests/backtest/test_sql_query_sc_b06.py`: insert N=5 fake `BACKTEST_*` rows via the test SQLite fixture; run the SC-B06 query verbatim from `quickstart.md`; assert it returns N rows in correct descending order; assert the partial-index on `audit_log` is hit (via `EXPLAIN QUERY PLAN`)

### Implementation for User Story 3

- [ ] T050 [US3] Implement `src/auto_invest/backtest/engine.py::_emit_started` / `_emit_completed` / `_emit_failed`; single call site each; wraps `audit.append` only
- [ ] T051 [US3] Implement try/except in `engine.py::run_backtest` per `contracts/audit-events.md`: catches `Exception` (NOT `BaseException`); maps exception class to phase via dispatch table `{OhlcvDataQualityError|OhlcvVendorError|OhlcvWindowError: "ingest_ohlcv", BacktestReproducibilityError: "report"}` else default `"replay"`; constructs `reason` from `str(exc)` truncated to 256 chars and redacted; calls `_emit_failed`; re-raises
- [ ] T052 [US3] Verify the existing `auto_invest.persistence.db` migration runner picks up `0003_backtest_events.sql` automatically on next startup; if not, add explicit registration (one-liner)

**Checkpoint — US3**: every backtest's audit lineage is queryable via plain SQL; FR-B16 invariant verified by tests.

---

## Phase 6: User Story 4 (P2) — On-Disk Run Artifact

**Goal**: every backtest produces `data/backtests/<run_id>/{manifest.json, report.json, daily.csv, fills.csv, audit-events.json}` — atomic, byte-identical for identical inputs (FR-B12).

**Independent Test**: run a backtest, locate `data/backtests/<run_id>/`, parse each file against the published schema, verify the five files exist with the expected schemas. Run twice and diff — only `start_ts_utc`/`end_ts_utc`/`dirty` (and `seq_id`/`ts_utc` per audit-events row) differ.

### Tests for User Story 4 ⚠️

- [ ] T053 [P] [US4] Test `tests/backtest/test_artifact_byte_identity.py`: run the engine twice with seed=0 and identical inputs; diff `report.json` (byte-identical), `daily.csv` (byte-identical), `fills.csv` (byte-identical), `manifest.json` excluding `start_ts_utc`/`end_ts_utc`/`dirty` (byte-identical), `audit-events.json` per-row excluding `seq_id`/`ts_utc` (byte-identical) — FR-B12, SC-B03
- [ ] T054 [P] [US4] Test `tests/backtest/test_artifact_atomic.py`: monkeypatch the artifact-writer to crash mid-write (after first file, before rename); assert NO `data/backtests/<run_id>/` directory exists (only `.tmp-<run_id>/` left behind); verify the next successful run cleans up the stale `.tmp-*`
- [ ] T055 [P] [US4] Test `tests/backtest/test_artifact_csv_quoting.py`: verify `daily.csv`'s `per_symbol_exposure_pct_json` column round-trips through `csv.DictReader`; embedded `"` doubled per RFC 4180; non-ASCII symbols (defensive: future-proof) stored as UTF-8

### Implementation for User Story 4

- [ ] T056 [US4] Create `src/auto_invest/backtest/artifact.py`: `ArtifactWriter(run_id, output_root)` with `__enter__` creating `<output_root>/.tmp-<run_id>/`; `write_manifest`/`write_report`/`write_daily_csv`/`write_fills_csv`/`write_audit_events`; `__exit__` on success calls `os.rename` to the final path; on failure leaves the `.tmp-*` for cleanup
- [ ] T057 [P] [US4] CSV writer helper with RFC 4180 quoting in `artifact.py` — handles embedded `"` doubling and `\n` line endings
- [ ] T058 [P] [US4] Create `audit-events.json` builder: SQL `SELECT seq_id, ts_utc, event_type, payload FROM audit_log WHERE event_type LIKE 'BACKTEST_%' AND json_extract(payload, '$.run_id') = ?` ordered by `seq_id`; serialise to the file
- [ ] T059 [US4] Stale-tmp cleanup at the start of every run: `glob('.tmp-*')` under `output_root`, `rmtree` any directory whose mtime is more than 1 hour old (operator-tunable in v2)

**Checkpoint — US4**: artifact directory is the on-disk source of truth; spec 007's canary harness can read it directly; reproducibility verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: harden the engine for the spec 007 consumer; documentation; lint/test cleanliness.

- [ ] T060 [P] Property fuzz test `tests/backtest/test_property_fuzz.py` using `hypothesis`: generates `(rules_toml, ohlcv_dataset, seed)` triples; runs the engine twice per triple; asserts the four byte-comparison files are identical. Default 100 examples; mark with `@pytest.mark.nightly` and run with `--hypothesis-seed=0` and `max_examples=10000` in nightly CI (R-10, SC-B07)
- [ ] T061 [P] Expose `auto_invest.backtest.run_backtest` and `BacktestConfig` in `src/auto_invest/backtest/__init__.py` for direct import by the spec 007 canary harness (R-9, dual entry point)
- [ ] T062 [P] Quickstart validation: run the five steps in `quickstart.md` end-to-end against the operator's local venv; record any deltas as docs fixes (this is a manual verification task; the operator runs it before sign-off)
- [ ] T063 [P] README update at repo root: add a one-paragraph "Backtest engine (spec 008)" section with a link to `specs/008-backtest-engine/quickstart.md`
- [ ] T064 [P] HANDOFF update: amend `HANDOFF.md` and/or `HANDOFF-002-003.md` to reflect that spec 008 has shipped and the next milestone is spec 007 (hardened canary) implementation
- [ ] T065 Run `uv run ruff check src tests` and `uv run ruff format --check src tests`; fix any lint or format issues
- [ ] T066 Run the full `uv run pytest` suite (NOT in `nightly` mode); assert all tests pass; record test count delta in the commit message
- [ ] T067 Confirm `tests/backtest/test_kernel_safety.py` (T017) passes against the working tree at the moment of the post-Phase-2 first non-Kernel commit (i.e. after T013 lands, every subsequent commit's diff must NOT intersect `kernel.toml` paths). Run `git diff main..HEAD --name-only | grep -F -f <(awk -F'"' '/files = /,/]/{print $2}' .specify/memory/kernel.toml) ; echo "(should be empty)"` for spot-checking
- [ ] T068 [P] [US1] Add wall-clock assertion to `tests/backtest/test_synthetic_shock_mode.py` (T018) — wrap the engine call in `time.perf_counter()` and assert wall-clock < 30 s (SC-B05). The fixture OHLCV must be local cache only so vendor latency is excluded from the budget.
- [ ] T069 [P] Add `tests/backtest/test_no_network_during_replay.py` (FR-B09 cross-cutting): block all outbound HTTP via a global `respx` fixture that raises on any request; pre-populate the local OHLCV cache with the required bars; run a full backtest end-to-end; assert it completes successfully (proves engine never reaches for the network mid-replay) AND a parametrised second run with one bar missing from cache asserts the engine raises `OhlcvWindowError` BEFORE `BACKTEST_STARTED` is emitted (so the no-network invariant is checked at ingest, not silently masked).
- [ ] T070 [P] Expand `tests/backtest/test_engine_pipeline_reuse.py` (T031) into an SC-B04 fault matrix: parametrise over at least six injected-fault classes — (1) per-trade cap > global cap in rule TOML, (2) symbol off the live whitelist, (3) NaN bar in OHLCV cache, (4) zero-volume bar on a non-holiday trading day, (5) rule timeframe finer than the dataset resolution (e.g. `timeframe="1m"` against daily bars), (6) duplicate rule_id; assert each fault produces the same operator-readable rejection message in backtest as in live (where applicable) and that injected faults are rejected in 100% of test cases (SC-B04).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; can start immediately
- **Foundational (Phase 2)**: depends on Phase 1; **BLOCKS all user stories**; the entire phase is the documented one-time K-meta human-merge change set
- **US1 (Phase 3)**: depends on Phase 2 complete; can start once T013, T019 land
- **US2 (Phase 4)**: depends on Phase 2 complete; bulk can run in parallel with US1, but T041 (engine main loop) is the integration point that both US1 and US2 share — so in practice T041 lands after both US1's T021/T022 and US2's adapter+fills+portfolio chain are ready
- **US3 (Phase 5)**: depends on T007 (Phase 2) plus T041 (US2 main loop); audit emission is wired by T050/T051 inside the engine
- **US4 (Phase 6)**: depends on T041 (US2 main loop); artifact writing is the engine's last step
- **Polish (Phase 7)**: depends on US1, US2, US3, US4 all complete; T067 is the final sign-off check

### Critical-Path Tasks (single chain through the implementation)

```text
T001 → T005 → T006 → T007 → T013 → T015 → T021 → T041 → T056 → T067
(setup)  (migration)  (audit.py)  (worker DI)  (kernel guard)  (engine loop)  (artifact)  (final lint)
```

Everything else can run in parallel within phase boundaries.

### Within Each User Story

- Tests written first (the relevant `tests/backtest/test_*.py` file is created before its matching implementation file)
- Models / data classes before services that use them
- Adapters / pure functions before the engine main loop
- Main loop before audit emission and artifact writing
- Story complete before moving to next priority

### Parallel Opportunities

- Phase 1: T002, T003, T004 all in parallel
- Phase 2: T008, T009, T010, T011, T012, T014 all in parallel; T005, T006, T007, T013 sequentially (each is one file but the change set is one logical unit)
- US1 tests (T016, T017, T018) can be drafted in parallel; T018 depends on T021/T022 to actually pass
- US2 tests T024..T032 can all run in parallel once their target files exist
- US2 adapters T035, T036 can run in parallel after T033, T034
- US2 pure-function helpers T038, T039, T042 can run in parallel
- US3 tests T046..T049 all in parallel
- US4 tests T053..T055 all in parallel; T057, T058 in parallel
- Phase 7: T060, T061, T062, T063, T064 all in parallel

---

## Parallel Example: User Story 2 implementation

```bash
# Once T033 (Protocol) and T034 (cache) land, the two adapters can be developed in parallel:
Task: "Implement yfinance adapter in src/auto_invest/backtest/ohlcv/yfinance_adapter.py per contracts/ohlcv-adapter.md"
Task: "Implement KIS historical adapter in src/auto_invest/backtest/ohlcv/kis_historical_adapter.py per contracts/ohlcv-adapter.md"

# Pure-function helpers in parallel:
Task: "Implement fill model in src/auto_invest/backtest/fills.py per FR-B07 + R-4"
Task: "Implement portfolio ledger in src/auto_invest/backtest/portfolio.py per data-model.md SimulatedFill / DailyState"
Task: "Implement report computation in src/auto_invest/backtest/report.py per FR-B11 + R-7"

# Test files in parallel — write all of these BEFORE their implementations:
Task: "Write tests/backtest/test_fills_model.py covering FR-B07 hybrid branches"
Task: "Write tests/backtest/test_report_math.py with sine-wave fixture"
Task: "Write tests/backtest/test_verdict.py covering v1 thresholds and bankruptcy"
```

---

## Implementation Strategy

### Realistic ordering — why P2 stories ship with P1

The four user stories in spec 008 have priorities P1, P1, P2, P2. The naive read is "ship US1 alone first as MVP". That is wrong here, because:

- US1 (synthetic-shock for spec 007) and US2 (operator ad-hoc) share the **same** engine main loop (T041). Neither story can land without the loop.
- US3 (audit-log integration) is a six-line wiring on top of T041; FR-B16 demands every started run is traced. Splitting US3 out costs more than it saves.
- US4 (on-disk artifact) is what spec 007's canary harness *reads*. Without US4, US1 has nothing to hand spec 007.

So the realistic increments are:

1. **Increment 1 (one PR, one human-merge event)**: Phases 1–2 entirely. Lands the K-meta touch and the foundation. Test gate: T015 passes; live worker tests still pass (T013 added kwargs default `None`).
2. **Increment 2 (one PR, non-Kernel)**: Phase 3 (US1) + Phase 4 (US2) + Phase 5 (US3) + Phase 6 (US4) together. This is the engine's first usable shape. Test gate: all of T016..T058's tests pass.
3. **Increment 3 (one PR, non-Kernel)**: Phase 7 polish. Test gate: ruff clean; full test suite green; quickstart manually verified; T067 spot-check empty.

If any single PR review is too large, increment 2 splits naturally along the user-story boundaries (US1+US3+US4 first because spec 007 needs them; US2 second). But these are non-Kernel boundary slips, not constitutional ones.

### MVP scope

The narrowest shippable cut is **Increment 1 + Increment 2** as defined above. Increment 3 is hardening; the engine is *operationally* useful after Increment 2, but only Increment 3 makes it press-ready for spec 007's canary harness.

### Parallel team strategy

This feature is largely single-developer work because the integration points (T041 engine loop, T013 worker DI, T021 kernel-touch check) sit on the critical path and lock most of the parallelism. With two developers:

1. Developer A drives the critical path (T005 → T013 → T041 → T056 → T067).
2. Developer B owns the adapter pair (T035, T036), the pure-function helpers (T038, T039, T042), and the tests across all phases.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps each task to the user story it serves
- Phase 2 is intentionally a single review event — review the migration, the kernel.toml edit, the audit.py edit, and the worker DI seam together. Do NOT split this PR.
- Phase 3+ PRs MUST NOT touch any path under `kernel.toml` after T006 lands. Verify with the spot-check in T067.
- Tests written first; verify failure before implementation; commit after each task or logical group.
- Live worker behaviour MUST remain byte-identical to today after T013 — the new kwargs default to `None` and are the only branch a backtest activates.
