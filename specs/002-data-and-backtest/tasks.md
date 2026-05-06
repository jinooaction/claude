# Tasks: Multi-Asset Data Infrastructure & Backtest Engine

**Input**: Design documents from `specs/002-data-and-backtest/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Generated for every module the constitution's "test gate" covers — risk gates (reused from spec 001), backtest engine determinism, point-in-time barrier, cost model, ingestion-adapter conformance, promotion-seal verification, audit-log invariants. Pure plumbing (CLI ergonomics, README) ships without dedicated tests.

**Organization**: Tasks are grouped by user story so each phase ends at an independently-demonstrable checkpoint.

## Format

`- [ ] T### [P?] [Story?] Description with file path`

- `[P]` — task touches a different file than its phase peers and has no incomplete dependencies; eligible for parallel execution.
- `[US1] / [US2] / [US3] / [US4] / [US5]` — user-story phase tasks only. Setup, Foundational, and Polish phases carry no story label.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton additions, dev dependencies, fixture directories, gitignore. Most of the project skeleton already exists from spec 001; these tasks add the new top-level modules and extend ignore lists.

- [X] T001 Create source-tree additions: `src/auto_invest/{backtest,promotion}/__init__.py`, `src/auto_invest/market_data/adapters/__init__.py`, plus `tests/{unit,integration}/{backtest,ingestion,promotion}/` and `tests/fixtures/{historical/{equity,crypto},backtests}/` with `.gitkeep` files.
- [X] T002 Add runtime dependency `pyarrow` via `uv add pyarrow` and verify `pyproject.toml` reflects it (forward-compat Parquet export per R-5).
- [X] T003 [P] Extend `.gitignore` to ignore `data/backtests/` and `data/promotions/` (operator-specific run artifacts) and a new `data/historical/` if any adapter spills filesystem cache. — *No-op: existing `data/` ignore already covers these.*
- [X] T004 [P] Create `config/data.toml.example` documenting `enabled_adapters`, `default_vendor_per_kind`, `vendor_disagreement_tolerance_bps` per the schema shown in `quickstart.md` step 1.
- [X] T005 [P] Create `config/promotion.toml.example` documenting `PromotionThresholds` defaults from R-4.
- [X] T006 [P] Add `tests/fixtures/historical/equity/aapl_2023_2025_1d.jsonl` (renamed `aapl_2024_2025_1d.jsonl`, 522 weekday bars) and `tests/fixtures/historical/crypto/btcusd_2024_2025_1d.jsonl` (731 daily bars) containing pinned recorded OHLCV slices used by integration tests. *Synthetic seeded data — no live HTTP required. A future task may replace with real recorded fixtures.*

**Checkpoint**: New module trees exist; `uv sync` succeeds; `uv run pytest` passes (only spec 001 tests run; no new ones yet).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting infrastructure that every user story in this spec depends on — the new DB schema, the data-store reader with point-in-time barrier wiring, the adapter ABC, the calendar abstraction, the new config models, and the single-source-of-truth refactor for the risk gates.

**⚠️ CRITICAL**: No user-story phase begins until this phase is complete.

### Database schema (constitution IV — append-only)

- [X] T007 Author migration `0002_data_and_backtest.sql` defining `historical_bars`, `event_series`, `corporate_actions`, `data_quality_events`, `backtest_runs`, `promotion_seals`, `divergence_events` exactly as `data-model.md` specifies, including UPDATE/DELETE-blocking triggers and indices, at `src/auto_invest/persistence/migrations/0002_data_and_backtest.sql`.
- [X] T008 [P] Extend `src/auto_invest/persistence/db.py` migration runner test fixture so spec 001's `test_db_migrate.py` still passes after `0002` is applied; add `tests/unit/persistence/test_migration_0002.py` asserting every new table rejects UPDATE/DELETE while `frozen = 1`.

### Data-source + backtest config models (FR-D-001, FR-B-001)

- [X] T009 [P] Implement `DataSourcesConfig` pydantic model with `enabled_adapters` deny-by-default and `default_vendor_per_kind` validation in `src/auto_invest/config/data.py`.
- [X] T010 [P] Implement `CostModel`, `WalkForwardConfig`, `OOSWindowConfig`, and `BacktestConfig` pydantic models in `src/auto_invest/config/backtest.py` per `contracts/backtest-config.md` (decimal-as-string, no float literals).
- [X] T011 Implement canonical TOML hashing in `src/auto_invest/backtest/determinism.py`: sort keys, normalize decimals, SHA-256 the canonical bytes; expose `config_hash(toml_text)` and `rule_snapshot_hash(rule_text)`. Includes property-based test in `tests/unit/backtest/test_canonical_hash.py` confirming whitespace / key-order / decimal-format invariance.
- [X] T012 [P] Implement `PromotionThresholds` pydantic model (R-4 defaults) in `src/auto_invest/config/promotion.py`; loader reads `config/promotion.toml` if present, falls back to defaults.

### Market calendar abstraction (FR-D-006)

- [X] T013 Refactor `src/auto_invest/worker/schedule.py` into `src/auto_invest/market_data/calendar.py` exposing `MarketCalendar` ABC with two implementations: `DiscreteSessionCalendar` (existing exchange_calendars wrapper, used for nasdaq/nyse/krx/lse) and `AlwaysOpenCalendar` (used for crypto). Update spec 001 imports so the existing worker behaviour is preserved; add `tests/unit/market_data/test_calendar.py` covering both implementations.

### Ingestion adapter ABC (FR-D-003)

- [X] T014 Implement `IngestionAdapter` ABC, `InstrumentRef`, `BarRecord`, `EventRecord`, `CorporateActionRecord` dataclasses, `ADAPTERS` registry, and `register_adapter` decorator in `src/auto_invest/market_data/adapters/__init__.py` per `contracts/ingestion-adapter.md`.
- [X] T015 [P] Add the shared adapter conformance test scaffold at `tests/integration/ingestion/test_adapter_conformance.py` parametrising over `ADAPTERS.values()`. The scaffold passes with zero adapters registered (each adapter's PR adds its own registration).

### Data store extensions (FR-D-002, FR-B-002)

- [X] T016 Extend `src/auto_invest/market_data/store.py` with `HistoricalBarsStore.write_bars(records, *, as_of_ts)` and `HistoricalBarsStore.write_events(records, *, as_of_ts)` and `HistoricalBarsStore.write_corporate_actions(records, *, as_of_ts)`. Writers are append-only; idempotent on duplicate `(asset_class, venue, symbol, kind, vendor, ts, as_of_ts)`.
- [X] T017 Implement `src/auto_invest/market_data/revisions.py` exposing `latest_as_of(...)`, `iter_bars(..., as_of_ts_pin)`, `iter_events(..., as_of_ts_pin)` and `iter_corporate_actions(..., as_of_ts_pin)`. **Reads enforce the point-in-time barrier**: any bar / event / action whose `as_of_ts > as_of_ts_pin` or whose content `ts > requested_window_end` is filtered before yielding (depends on T007, T016).
- [X] T018 Add `tests/unit/market_data/test_revisions.py` covering: as_of_ts pin filters out late revisions, original revision still returned at its own `as_of_ts`, ordering invariants, NULL-aware key handling for instrument-agnostic events.

### Data quality (FR-D-005)

- [X] T019 [P] Extend `src/auto_invest/market_data/quality.py` with `detect_gaps(instrument, kind, calendar, from_utc, to_utc)` and `detect_vendor_disagreement(instrument, kind, tolerance_bps)`; both write rows into `data_quality_events`. Add `tests/unit/market_data/test_quality.py`.

### Risk-gate single source of truth (SC-005)

- [X] T020 Audit `src/auto_invest/risk/` and `src/auto_invest/execution/router.py` for any live-only assumptions (e.g., references to a real broker client). Refactor so the gate chain is constructible against any `Broker`-protocol implementation. No new behaviour; existing 256 tests must still pass.
- [X] T021 Implement `src/auto_invest/execution/backtest_broker.py` exposing the same `Broker` protocol as the live KIS adapter, but with a `place_order(order, *, bar)` method that defers to the cost model (added in Phase 3). Add `tests/unit/execution/test_backtest_broker_protocol.py` confirming protocol parity (mypy-style structural check via `runtime_checkable`).

**Checkpoint**: New tables exist; new config models load; calendar abstraction covers both venue families; ingestion ABC + conformance scaffold compiles; data store reader enforces the point-in-time barrier; risk-gate code path is import-clean from both routers.

---

## Phase 3: User Story 1 — Backtest a candidate rule before risking capital (Priority: P1) 🎯 MVP

**Goal**: Operator runs `auto-invest backtest --rule <file> --from <date> --to <date>` against locally-cached historical data and receives a deterministic, reproducible report covering returns / drawdown / hit rate / exposure / turnover / itemised cost.

**Independent Test**: With pre-loaded `tests/fixtures/historical/equity/aapl_2023_2025_1d.jsonl` ingested into a temp DB, run a known RSI rule over a 12-month window; assert the report exists, contains the FR-B-008 metric set, runs in under 60 s, and a re-run produces a byte-identical metrics file.

### Implementation

- [X] T022 [US1] Implement `src/auto_invest/backtest/portfolio.py`: cash + position accounting in the simulator. Tracks per-instrument quantity, average cost basis, realised P&L per closed leg, mark-to-market unrealised P&L per bar.
- [X] T023 [US1] Implement `src/auto_invest/backtest/cost_model.py` v1: commission (`commission_bps` × notional + min) + fixed half-spread slippage. (Square-root impact and participation cap come in US2, T035.)
- [X] T024 [US1] Wire `BacktestBroker.place_order` to `cost_model` so simulated fills are produced from the bar's OHLC + the cost model output. Update `tests/unit/execution/test_backtest_broker_protocol.py` to cover a fill round-trip.
- [X] T025 [US1] Implement `src/auto_invest/backtest/engine.py`: event-driven replay loop that streams bars from `revisions.iter_bars(..., as_of_ts_pin)` in chronological order, evaluates the rule's trigger via the existing `strategy/triggers.py`, runs the gate chain via `execution/router.py`, places orders via `BacktestBroker`, updates `Portfolio`, and writes simulated audit rows + cost-itemised orders to in-memory buffers. Engine returns a `BacktestResult` dataclass (depends on T017, T022, T023, T024).
- [X] T026 [US1] Implement `src/auto_invest/backtest/metrics.py`: total return, CAGR, volatility, Sharpe, Sortino, max drawdown, hit rate, win/loss ratio, exposure, turnover, gross transaction cost, per-trade P&L distribution. Add `tests/unit/backtest/test_metrics.py` against canonical synthetic series.
- [X] T027 [US1] Implement `src/auto_invest/backtest/report.py`: emit `report.md` (human-readable) + `metrics.json` (machine-readable) into `data/backtests/<run_id>/`. Both files derive from the same `BacktestResult` so divergence is impossible.
- [X] T028 [US1] Wire run-directory layout in `engine.py`: write `inputs/run.toml` (canonicalised), `inputs/rule_snapshot.toml`, `inputs/data_pin.json`, `audit_log.jsonl`, `orders.jsonl`, `metrics.json`, `report.md`, then insert a row into `backtest_runs`. `run_id = sha256(rule_snapshot_hash || config_hash || data_pin_hash)[:12]`.
- [X] T029 [US1] Add `auto-invest backtest` CLI subcommand in `src/auto_invest/cli.py` per `contracts/backtest-cli.md`: support `--rule` flag form (auto-generate `run.toml`) and `--config` form. Idempotent re-run on existing `run_id`. Exit codes per the contract (0 / 1 / 2 / 6 implemented in this phase; 3 / 4 / 5 land in US2 and Polish).
- [X] T030 [US1] Add `tests/integration/backtest/test_single_run.py`: pre-load AAPL fixture, run a known rule, assert report exists, metrics conform, run directory is well-formed.
- [X] T031 [US1] Add `tests/integration/backtest/test_determinism.py`: run twice with the same inputs; assert identical `run_id`, byte-identical `metrics.json`, byte-identical `audit_log.jsonl`. (SC-002)

**Checkpoint**: `auto-invest backtest --rule sample.toml --from 2024-01-01 --to 2024-12-31` produces a usable report and a re-run hits the idempotent path. The report can already be read by an operator. **It is not yet trustworthy**: there is no lookahead barrier in the strategy contract, costs lack market-impact modelling, and limit orders have no time-in-force handling. US2 closes those gaps.

---

## Phase 4: User Story 2 — Replay is point-in-time correct and uses realistic execution costs (Priority: P1)

**Goal**: The backtest engine refuses to read post-decision data, applies a defensible cost model with commission + half-spread + sqrt impact + participation cap, and honours limit-order time-in-force semantics. After this phase, the report is *trustworthy*.

**Independent Test**: A "cheating" strategy that reads `bars[t+1]` raises `LookaheadError` and the run aborts with exit code 3. A market-order fill in a thin bar is partially filled at the participation cap. A limit order priced outside the bar's range expires unfilled per its TIF.

### Implementation

- [ ] T032 [US2] Define `LookaheadError` in `src/auto_invest/backtest/engine.py`. Wrap every read that the strategy makes against the data store via a `BarWindow` context object whose `__getitem__` enforces `bar.as_of_ts <= as_of_ts_pin` and `bar.bar_open_ts <= current_decision_ts`. Any violation raises `LookaheadError` and the engine aborts with status `aborted_lookahead` and exit code 3.
- [ ] T033 [US2] Add `tests/integration/backtest/test_lookahead_barrier.py` with a synthetic strategy that intentionally indexes one bar past the decision time; assert `LookaheadError` is raised, the run directory carries `result_status="aborted_lookahead"`, the CLI exits 3.
- [ ] T034 [US2] Add `tests/unit/backtest/test_revisions_pin.py` covering: a late-arriving revision with `as_of_ts > pin` is invisible during replay; the pre-revision row is still visible at its original `as_of_ts`. (FR-B-002)
- [ ] T035 [US2] Extend `src/auto_invest/backtest/cost_model.py` with the square-root market-impact term (`impact_coeff × σ × sqrt(order_qty / bar_volume) × notional`) and the participation cap (default 10% of bar volume). Itemise `commission` / `half_spread` / `impact` separately in `orders.jsonl`. Tests in `tests/unit/backtest/test_cost_model.py`.
- [ ] T036 [US2] Implement time-in-force handling in `BacktestBroker.place_order` for `day` / `gtc` / `ioc` / `fok`: if the bar's range does not include the limit price, expire/cancel per TIF; record the cancel/expire in the simulated audit log identically to live behaviour. Tests in `tests/unit/execution/test_backtest_broker_tif.py`.
- [ ] T037 [US2] Wire corporate-action application in `engine.py`: between bars, consult `revisions.iter_corporate_actions` for the instrument; apply splits to position quantity and cost basis, apply cash dividends to cash. Tests in `tests/integration/backtest/test_corporate_actions.py` using a synthetic 2-for-1 split fixture.
- [ ] T038 [US2] Add `tests/unit/backtest/test_risk_gate_parity.py`: import `risk/` from both `execution/router.py` (live path) and `execution/backtest_broker.py` (simulated path); assert they reference the **same module objects** (single source of truth — SC-005).

**Checkpoint**: A strategy that does not cheat passes; one that does, dies. The cost report shows commission / half-spread / impact line items. Limit orders behave the same as in live trading. The backtest is now trustworthy enough to be the basis for promotion (which lands in US5).

---

## Phase 5: User Story 3 — Multi-source, multi-asset ingestion (Priority: P2)

**Goal**: Operator can run `auto-invest data ingest --adapter <name>` to populate the unified store from a vendor; `auto-invest data describe` shows what is loaded; the public-crypto adapter exercises the always-open calendar path; vendor pinning per backtest run is honoured.

**Independent Test**: With `enabled_adapters = ["kis_us_equity", "crypto_public"]`, ingest one month of AAPL daily bars and one month of BTC-USD daily bars; `data describe --symbol AAPL` shows the KIS row, `data describe --symbol BTC-USD` shows the crypto row; running a backtest with `--vendor crypto_public` against BTC-USD reads from the crypto rows only.

### Implementation

- [ ] T039 [P] [US3] Implement `src/auto_invest/market_data/adapters/kis_us_equity.py` wrapping the existing `broker/overseas.py` quote/history endpoints inside the `IngestionAdapter` ABC. Re-uses the existing `tenacity` retry, `AsyncTokenBucket`, and `CircuitBreaker` from spec 001 (constitution VII).
- [ ] T040 [P] [US3] Implement `src/auto_invest/market_data/adapters/crypto_public.py` against a public-keyless candles endpoint (e.g., Binance public klines). `needs_auth = False`. Uses `AlwaysOpenCalendar`. Recorded fixtures under `tests/fixtures/historical/crypto/`.
- [ ] T041 [US3] Add `auto-invest data ingest` CLI subcommand in `cli.py`: looks up adapter by name in `ADAPTERS`, drives `fetch_bars` / `fetch_events` / `fetch_corporate_actions` for the requested window, writes via `HistoricalBarsStore`. Idempotent — re-ingest is a no-op when content matches.
- [ ] T042 [US3] Add `auto-invest data describe` CLI subcommand: reports per `(asset_class, venue, symbol, kind, vendor)` earliest / latest record, gap count, last revision time, vendor count. Reads `is_adjusted=0` by default; `--adjusted` switches.
- [ ] T043 [US3] Add `auto-invest data revisions` CLI subcommand: lists recorded revisions for one `(instrument, kind, ts)` ordered by `as_of_ts_utc`.
- [ ] T044 [US3] Wire vendor pinning in `BacktestConfig`: per-instrument `vendor` overrides the default from `DataSourcesConfig`. The engine resolves vendor at config-load time and embeds it in `data_pin.json` so the run is reproducible.
- [ ] T045 [P] [US3] Activate the adapter conformance test (T015) for `kis_us_equity` and `crypto_public`: ordering, idempotence, calendar consistency, resilience (synthetic 5xx then 200 → retry; 10× 5xx → breaker open). Live HTTP gated by `KIS_LIVE_TEST=1` / `CRYPTO_LIVE_TEST=1`; CI uses recorded fixtures only.
- [ ] T046 [US3] Add `tests/integration/ingestion/test_multi_vendor.py`: ingest the same instrument from two simulated vendors with disagreeing prices; assert `vendor_disagreement` is recorded in `data_quality_events`; assert a backtest run pinned to one vendor is unaffected by the other.

**Checkpoint**: Two adapters live in the registry; `data describe` shows them side by side; a backtest pinned to one vendor reads only that vendor; the second-adapter PR (crypto) was completed without modifying the first (kis_us_equity).

---

## Phase 6: User Story 4 — Walk-forward and held-out OOS evaluation (Priority: P2)

**Goal**: `auto-invest backtest --mode oos --oos-from <date> --oos-to <date>` and `--mode walkforward` produce a report with in-sample and out-of-sample metrics side-by-side; the OOS window is unreadable during in-sample evaluation.

**Independent Test**: Run a fixed-parameter strategy in (a) `single`, (b) `oos` with last 6 months reserved, (c) `walkforward` with 365/90/90 windows; verify the report shows three sections, each with its own metric block; verify a strategy that tries to read OOS data during in-sample raises `LookaheadError`.

### Implementation

- [ ] T047 [US4] Implement `src/auto_invest/backtest/walkforward.py` exposing `iter_folds(window_from, window_to, train_days, test_days, step_days, calendar)`; folds snap to session boundaries (R-3). Tests in `tests/unit/backtest/test_walkforward_folds.py`.
- [ ] T048 [US4] Extend `engine.py` to honour `WalkForwardConfig`: per-fold the engine instantiates a fresh `Portfolio` with the operator's declared starting capital, restricts the `as_of_ts_pin` to the fold's training end, and writes per-fold output under `data/backtests/<run_id>/walkforward/fold_NNN/`.
- [ ] T049 [US4] Extend `engine.py` to honour `OOSWindowConfig`: in-sample reads are restricted to `[window_from, oos_from)` (the `BarWindow` context refuses any read into the OOS slice during the in-sample phase); OOS reads are allowed only during the OOS phase. Tests in `tests/integration/backtest/test_oos_barrier.py`.
- [ ] T050 [US4] Implement aggregated reporting in `report.md` for `walkforward` and `oos` modes: per-fold metrics, fold-level Sharpe variance, worst-fold drawdown, OOS metrics block. `metrics.json` includes a separate `oos` section.
- [ ] T051 [US4] Apply default OOS reservation per R-3 (`max(20% of window, last 6 months)`) when `--mode oos` is set without explicit `--oos-from` / `--oos-to`. Tests in `tests/unit/backtest/test_oos_default_window.py`.
- [ ] T052 [US4] Add `tests/integration/backtest/test_walkforward_e2e.py`: full walk-forward run on a synthetic dataset, assert per-fold + aggregated metrics are present and consistent.

**Checkpoint**: Walk-forward and OOS modes work end-to-end; the OOS barrier is enforced by the same point-in-time machinery that catches lookahead bugs.

---

## Phase 7: User Story 5 — Promotion seal as a first-class input to canary (Priority: P3)

**Goal**: The live worker refuses to load a rule that lacks a non-revoked, threshold-clearing promotion seal. The operator issues seals with `auto-invest promote --rule <r> --backtest <id> --issue` and revokes with `--revoke`. The daily reporter computes live-vs-backtest divergence and halts a rule on sustained divergence.

**Independent Test**: Submit a rule without a seal to the live worker → exit code 11. Issue a seal whose OOS metrics fail one threshold → `promote --issue` exits 8 with a per-threshold diff. Issue a passing seal → worker accepts the rule. After 5 days of divergence > threshold, the rule is auto-halted.

### Implementation

- [ ] T053 [P] [US5] Implement `src/auto_invest/promotion/thresholds.py`: load `PromotionThresholds` from `config/promotion.toml` falling back to R-4 defaults. Tests in `tests/unit/promotion/test_thresholds.py`.
- [ ] T054 [US5] Implement `src/auto_invest/promotion/seal.py`: write/read/validate `data/promotions/<seal_id>.toml` per `contracts/promotion-seal.md`; insert mirror row into `promotion_seals`; expose `latest_active_seal(rule_snapshot_hash)`. Tests in `tests/unit/promotion/test_seal.py`.
- [ ] T055 [US5] Implement the 7-step seal verification in `src/auto_invest/promotion/seal.py::verify_seal_for_rule(rule_path)`. Each step's failure mode is logged and returned with a numeric step index. Tests in `tests/unit/promotion/test_seal_verification.py` covering each of the 7 failure modes.
- [ ] T056 [US5] Add `auto-invest promote` CLI subcommand in `cli.py`: `--issue`, `--check`, `--revoke <seal_id> --reason <text>` per `contracts/backtest-cli.md`. Exit codes 0 / 1 / 7 / 8 / 9.
- [ ] T057 [US5] Extend `src/auto_invest/worker/__init__.py` startup loader: for each rule whose `stage` is `CANARY` or `FULL_LIVE`, call `verify_seal_for_rule(rule.path)`; on any failure, exit non-zero (code 11) and write the rejection to the audit log with the failing step index. Tests in `tests/integration/promotion/test_worker_rejection.py`.
- [ ] T058 [US5] Implement `src/auto_invest/promotion/divergence.py`: daily comparison of live realised P&L distribution vs backtest distribution per promoted rule; writes rows into `divergence_events`; flips a per-rule halt after `divergence_alert_window_days` of breach. Tests in `tests/unit/promotion/test_divergence.py`.
- [ ] T059 [US5] Extend `src/auto_invest/reports/daily.py` (spec 001) to surface the divergence flag on the daily report when present. No-op when no rule has a seal yet.
- [ ] T060 [US5] Add `tests/integration/promotion/test_seal_lifecycle.py`: backtest → check (fail) → tune → backtest → check (pass) → issue → load in worker (accept) → revoke → reload in worker (reject).

**Checkpoint**: All five user stories are independently functional. Constitution principle VI is fully operational. The system has its first self-improving primitive (live-vs-backtest divergence).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Performance benchmark, quickstart validation, README updates, documentation pointers, edge-case completeness, and the `--max-runtime-seconds` exit path that was deferred from US1.

- [ ] T061 [P] Update `README.md`: add a section on `auto-invest backtest`, `auto-invest data`, and `auto-invest promote`; update "What v1 does NOT do" to reflect that backtest + promotion now exist; add a pointer to `specs/002-data-and-backtest/quickstart.md`.
- [ ] T062 [P] Implement `--max-runtime-seconds` budget in `engine.py`: a wall-clock guard that aborts cleanly past the budget with status `aborted_runtime` and exit code 5. Tests in `tests/unit/backtest/test_runtime_budget.py`.
- [ ] T063 Implement performance benchmark `tests/integration/backtest/test_perf_5_year.py`: a 5-year 1m-bar synthetic backtest must complete in < 60 s and use < 1 GB resident memory on the operator's hardware reference (skipped on CI when `BENCH=0`). (SC-003)
- [ ] T064 [P] Run the `quickstart.md` end-to-end as an operator-style script under `tests/integration/quickstart/test_quickstart_002.py` (using fixture data only; no live HTTP). Asserts each section's expected outputs.
- [ ] T065 Validate the migration path on a real operator DB: spin up a copy of `data/auto_invest.db` from the operator's machine, run `auto-invest db migrate`, confirm zero data loss, all spec 001 tables intact, all spec 002 tables present. Document the procedure in `quickstart.md` step "0 — Upgrade from v1".

**Checkpoint**: Performance budget met, quickstart runs green, operator DB upgrade procedure documented. Spec 002 ships when this phase is green.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies; can begin immediately.
- **Phase 2 (Foundational)**: depends on Phase 1; **blocks all user-story phases**.
- **Phase 3 (US1 — Backtest MVP)**: depends on Phase 2.
- **Phase 4 (US2 — point-in-time + cost realism)**: depends on Phase 3 (extends `engine.py`, `cost_model.py`, `BacktestBroker`).
- **Phase 5 (US3 — multi-source ingestion)**: depends on Phase 2 (specifically T014 ABC, T016/T017 store + revisions). Can run **in parallel with Phase 3 and Phase 4** if staffed.
- **Phase 6 (US4 — walk-forward + OOS)**: depends on Phase 3 (engine), Phase 4 (point-in-time barrier reuse).
- **Phase 7 (US5 — promotion seal)**: depends on Phase 3 (`backtest_runs` rows exist), Phase 4 (trustworthy metrics), Phase 6 (OOS metrics required for promotion).
- **Phase 8 (Polish)**: depends on whichever user stories the operator chooses to ship together; minimum is Phase 3 + Phase 4.

### Within Each User Story

- Models / schemas before services
- Services before CLI subcommands
- Implementation before integration tests

### Parallel Opportunities

- Phase 1 tasks T003 / T004 / T005 / T006 are all independent files and can run in parallel.
- Phase 2 has several `[P]` tasks (T008, T009, T010, T012, T015, T019) that touch independent files; the rest serialise on `0002_data_and_backtest.sql` (T007) → store extensions (T016/T017).
- Phase 5 (ingestion) is genuinely independent of Phase 3 (engine) once Phase 2 lands; one developer could pick up US3 while another is on US1+US2.
- T039 (KIS adapter) and T040 (crypto adapter) are parallel — distinct files, distinct fixtures.
- T053 (thresholds) is parallel with T054 (seal); T058 (divergence) follows T054.

---

## Implementation Strategy

### MVP First (Phase 3 only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (US1 — Backtest MVP).
3. **STOP and validate**: backtest runs, deterministic re-run holds, golden metrics match.
4. The operator can already audit candidate rules. The report is **not yet trustworthy** for promotion — that needs Phase 4.

### Trustworthy Backtest

5. Complete Phase 4 (US2 — point-in-time + cost realism).
6. After Phase 4, the report can be the basis for a promotion-gate decision (mechanically issued by Phase 7 once that lands).

### Asset-Class Generalisation

7. Complete Phase 5 (US3 — multi-source ingestion). This unlocks crypto / FX / future asset classes at the data layer (trading those classes is a future spec gated by a constitution amendment).

### Hardened Validation

8. Complete Phase 6 (US4 — walk-forward + OOS). Now the workflow can resist overfitting.

### Promotion Loop

9. Complete Phase 7 (US5 — promotion seal). The live worker now refuses unsealed rules; constitution principle VI is mechanically enforced; the divergence metric primes the self-improving loop.

### Ship

10. Complete Phase 8 (Polish). Run the full test suite (256 from spec 001 + ~40 new from spec 002). Land on `main` via PR after operator review.

---

## Notes

- `[P]` tasks = different files, no incomplete-task dependencies. Avoid claiming `[P]` for two tasks that both edit `cli.py` or both edit `engine.py`.
- Every user story is a complete, independently-shippable increment. The operator is free to stop after any phase and resume later.
- Tests use recorded fixtures only; live HTTP is gated by per-vendor env vars (`KIS_LIVE_TEST=1`, `CRYPTO_LIVE_TEST=1`).
- Constitution principle VI becomes machinery only after Phase 7. Until then, the promotion seal verification is dead code that the worker does not invoke (it lives behind a feature flag set in the worker startup).
- After Phase 7 lands, **all rules in the operator's canary or full-live stage on `main` must have a matching seal**. This requires either re-backtesting existing canary rules or temporarily disabling the seal gate via `--unsealed-development` + `--dry-run` until seals are issued.
